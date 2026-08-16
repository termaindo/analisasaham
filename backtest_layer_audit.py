"""
backtest_layer_audit.py
========================
Script riset OFFLINE lanjutan dari backtest_teknikal.py. Bedanya: script ini
TIDAK cuma mencatat skor total, tapi membongkar kontribusi POIN tiap indikator
individual (EMA_Stack, Supertrend, BB_Mid, Parabolic SAR, MACD, RSI,
Stochastic, Volume Spike, Fibonacci, Bollinger Bands, Candlestick) dari
compute_score() di modules/teknikal.py, lalu mencatatnya bersisian dengan
forward return riil.

TUJUAN
------
Backtest skor total (backtest_teknikal.py) sudah menunjukkan korelasi
skor-vs-return mendekati nol (p > 0.4 di semua horizon, N=690 independen).
Itu TIDAK berarti semua indikator di dalamnya sama buruknya — bisa jadi
beberapa indikator justru berkorelasi baik, tapi kontribusinya "ditenggelamkan"
oleh indikator lain yang berkorelasi negatif atau nol, karena semua dijumlah
begitu saja dengan bobot W_* yang belum pernah divalidasi individual.

Script ini TIDAK mengubah compute_score() — hanya memanggilnya dan membaca
field "poin" yang SUDAH ADA di struktur dict hasilnya (result["layer2_trend"]
["EMA_Stack"]["poin"], dst). Jadi hasil totalnya, kalau dijumlah, akan sama
persis dengan skor yang dihasilkan backtest_teknikal.py — script ini murni
observasi tambahan, bukan logika baru.

CARA PAKAI (identik dengan backtest_teknikal.py, termasuk --non-overlapping)
-----------------------------------------------------------------------------
    python backtest_layer_audit.py --tickers BBCA,BBRI,BMRI,BBNI,BRIS \
        --years 5 --non-overlapping --tag batch1_bank

Output: outputs/layer_audit_<timestamp><tag>.csv
    Satu baris per titik sinyal, kolom:
    - Ticker, Tanggal, Skor (total, sama seperti backtest_teknikal.py)
    - Poin per indikator: EMA_Stack, Supertrend, BB_Mid, SAR, MACD, RSI,
      Stochastic, VolSpike, Fibonacci, BollingerBands, Candlestick
    - Nilai mentah beberapa indikator kunci: ADX_val, VolRatio_val, RSI_val,
      MACD_Hist_val, ATR_pct_val (untuk cek hubungan non-linear/tier)
    - Flag ADX_ok, Vol_ok (Layer 1)
    - Return_{h}D_pct, MaxDD_{h}D_pct untuk tiap holding period

Setelah semua batch selesai, gabungkan & analisis dengan analyze_layer_audit.py.
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


def _extract_layer_poin(sc: dict) -> dict:
    """Bongkar field 'poin' dari tiap indikator di hasil compute_score()."""
    l1 = sc.get("layer1_filter", {})
    l2 = sc.get("layer2_trend", {})
    l3 = sc.get("layer3_momentum", {})
    l4 = sc.get("layer4_entry", {})
    info = sc.get("info", {})

    return {
        # Layer 2 — Trend
        "EMA_Stack_poin":     l2.get("EMA_Stack", {}).get("poin", np.nan),
        "Supertrend_poin":    l2.get("Supertrend", {}).get("poin", np.nan),
        "BB_Mid_poin":        l2.get("BB_Mid", {}).get("poin", np.nan),
        "SAR_poin":           l2.get("Parabolic_SAR", {}).get("poin", np.nan),
        "Trend_Total":        l2.get("_total", np.nan),
        # Layer 3 — Momentum
        "MACD_poin":          l3.get("MACD", {}).get("poin", np.nan),
        "RSI_poin":           l3.get("RSI", {}).get("poin", np.nan),
        "Stochastic_poin":    l3.get("Stochastic", {}).get("poin", np.nan),
        "Momentum_Total":     l3.get("_total", np.nan),
        # Layer 4 — Entry Trigger
        "VolSpike_poin":      l4.get("Volume_Spike", {}).get("poin", np.nan),
        "Fibonacci_poin":     l4.get("Fibonacci", {}).get("poin", np.nan),
        "BollingerBands_poin": l4.get("Bollinger_Bands", {}).get("poin", np.nan),
        "Candlestick_poin":   l4.get("Candlestick", {}).get("poin", np.nan),
        "Entry_Total":        l4.get("_total", np.nan),
        # Layer 1 — Filter (flag, bukan poin)
        "ADX_ok":             l1.get("ADX", {}).get("ok", np.nan),
        "Vol_ok":             l1.get("Volume", {}).get("ok", np.nan),
        # Nilai mentah kunci (untuk cek hubungan non-linear/tier di luar poin diskrit)
        "ADX_val":            info.get("adx", np.nan),
        "VolRatio_val":       info.get("vol_ratio", np.nan),
        "RSI_val":            info.get("rsi", np.nan),
        "MACD_Hist_val":      info.get("macd_hist", np.nan),
        "ATR_pct_val":        info.get("atr_pct", np.nan),
    }


def walk_forward_layer_audit(
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
        window = df_ind.iloc[: i + 1]
        try:
            sc = compute_score(window, timeframe="swing")
        except Exception:
            continue

        harga_entry = float(df_ind["Close"].iloc[i])
        tanggal     = df_ind.index[i]

        row = {
            "Ticker":         ticker.replace(".JK", ""),
            "Tanggal":        tanggal.strftime("%Y-%m-%d"),
            "Skor":           sc["score"],
            "GoNogo":         sc["go_nogo"],
            "HargaEntry":     harga_entry,
            "NonOverlapping": non_overlapping,
        }
        row.update(_extract_layer_poin(sc))

        for h in holding_days:
            harga_fwd = float(df_ind["Close"].iloc[i + h])
            ret_pct = (harga_fwd - harga_entry) / harga_entry * 100
            low_window = df_ind["Low"].iloc[i + 1 : i + h + 1]
            max_dd_pct = (
                ((low_window.min() - harga_entry) / harga_entry * 100)
                if not low_window.empty else np.nan
            )
            row[f"Return_{h}D_pct"] = round(ret_pct, 2)
            row[f"MaxDD_{h}D_pct"]  = round(max_dd_pct, 2)

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


def main():
    parser = argparse.ArgumentParser(description="Audit kontribusi per-indikator compute_score() vs forward return")
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
                         help="Label batch, mis. 'batch1_bank'. Disarankan selalu diisi.")
    args = parser.parse_args()

    holding_days = sorted(int(x.strip()) for x in args.holding_days.split(",") if x.strip())
    tickers = load_universe(args)
    max_hold = max(holding_days)

    if args.non_overlapping and args.sample_every < max_hold:
        print(f"ℹ️ --non-overlapping aktif: langkah sampling efektif = {max_hold} hari bursa.")

    print(f"📊 Layer audit | Universe: {len(tickers)} ticker | Histori: {args.years} tahun | "
          f"Holding: {holding_days} | Mode: {'NON-OVERLAPPING' if args.non_overlapping else 'overlapping'}")
    print("🔄 Menjalankan (bisa beberapa menit)...\n")

    t0 = time.time()
    all_rows: list[dict] = []
    gagal: list[str] = []

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(
                walk_forward_layer_audit, t, args.years, holding_days,
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
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = f"_{args.tag}" if args.tag else ""
    mode_suffix = "_nonoverlap" if args.non_overlapping else "_overlap"
    path_out = os.path.join(args.output_dir, f"layer_audit_{ts}{tag}{mode_suffix}.csv")
    df_sinyal.to_csv(path_out, index=False)

    print(f"\n📁 File tersimpan: {path_out}")
    print("💡 Setelah semua batch selesai, gabungkan dengan analyze_layer_audit.py")


if __name__ == "__main__":
    main()
