"""
backtest_teknikal.py
=====================
Script riset OFFLINE (bukan bagian dari aplikasi Streamlit) untuk mengkalibrasi
threshold skor teknikal.py secara empiris, bukan dari asumsi.

TUJUAN
------
compute_score() di modules/teknikal.py memberi label STRONG BUY/BELI/dst
berdasarkan ambang skor (65/35/10/-9/-34/-64) yang dipilih heuristik, belum
divalidasi terhadap hasil riil. Script ini menjawab: "kalau skor >= 35
('BELI'), berapa persen kejadian itu benar-benar profit dalam 5/10/20 hari
ke depan?" — dengan cara walk-forward: hitung skor di setiap hari historis
memakai fungsi compute_score() ASLI dari aplikasi (bukan ditulis ulang),
lalu ukur return riil hari-hari setelahnya.

CARA PAKAI
----------
Jalankan dari root repo (folder yang berisi app.py, modules/, utils/):

    python backtest_teknikal.py --from-liquid --years 5 --holding-days 5,10,20
    python backtest_teknikal.py --tickers BBCA,BBRI,TLKM,ASII --years 3

Output:
    outputs/backtest_sinyal_<timestamp>.csv     -> detail tiap titik sinyal
    outputs/backtest_ringkasan_<timestamp>.csv  -> agregasi per bucket skor
    Ringkasan tercetak juga ke terminal.

KETERBATASAN (baca sebelum menyimpulkan)
-----------------------------------------
1. Hanya mem-backtest timeframe SWING (interval harian). Timeframe Day Trade
   (M15) tidak dibacktest di sini karena yfinance membatasi data intraday
   hanya 60 hari ke belakang — sample size-nya akan terlalu kecil untuk
   kalibrasi yang bermakna. Perlu sumber data intraday historis terpisah
   kalau mau backtest Day Trade dengan layak.
2. Return dihitung dari Close-to-Close forward N hari, TANPA simulasi
   stop-loss/take-profit intra-hari. Win rate riil trading plan (dengan SL/TP
   aktual dari render_trading_plan) akan berbeda — script ini mengukur
   "apakah arah & kekuatan skornya benar", bukan performa trading plan utuh.
3. Bias survivorship: ticker yang sudah delisting/suspend lama tidak akan
   muncul di liquid_stocks.csv saat ini, jadi historinya tidak ikut ter-cover.
4. compute_score() dipanggil ulang di window data yang tumbuh (expanding
   window) untuk tiap titik sampel — ini caranya paling akurat mencegah
   lookahead bias, tapi otomatis lebih lambat dibanding hitung sekali di
   seluruh data. Pakai --sample-every untuk mempercepat kalau perlu.
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

# ── Pastikan repo root ada di sys.path agar "modules." dan "utils." bisa di-import ──
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from modules.teknikal import calculate_technical_indicators, compute_score
except ImportError:
    try:
        # fallback kalau script dijalankan dari dalam folder modules/ atau file
        # teknikal.py belum dipindah ke modules/ (masih flat di root)
        from teknikal import calculate_technical_indicators, compute_score
    except ImportError as e:
        print(
            "❌ Tidak bisa import calculate_technical_indicators/compute_score dari "
            "modules/teknikal.py atau teknikal.py. Jalankan script ini dari root repo "
            "(folder yang sama dengan app.py), atau sesuaikan path import di atas.\n"
            f"Detail: {e}"
        )
        sys.exit(1)

try:
    from utils.data_loader import get_liquid_stocks
except ImportError:
    get_liquid_stocks = None  # --from-liquid tidak akan bisa dipakai, tapi --tickers tetap jalan

import yfinance as yf


# ─────────────────────────────────────────────────────────────────────────────
# LABEL BUCKET — sama persis dengan ambang di compute_score() saat ini,
# supaya hasil backtest bisa langsung menjawab "threshold sekarang masuk akal atau tidak"
# ─────────────────────────────────────────────────────────────────────────────

def _label_bucket(score: float, go_nogo: bool) -> str:
    if not go_nogo:
        return "KONDISI TIDAK IDEAL (veto)"
    if score >= 65:
        return "STRONG BUY (>=65)"
    elif score >= 35:
        return "BELI (35-64)"
    elif score >= 10:
        return "MASUK PANTAUAN (10-34)"
    elif score >= -9:
        return "NETRAL (-9..9)"
    elif score >= -34:
        return "HATI-HATI (-34..-10)"
    elif score >= -64:
        return "JUAL/HINDARI (-64..-35)"
    else:
        return "STRONG SELL (<-64)"


_LABEL_ORDER = [
    "STRONG SELL (<-64)", "JUAL/HINDARI (-64..-35)", "HATI-HATI (-34..-10)",
    "NETRAL (-9..9)", "MASUK PANTAUAN (10-34)", "BELI (35-64)",
    "STRONG BUY (>=65)", "KONDISI TIDAK IDEAL (veto)",
]


def _decile_bucket(score: float) -> str:
    """Bucket skor jadi rentang 10 poin, independen dari label, untuk kalibrasi lebih halus."""
    lo = int(np.floor(score / 10.0) * 10)
    hi = lo + 10
    return f"{lo:+d} s/d {hi:+d}"


# ─────────────────────────────────────────────────────────────────────────────
# FETCH DATA HISTORIS
# ─────────────────────────────────────────────────────────────────────────────

def fetch_history(ticker: str, years: int) -> pd.DataFrame:
    """
    Ambil histori harga harian langsung dari yfinance (bukan get_full_stock_data,
    karena itu dibatasi period='2y' untuk interval harian — kurang untuk backtest
    yang butuh sample lintas beberapa siklus market).
    """
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


# ─────────────────────────────────────────────────────────────────────────────
# WALK-FORWARD UNTUK SATU TICKER
# ─────────────────────────────────────────────────────────────────────────────

def walk_forward_single(
    ticker: str,
    years: int,
    holding_days: list[int],
    min_warmup: int,
    sample_every: int,
) -> list[dict]:
    """
    Hitung skor teknikal di tiap titik sampel historis (expanding window, tanpa
    lookahead), lalu catat forward return riil untuk tiap holding period.
    Return: list of dict, satu dict per titik sinyal.
    """
    df_raw = fetch_history(ticker, years)
    if df_raw.empty or len(df_raw) < (min_warmup + max(holding_days) + 5):
        return []

    # Indikator dihitung SEKALI di seluruh histori — aman dari lookahead karena
    # semua indikator di calculate_technical_indicators() bersifat causal
    # (rolling/ewm hanya menengok ke belakang), jadi nilainya di baris ke-i
    # identik dengan kalau dihitung ulang dari df.iloc[:i+1]. Ini murni untuk
    # efisiensi — bukan pintasan yang mengorbankan akurasi.
    try:
        df_ind = calculate_technical_indicators(df_raw)
    except Exception as e:
        print(f"  ⚠️ Gagal hitung indikator {ticker}: {e}")
        return []

    n = len(df_ind)
    max_hold = max(holding_days)
    hasil = []

    idx_range = range(min_warmup, n - max_hold, max(1, sample_every))

    for i in idx_range:
        window = df_ind.iloc[: i + 1]   # hanya data s.d. hari ke-i — tanpa lookahead
        try:
            sc = compute_score(window, timeframe="swing")
        except Exception:
            continue

        harga_entry = float(df_ind["Close"].iloc[i])
        tanggal     = df_ind.index[i]

        row = {
            "Ticker":      ticker.replace(".JK", ""),
            "Tanggal":     tanggal.strftime("%Y-%m-%d"),
            "Skor":        sc["score"],
            "Label":       _label_bucket(sc["score"], sc["go_nogo"]),
            "Decile":      _decile_bucket(sc["score"]),
            "GoNogo":      sc["go_nogo"],
            "HargaEntry":  harga_entry,
        }

        for h in holding_days:
            harga_fwd = float(df_ind["Close"].iloc[i + h])
            ret_pct = (harga_fwd - harga_entry) / harga_entry * 100

            # Max drawdown intraperiode (harga terendah relatif entry, sebelum
            # exit di hari ke-h) — proxy kasar risiko "seberapa dalam nyungsep
            # dulu sebelum forward return akhirnya tercapai"
            low_window = df_ind["Low"].iloc[i + 1 : i + h + 1]
            max_dd_pct = (
                ((low_window.min() - harga_entry) / harga_entry * 100)
                if not low_window.empty else np.nan
            )

            row[f"Return_{h}D_pct"] = round(ret_pct, 2)
            row[f"MaxDD_{h}D_pct"]  = round(max_dd_pct, 2)

        hasil.append(row)

    return hasil


# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSE
# ─────────────────────────────────────────────────────────────────────────────

def load_universe(args) -> list[str]:
    if args.tickers:
        tickers = [t.strip().upper().replace(".JK", "") + ".JK" for t in args.tickers.split(",") if t.strip()]
        return tickers

    if args.from_liquid:
        if get_liquid_stocks is None:
            print("❌ utils/data_loader.py tidak bisa di-import — pakai --tickers sebagai alternatif.")
            sys.exit(1)
        df = get_liquid_stocks()
        if df.empty:
            print("❌ liquid_stocks.csv kosong/tidak ditemukan — pakai --tickers sebagai alternatif.")
            sys.exit(1)
        col = "Ticker" if "Ticker" in df.columns else df.columns[0]
        tickers = [
            (t if t.endswith(".JK") else t + ".JK")
            for t in df[col].astype(str).str.strip().tolist()
        ]
        return tickers

    print("❌ Harus pilih salah satu: --tickers TICKER1,TICKER2,... atau --from-liquid")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# RINGKASAN PER BUCKET
# ─────────────────────────────────────────────────────────────────────────────

def summarize(df_sinyal: pd.DataFrame, holding_days: list[int], bucket_col: str, order: list[str] | None) -> pd.DataFrame:
    rows = []
    groups = df_sinyal.groupby(bucket_col)
    for bucket, g in groups:
        row = {"Bucket": bucket, "N_Sinyal": len(g), "N_Ticker": g["Ticker"].nunique()}
        for h in holding_days:
            ret_col = f"Return_{h}D_pct"
            dd_col  = f"MaxDD_{h}D_pct"
            row[f"WinRate_{h}D_%"]     = round((g[ret_col] > 0).mean() * 100, 1)
            row[f"WinRate2pct_{h}D_%"] = round((g[ret_col] >= 2.0).mean() * 100, 1)
            row[f"AvgReturn_{h}D_%"]   = round(g[ret_col].mean(), 2)
            row[f"MedianReturn_{h}D_%"] = round(g[ret_col].median(), 2)
            row[f"AvgMaxDD_{h}D_%"]    = round(g[dd_col].mean(), 2)
        rows.append(row)

    df_summary = pd.DataFrame(rows)
    if order is not None:
        df_summary["_order"] = df_summary["Bucket"].apply(lambda b: order.index(b) if b in order else -1)
        df_summary = df_summary.sort_values("_order").drop(columns="_order")
    else:
        df_summary = df_summary.sort_values("Bucket")
    return df_summary.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Backtest walk-forward untuk kalibrasi threshold skor teknikal.py"
    )
    parser.add_argument("--tickers", type=str, default=None,
                         help="Daftar ticker manual, pisah koma. Contoh: BBCA,BBRI,TLKM")
    parser.add_argument("--from-liquid", action="store_true",
                         help="Ambil universe dari liquid_stocks.csv via get_liquid_stocks()")
    parser.add_argument("--years", type=int, default=5,
                         help="Berapa tahun histori diambil per ticker (default: 5)")
    parser.add_argument("--holding-days", type=str, default="5,10,20",
                         help="Holding period dalam hari bursa, pisah koma (default: 5,10,20)")
    parser.add_argument("--min-warmup", type=int, default=250,
                         help="Minimum bar warmup sebelum mulai sampling (default: 250, agar EMA200/ADX stabil)")
    parser.add_argument("--sample-every", type=int, default=2,
                         help="Sampling tiap N hari bursa (default: 2, untuk mempercepat run tanpa kehilangan sinyal terlalu banyak)")
    parser.add_argument("--max-workers", type=int, default=6,
                         help="Jumlah thread paralel fetch+backtest per ticker (default: 6)")
    parser.add_argument("--output-dir", type=str, default="outputs",
                         help="Folder output CSV (default: outputs/)")
    args = parser.parse_args()

    holding_days = sorted(int(x.strip()) for x in args.holding_days.split(",") if x.strip())
    tickers = load_universe(args)

    print(f"📊 Universe: {len(tickers)} ticker | Histori: {args.years} tahun | "
          f"Holding: {holding_days} hari | Sample tiap {args.sample_every} hari")
    print("🔄 Menjalankan walk-forward backtest (bisa beberapa menit)...\n")

    t0 = time.time()
    all_rows: list[dict] = []
    gagal: list[str] = []

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(
                walk_forward_single, t, args.years, holding_days,
                args.min_warmup, args.sample_every,
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
        print(f"⚠️ {len(gagal)} ticker dilewati/gagal: {', '.join(gagal[:15])}"
              f"{' ...' if len(gagal) > 15 else ''}")

    if not all_rows:
        print("❌ Tidak ada titik sinyal yang berhasil dihitung. Cek koneksi/ticker/parameter.")
        sys.exit(1)

    df_sinyal = pd.DataFrame(all_rows)

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path_detail  = os.path.join(args.output_dir, f"backtest_sinyal_{ts}.csv")
    path_label   = os.path.join(args.output_dir, f"backtest_ringkasan_label_{ts}.csv")
    path_decile  = os.path.join(args.output_dir, f"backtest_ringkasan_decile_{ts}.csv")

    df_sinyal.to_csv(path_detail, index=False)

    df_label_summary = summarize(df_sinyal, holding_days, "Label", _LABEL_ORDER)
    df_label_summary.to_csv(path_label, index=False)

    df_decile_summary = summarize(df_sinyal, holding_days, "Decile", None)
    df_decile_summary.to_csv(path_decile, index=False)

    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)

    print("\n" + "=" * 80)
    print("RINGKASAN PER LABEL (bucket sesuai threshold compute_score() SAAT INI)")
    print("=" * 80)
    print(df_label_summary.to_string(index=False))

    print("\n" + "=" * 80)
    print("RINGKASAN PER DECILE SKOR (independen dari label, untuk cek kalibrasi halus)")
    print("=" * 80)
    print(df_decile_summary.to_string(index=False))

    print(f"\n📁 File tersimpan:")
    print(f"   - Detail per sinyal : {path_detail}")
    print(f"   - Ringkasan label   : {path_label}")
    print(f"   - Ringkasan decile  : {path_decile}")

    print(
        "\n💡 Cara baca: kalau target aplikasi win rate >50%, cek kolom WinRate_*D_%"
        " untuk tiap bucket. Kalau bucket 'BELI (35-64)' win rate-nya jauh di bawah 50%,"
        " threshold 35 terlalu longgar. Kalau bucket 'MASUK PANTAUAN (10-34)' win rate-nya"
        " sudah >50%, threshold 'BELI' saat ini mungkin terlalu ketat (skor 10-34 sudah"
        " cukup layak, tapi masih dilabeli 'pantau saja')."
    )


if __name__ == "__main__":
    main()
