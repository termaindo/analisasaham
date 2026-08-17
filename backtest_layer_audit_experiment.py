"""
backtest_layer_audit_experiment.py
====================================
Script riset OFFLINE untuk menguji hipotesis mean-reversion Layer Trend,
lanjutan dari backtest_layer_audit.py.

LATAR BELAKANG
--------------
Layer audit (backtest_layer_audit.py, 30 ticker, N=1355, non-overlapping,
Agustus 2026 — setelah bug _calc_supertrend() diperbaiki) menunjukkan 6 dari
6 indikator trend-confirmation bullish (EMA_Stack, Supertrend, BB_Mid, SAR,
MACD, Candlestick) BERKORELASI NEGATIF dengan forward return 5D/10D — bukan
positif seperti diasumsikan compute_score(). Skor total pun ikut negatif
signifikan di 5D (r=-0.103, p=0.0001) dan 10D (r=-0.093, p=0.0006).

Uji cepat lewat rekonstruksi dari data existing (Trend_Total + Momentum_Total
+ Entry_Total - penalti ADX/Vol, sudah diverifikasi cocok 100% dengan kolom
Skor asli) menunjukkan:
  - Membalik tanda Layer Trend (reversed): r=+0.074 (5D, p=0.0068),
    r=+0.064 (10D, p=0.0188) — signifikan, arah benar, TAPI magnitude kecil
    dan win rate bucket BELI masih di bawah 50% (47.5% di 5D).
  - Menghapus Layer Trend (neutral): r=-0.023 (5D, p=0.39) — skor jadi
    tidak informatif sama sekali.

Script ini menjalankan ulang walk-forward SECARA LANGSUNG (bukan rekonstruksi
dari data lama) supaya bisa divalidasi dengan data segar (mis. ticker BBRI
yang sempat gagal fetch), dan supaya hasilnya bisa dipercaya independen dari
asumsi rekonstruksi di atas.

PENTING — TIDAK ADA PERUBAHAN DI modules/teknikal.py
------------------------------------------------------
Script ini TIDAK memodifikasi compute_score() maupun mengimpor salinan
duplikat teknikal.py. Ia memanggil compute_score() APA ADANYA (persis versi
produksi yang sudah di-fix bug Supertrend-nya), lalu membaca ulang
Trend_Total / Momentum_Total / Entry_Total / ADX_ok / Vol_ok dari dict hasil
yang SUDAH tersedia (sama seperti backtest_layer_audit.py), dan menyusun
ulang 3 varian skor dari situ:

    raw_normal   = Trend_Total + Momentum_Total + Entry_Total - penalti
    raw_reversed = -Trend_Total + Momentum_Total + Entry_Total - penalti
    raw_neutral  =  0           + Momentum_Total + Entry_Total - penalti
    Skor_* = clip(raw_*, -100, 100)

Formula penalti ADX/Vol disalin persis dari compute_score() (PEN_ADX_WEAK=20,
PEN_VOL_SEPI=10, masing-masing dikali 0.5 jika ADX_ok/Vol_ok False) — bukan
logika baru, murni transkripsi ulang exact yang sudah divalidasi berulang
kali menghasilkan kecocokan 100% dengan kolom Skor asli compute_score().

Keuntungan desain ini dibanding membuat teknikal_experimental.py (salinan
duplikat teknikal.py yang dimodifikasi): tidak ada risiko file duplikat jadi
basi kalau modules/teknikal.py diubah lagi di masa depan, dan nol risiko ke
kode produksi karena compute_score() dipanggil tanpa modifikasi apa pun.

CARA PAKAI (identik dengan backtest_layer_audit.py)
-----------------------------------------------------
    python backtest_layer_audit_experiment.py --tickers BBRI \
        --years 5 --non-overlapping --tag bbri_only

    python backtest_layer_audit_experiment.py \
        --tickers BBCA,BBRI,BMRI,BBNI,BRIS \
        --years 5 --non-overlapping --tag batch1_bank_experiment

Output: outputs/layer_audit_experiment_<timestamp><tag>.csv
    Satu baris per titik sinyal, kolom:
    - Ticker, Tanggal, HargaEntry, NonOverlapping
    - Trend_Total, Momentum_Total, Entry_Total, ADX_ok, Vol_ok (komponen mentah)
    - Skor_normal, Skor_reversed, Skor_neutral (3 varian untuk dibandingkan)
    - Return_{h}D_pct, MaxDD_{h}D_pct untuk tiap holding period

Setelah semua batch selesai, gabungkan CSV-nya dan bandingkan korelasi /
win-rate per varian (r dan p untuk Skor_normal vs Skor_reversed vs
Skor_neutral terhadap Return_*D_pct) — sama seperti dilakukan pada hasil
rekonstruksi, tapi sekarang dari perhitungan langsung, bukan rekonstruksi.
"""

import argparse
import os
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from modules.teknikal import calculate_technical_indicators, compute_score
except ImportError:
    try:
        from teknikal import calculate_technical_indicators, compute_score
    except ImportError as e:
        print(
            "❌ Tidak bisa import calculate_technical_indicators/compute_score dari "
            "modules/teknikal.py atau teknikal.py. Jalankan script ini dari root repo "
            "(folder yang sama dengan app.py).\n"
            f"Detail: {e}"
        )
        sys.exit(1)

try:
    from utils.data_loader import get_liquid_stocks
except ImportError:
    get_liquid_stocks = None

import yfinance as yf


# ─────────────────────────────────────────────────────────────────────────────
# KONSTANTA — disalin PERSIS dari compute_score() di modules/teknikal.py
# Kalau nilai ini pernah diubah di teknikal.py, ubah juga di sini agar
# rekonstruksi tetap akurat.
# ─────────────────────────────────────────────────────────────────────────────
PEN_ADX_WEAK = 20
PEN_VOL_SEPI = 10


def fetch_history(ticker: str, years: int) -> pd.DataFrame:
    try:
        tk = yf.Ticker(ticker)
        df = tk.history(period=f"{years}y", interval="1d")
        if df.empty:
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        mask = (df["Close"] > 0) & (df["Volume"] > 0) & df["Close"].notna()
        df = df[mask].copy()
        return df
    except Exception as e:
        print(f"  ⚠️ Gagal fetch {ticker}: {e}")
        return pd.DataFrame()


def _compute_3_variants(sc: dict) -> dict:
    """
    Dari satu hasil compute_score() (TIDAK dimodifikasi), susun ulang 3 varian
    skor: normal (persis produksi), reversed (Layer Trend dibalik tandanya),
    neutral (Layer Trend dihapus/dinolkan). Momentum, Entry, dan penalti
    ADX/Vol identik di ketiga varian — hanya kontribusi Trend yang berbeda.
    """
    l1 = sc.get("layer1_filter", {})
    l2 = sc.get("layer2_trend", {})
    l3 = sc.get("layer3_momentum", {})
    l4 = sc.get("layer4_entry", {})

    trend_total = l2.get("_total", np.nan)
    momentum_total = l3.get("_total", np.nan)
    entry_total = l4.get("_total", np.nan)
    adx_ok = l1.get("ADX", {}).get("ok", True)
    vol_ok = l1.get("Volume", {}).get("ok", True)

    penalty = 0.0
    if not adx_ok:
        penalty += PEN_ADX_WEAK * 0.5
    if not vol_ok:
        penalty += PEN_VOL_SEPI * 0.5

    raw_normal = trend_total + momentum_total + entry_total - penalty
    raw_reversed = -trend_total + momentum_total + entry_total - penalty
    raw_neutral = 0.0 + momentum_total + entry_total - penalty

    def _clip(x):
        return max(-100, min(100, x))

    return {
        "Trend_Total": trend_total,
        "Momentum_Total": momentum_total,
        "Entry_Total": entry_total,
        "ADX_ok": adx_ok,
        "Vol_ok": vol_ok,
        "Skor_normal": round(_clip(raw_normal), 2),
        "Skor_reversed": round(_clip(raw_reversed), 2),
        "Skor_neutral": round(_clip(raw_neutral), 2),
    }


def walk_forward_experiment(
    ticker: str,
    years: int,
    holding_days: list[int],
    min_warmup: int,
    sample_every: int,
    non_overlapping: bool = False,
) -> list[dict]:
    df_raw = fetch_history(ticker, years)
    if df_raw.empty or len(df_raw) < (min_warmup + max(holding_days) + 5):
        return []

    try:
        df_ind = calculate_technical_indicators(df_raw)
    except Exception as e:
        print(f"  ⚠️ Gagal hitung indikator {ticker}: {e}")
        return []

    n = len(df_ind)
    max_hold = max(holding_days)
    effective_step = max(sample_every, max_hold) if non_overlapping else max(1, sample_every)

    hasil = []
    idx_range = range(min_warmup, n - max_hold, effective_step)

    for i in idx_range:
        window = df_ind.iloc[: i + 1]   # expanding window, tanpa lookahead — sama seperti backtest_layer_audit.py
        try:
            sc = compute_score(window, timeframe="swing")   # compute_score() TIDAK dimodifikasi
        except Exception:
            continue

        harga_entry = float(df_ind["Close"].iloc[i])
        tanggal = df_ind.index[i]

        row = {
            "Ticker": ticker.replace(".JK", ""),
            "Tanggal": tanggal.strftime("%Y-%m-%d"),
            "HargaEntry": harga_entry,
            "NonOverlapping": non_overlapping,
        }
        row.update(_compute_3_variants(sc))

        for h in holding_days:
            harga_fwd = float(df_ind["Close"].iloc[i + h])
            ret_pct = (harga_fwd - harga_entry) / harga_entry * 100
            low_window = df_ind["Low"].iloc[i + 1 : i + h + 1]
            max_dd_pct = (
                ((low_window.min() - harga_entry) / harga_entry * 100)
                if not low_window.empty else np.nan
            )
            row[f"Return_{h}D_pct"] = round(ret_pct, 2)
            row[f"MaxDD_{h}D_pct"] = round(max_dd_pct, 2)

        hasil.append(row)

    return hasil


def load_universe(args) -> list[str]:
    if args.tickers:
        return [t.strip().upper().replace(".JK", "") + ".JK" for t in args.tickers.split(",") if t.strip()]
    if args.from_liquid:
        if get_liquid_stocks is None:
            print("❌ utils/data_loader.py tidak bisa di-import — pakai --tickers.")
            sys.exit(1)
        df = get_liquid_stocks()
        if df.empty:
            print("❌ liquid_stocks.csv kosong/tidak ditemukan — pakai --tickers.")
            sys.exit(1)
        col = "Ticker" if "Ticker" in df.columns else df.columns[0]
        return [(t if t.endswith(".JK") else t + ".JK") for t in df[col].astype(str).str.strip().tolist()]
    print("❌ Harus pilih salah satu: --tickers TICKER1,TICKER2,... atau --from-liquid")
    sys.exit(1)


def _quick_summary(df: pd.DataFrame, holding_days: list[int]) -> None:
    """Cetak ringkasan korelasi Pearson per varian ke terminal — cek cepat tanpa perlu buka CSV."""
    from scipy import stats
    print("\n" + "=" * 80)
    print("RINGKASAN CEPAT — Pearson r (Skor varian vs Return), N=%d" % len(df))
    print("=" * 80)
    for variant in ["Skor_normal", "Skor_reversed", "Skor_neutral"]:
        line = f"{variant:16s}"
        for h in holding_days:
            r, p = stats.pearsonr(df[variant], df[f"Return_{h}D_pct"])
            flag = "*" if p < 0.05 else " "
            line += f" | {h}D: r={r:+.3f} p={p:.4f}{flag}"
        print(line)
    print("(* = signifikan p<0.05)")
    print(
        "\nCatatan: hasil di atas dari batch/ticker yang dipilih saat ini saja. "
        "Gabungkan semua batch dengan pandas.concat sebelum menyimpulkan apa pun "
        "secara keseluruhan — jangan simpulkan dari satu batch kecil."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Backtest eksperimen: uji hipotesis mean-reversion Layer Trend (normal/reversed/neutral)"
    )
    parser.add_argument("--tickers", type=str, default=None)
    parser.add_argument("--from-liquid", action="store_true")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--holding-days", type=str, default="5,10,20")
    parser.add_argument("--min-warmup", type=int, default=250)
    parser.add_argument("--sample-every", type=int, default=2)
    parser.add_argument("--non-overlapping", action="store_true")
    parser.add_argument("--max-workers", type=int, default=6)
    parser.add_argument("--output-dir", type=str, default="outputs")
    parser.add_argument("--tag", type=str, default=None,
                         help="Label batch, mis. 'bbri_only' atau 'batch1_bank_experiment'.")
    args = parser.parse_args()

    holding_days = sorted(int(x.strip()) for x in args.holding_days.split(",") if x.strip())
    tickers = load_universe(args)
    max_hold = max(holding_days)

    if args.non_overlapping and args.sample_every < max_hold:
        print(f"ℹ️ --non-overlapping aktif: langkah sampling efektif = {max_hold} hari bursa.")

    print(f"📊 Layer audit EXPERIMENT | Universe: {len(tickers)} ticker | Histori: {args.years} tahun | "
          f"Holding: {holding_days} | Mode: {'NON-OVERLAPPING' if args.non_overlapping else 'overlapping'}")
    print("🔄 Menjalankan (bisa beberapa menit)...\n")

    t0 = time.time()
    all_rows: list[dict] = []
    gagal: list[str] = []

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(
                walk_forward_experiment, t, args.years, holding_days,
                args.min_warmup, args.sample_every, args.non_overlapping,
            ): t
            for t in tickers
        }
        done = 0
        for future in as_completed(futures):
            t = futures[future]
            done += 1
            try:
                rows = future.result()
                if rows:
                    all_rows.extend(rows)
                    print(f"  [{done}/{len(tickers)}] {t}: {len(rows)} titik sinyal")
                else:
                    gagal.append(t)
                    print(f"  [{done}/{len(tickers)}] {t}: dilewati (data tidak cukup)")
            except Exception as e:
                gagal.append(t)
                print(f"  [{done}/{len(tickers)}] {t}: ERROR — {e}")

    elapsed = time.time() - t0
    print(f"\n✅ Selesai dalam {elapsed:.0f} detik. Total titik sinyal: {len(all_rows)}")
    if gagal:
        print(f"⚠️ {len(gagal)} ticker dilewati/gagal: {', '.join(gagal[:15])}")

    if not all_rows:
        print("❌ Tidak ada titik sinyal yang berhasil dihitung.")
        sys.exit(1)

    df_sinyal = pd.DataFrame(all_rows)
    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = f"_{args.tag}" if args.tag else ""
    mode_suffix = "_nonoverlap" if args.non_overlapping else "_overlap"
    path_out = os.path.join(args.output_dir, f"layer_audit_experiment_{ts}{tag}{mode_suffix}.csv")
    df_sinyal.to_csv(path_out, index=False)

    print(f"\n📁 File tersimpan: {path_out}")

    try:
        _quick_summary(df_sinyal, holding_days)
    except ImportError:
        print("ℹ️ scipy tidak terpasang — lewati ringkasan cepat korelasi (tidak masalah, cek manual dari CSV).")


if __name__ == "__main__":
    main()
