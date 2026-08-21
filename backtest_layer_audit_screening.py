"""
backtest_layer_audit_screening.py
===================================
Layer audit untuk sistem scoring SWING TRADING di modules/screening.py —
saudara dari backtest_layer_audit.py (yang mengaudit compute_score() di
modules/teknikal.py). Tujuannya sama: membongkar kontribusi POIN tiap
indikator individual dari scoring screening.py terhadap forward return riil,
bukan cuma skor totalnya.

⚠️ PERBEDAAN PENTING vs backtest_layer_audit.py (teknikal.py):
-----------------------------------------------------------------------------
compute_score() di teknikal.py adalah fungsi MURNI (df in -> dict out) yang
bisa langsung diimpor dan dipanggil apa adanya — backtest_layer_audit.py
tidak pernah menulis ulang logikanya.

process_single_stock() di screening.py TIDAK bisa diperlakukan sama karena:
  1. Scoring-nya menyatu dengan fetch data LIVE (get_full_stock_data,
     df_universe untuk Sektor/ROE/ROA/MarketCap) — bukan fungsi murni.
  2. Ada 2 mode (Day Trading interval 15m, Swing Trading interval 1d) dengan
     bobot & indikator yang beda total.
  3. Day Trading butuh fetch MTF terpisah (data daily tambahan).

Karena itu, fungsi `compute_score_swing_pure()` di bawah adalah HASIL SALIN
ULANG manual dari blok "SCORING: SWING TRADING" di process_single_stock()
(screening.py, per kondisi source saat script ini dibuat). Ini BUKAN import
langsung. Konsekuensinya:
  - Kalau screening.py diubah (bobot/threshold/logika baru), script audit
    ini HARUS disinkronkan ulang manual — tidak otomatis ikut berubah.
  - Sebelum mempercayai hasil audit ini, SPOT-CHECK dulu: jalankan modul
    Screening Swing Trading di aplikasi untuk 3-5 ticker, bandingkan skor &
    breakdown poinnya dengan output kolom 'Skor' + poin per indikator di
    CSV hasil script ini untuk tanggal candle terakhir. Kalau meleset,
    JANGAN lanjut ke analisis — perbaiki dulu fungsi di bawah.

CAKUPAN AUDIT INI (Swing Trading, interval 1d):
  Diskorkan (poin, ikut ditotal ke 'Skor'):
    - Supertrend (10,3) tier: fresh cross +20 / sustained +15 / else 0
    - MA Structure tier: Tier1 +20 / Tier2 +10 / else 0
    - MACD Golden Cross (5 candle) +7.5
    - MACD Histogram naik +7.5
    - RVOL tier: >=2.5 +15 / >=1.2 +10 / else 0
    - RSI(14) Momentum 45-70 +10
    - RSI(14) Trend 3 candle naik +10
    - PSAR bullish +5
    - VPT Trend (EMA10 slope) +5
    - Bonus MACD Early Recovery +10
    - Penalti RSI Overbought (>75) -15

  TIDAK diskorkan, hanya dicatat sebagai FLAG diagnostik (bukan gate):
    - OBV_ok   : OBV candle ini > rata-rata OBV 5 candle sebelumnya
                 (di aplikasi live, gagal = gugur/dibuang dari hasil)
    - CMF_ok   : CMF(20) > -0.15
                 (di aplikasi live, gagal = gugur/dibuang dari hasil)
    - MTF_ok   : Supertrend_Dir==1 DAN Close>EMA50
                 (di aplikasi live, dgn mtf_filter aktif, gagal = gugur)

  TIDAK diaudit sama sekali (butuh snapshot lintas-ticker/live data,
  tidak bisa direkonstruksi point-in-time per ticker):
    - Filter eligibility: Value_MA20, MarketCap, ROE, ROA (dari df_universe
      & yfinance info langsung, bukan historical time series)
    - Bonus "Sector Hot" +10 (post-processing, bergantung rata-rata skor
      SEMUA ticker di sektor yang sama pada hari yang sama)

CARA PAKAI (identik dengan backtest_layer_audit.py)
-----------------------------------------------------------------------------
    python backtest_layer_audit_screening.py --tickers BBCA,BBRI,BMRI,BBNI,BRIS \
        --years 5 --non-overlapping --tag batch1_bank

Output: outputs/layer_audit_screening_<timestamp><tag><mode_suffix>.csv
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
    from modules.screening import (
        calculate_indicators,
        compute_supertrend_score,
        compute_vpt_trend,
        compute_rsi_trend_3,
        drop_empty_candles,
    )
except ImportError:
    try:
        from screening import (
            calculate_indicators,
            compute_supertrend_score,
            compute_vpt_trend,
            compute_rsi_trend_3,
            drop_empty_candles,
        )
    except ImportError as e:
        print(
            "❌ Tidak bisa import dari modules/screening.py atau screening.py. "
            "Jalankan script ini dari root repo (folder yang sama dengan app.py).\n"
            f"Detail: {e}"
        )
        sys.exit(1)

try:
    from utils.data_loader import get_liquid_stocks
except ImportError:
    get_liquid_stocks = None

import yfinance as yf


# ─────────────────────────────────────────────────────────────────────────────
# FETCH HISTORI (identik dengan backtest_layer_audit.py / backtest_teknikal.py)
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# FLAG DIAGNOSTIK — OBV Divergence & CMF(20)
# Dihitung causal (rolling/cumsum hanya menengok ke belakang) atas SELURUH
# histori sekali di awal, sama seperti indikator lain — aman dari lookahead.
# ─────────────────────────────────────────────────────────────────────────────

def _add_prefilter_series(df: pd.DataFrame) -> pd.DataFrame:
    """Tambah kolom OBV_cum dan CMF20 ke df untuk flag diagnostik pre-filter."""
    df = df.copy()

    # OBV kumulatif (replika loop di process_single_stock, divektorisasi)
    close_diff = df["Close"].diff()
    direction = np.sign(close_diff).fillna(0)
    df["_OBV_cum"] = (direction * df["Volume"]).cumsum()

    # CMF(20) — identik dengan blok di process_single_stock
    hl = df["High"] - df["Low"]
    mfm = (
        ((df["Close"] - df["Low"]) - (df["High"] - df["Close"]))
        / hl.replace(0, np.nan)
    )
    df["_CMF20"] = (
        (mfm * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum()
    )

    return df


OBV_LOOKBACK = 5
CMF_THRESHOLD = -0.15


def _check_obv_ok(df: pd.DataFrame, i: int) -> bool:
    """True jika OBV[i] > rata-rata OBV (i-5..i-1) — replika pre-filter screening.py."""
    if i < OBV_LOOKBACK:
        return True  # data belum cukup, jangan gugurkan
    obv_ref_avg = float(df["_OBV_cum"].iloc[i - OBV_LOOKBACK:i].mean())
    return float(df["_OBV_cum"].iloc[i]) > obv_ref_avg


def _check_cmf_ok(df: pd.DataFrame, i: int) -> bool:
    val = df["_CMF20"].iloc[i]
    if pd.isna(val):
        return True
    return float(val) > CMF_THRESHOLD


# ─────────────────────────────────────────────────────────────────────────────
# SCORING SWING TRADING — SALINAN MANUAL dari process_single_stock()
# (lihat peringatan di docstring atas file ini)
# ─────────────────────────────────────────────────────────────────────────────

def compute_score_swing_pure(df: pd.DataFrame, i: int) -> dict:
    """
    Replika persis blok scoring Swing Trading di screening.process_single_stock().
    df harus sudah melalui calculate_indicators(df, "Swing Trading") DAN
    _add_prefilter_series(df). i = index posisi "hari ini" (0-based iloc).
    """
    last = df.iloc[i]
    curr_price = float(last["Close"])

    detail: dict = {}
    score = 0.0

    # 1. Supertrend (10,3) tier
    st_pts, _ = compute_supertrend_score(df, i, 20.0, 15.0)
    score += st_pts
    detail["Supertrend_poin"] = st_pts

    # 2. MA Structure tier
    ema20 = float(last["EMA20"])
    ema50 = float(last["EMA50"])
    ema200 = float(last["EMA200"])
    if curr_price > ema20 and ema20 > ema50 and ema50 > ema200:
        ma_pts = 20
    elif curr_price > ema50 and ema20 > ema50:
        ma_pts = 10
    else:
        ma_pts = 0
    score += ma_pts
    detail["MAStructure_poin"] = ma_pts

    # 3. MACD Golden Cross (dalam 5 candle terakhir)
    macd_gc_window = max(i - 4, 0)
    macd_gc = False
    for k in range(macd_gc_window, i + 1):
        if k == 0:
            continue
        if (df["MACD"].iloc[k] > df["MACD_Signal"].iloc[k]
                and df["MACD"].iloc[k - 1] <= df["MACD_Signal"].iloc[k - 1]):
            macd_gc = True
            break
    if not macd_gc and float(last["MACD"]) > float(last["MACD_Signal"]):
        macd_gc = True
    macd_gc_pts = 7.5 if macd_gc else 0.0
    score += macd_gc_pts
    detail["MACD_GC_poin"] = macd_gc_pts

    # 4. MACD Histogram naik
    if i >= 1:
        hist_now = float(df["MACD_Hist"].iloc[i])
        hist_prev = float(df["MACD_Hist"].iloc[i - 1])
        macd_hist_pts = 7.5 if hist_now > hist_prev else 0.0
    else:
        hist_now = float(df["MACD_Hist"].iloc[i])
        macd_hist_pts = 0.0
    score += macd_hist_pts
    detail["MACD_Hist_poin"] = macd_hist_pts

    # 5. RVOL tier
    vol_sma20 = df["Volume"].rolling(20).mean().iloc[i]
    rvol = float(last["Volume"]) / float(vol_sma20) if (vol_sma20 and vol_sma20 > 0) else 0.0
    if rvol >= 2.5:
        rvol_pts = 15
    elif rvol >= 1.2:
        rvol_pts = 10
    else:
        rvol_pts = 0
    score += rvol_pts
    detail["RVOL_poin"] = rvol_pts
    detail["RVOL_val"] = round(rvol, 3)

    # 6. RSI(14) Momentum 45-70
    rsi_val = float(last["RSI"])
    rsi_mom_pts = 10 if 45 <= rsi_val <= 70 else 0
    score += rsi_mom_pts
    detail["RSIMomentum_poin"] = rsi_mom_pts
    detail["RSI_val"] = round(rsi_val, 2)

    # 7. RSI(14) Trend: 3 candle consecutive naik
    rsi_trend_pts = 10 if compute_rsi_trend_3(df, "RSI", i) else 0
    score += rsi_trend_pts
    detail["RSITrend_poin"] = rsi_trend_pts

    # 8. PSAR bullish
    psar_pts = 5 if bool(last.get("PSAR_Bull", False)) else 0
    score += psar_pts
    detail["PSAR_poin"] = psar_pts

    # 9. VPT Trend (EMA slope)
    vpt_pts = 5 if compute_vpt_trend(df, i) else 0
    score += vpt_pts
    detail["VPT_poin"] = vpt_pts

    # Bonus: MACD Early Recovery
    macd_now = float(last["MACD"])
    sig_now = float(last["MACD_Signal"])
    recovery_pts = 10 if (i >= 1 and hist_now > 0 and macd_now < sig_now) else 0
    score += recovery_pts
    detail["MACDRecovery_poin"] = recovery_pts

    # Penalti: RSI Overbought (>75)
    ob_pts = -15 if rsi_val > 75 else 0
    score += ob_pts
    detail["RSIOB_penalty"] = ob_pts

    # Floor 0, cap 100 — identik dengan process_single_stock
    detail["Skor"] = min(max(round(score), 0), 100)
    detail["ATR_val"] = round(float(last["ATR"]), 4)

    # Flag diagnostik (bukan gate)
    detail["OBV_ok"] = _check_obv_ok(df, i)
    detail["CMF_ok"] = _check_cmf_ok(df, i)
    detail["MTF_ok"] = bool(df["Supertrend_Dir"].iloc[i] == 1 and curr_price > ema50)

    return detail


# ─────────────────────────────────────────────────────────────────────────────
# WALK-FORWARD UNTUK SATU TICKER
# ─────────────────────────────────────────────────────────────────────────────

def walk_forward_screening_single(
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

    df_raw = drop_empty_candles(df_raw)
    if df_raw.empty or len(df_raw) < (min_warmup + max(holding_days) + 5):
        return []

    try:
        df_ind = calculate_indicators(df_raw, "Swing Trading")
        df_ind = _add_prefilter_series(df_ind)
    except Exception as e:
        print(f"  ⚠️ Gagal hitung indikator {ticker}: {e}")
        return []

    n = len(df_ind)
    max_hold = max(holding_days)
    effective_step = max(sample_every, max_hold) if non_overlapping else max(1, sample_every)

    hasil = []
    idx_range = range(min_warmup, n - max_hold, effective_step)

    for i in idx_range:
        try:
            sc = compute_score_swing_pure(df_ind, i)
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
        row.update(sc)

        for h in holding_days:
            harga_fwd = float(df_ind["Close"].iloc[i + h])
            ret_pct = (harga_fwd - harga_entry) / harga_entry * 100
            low_window = df_ind["Low"].iloc[i + 1: i + h + 1]
            max_dd_pct = (
                ((low_window.min() - harga_entry) / harga_entry * 100)
                if not low_window.empty else np.nan
            )
            row[f"Return_{h}D_pct"] = round(ret_pct, 2)
            row[f"MaxDD_{h}D_pct"] = round(max_dd_pct, 2)

        hasil.append(row)

    return hasil


# ─────────────────────────────────────────────────────────────────────────────
# UNIVERSE
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Audit kontribusi per-indikator scoring Swing Trading screening.py vs forward return"
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
                         help="Label batch, mis. 'batch1_bank'. Disarankan selalu diisi.")
    args = parser.parse_args()

    holding_days = sorted(int(x.strip()) for x in args.holding_days.split(",") if x.strip())
    tickers = load_universe(args)
    max_hold = max(holding_days)

    if args.non_overlapping and args.sample_every < max_hold:
        print(f"ℹ️ --non-overlapping aktif: langkah sampling efektif = {max_hold} hari bursa.")

    print(f"📊 Layer audit SCREENING.PY (Swing Trading) | Universe: {len(tickers)} ticker | "
          f"Histori: {args.years} tahun | Holding: {holding_days} | "
          f"Mode: {'NON-OVERLAPPING' if args.non_overlapping else 'overlapping'}")
    print("🔄 Menjalankan (bisa beberapa menit)...\n")

    t0 = time.time()
    all_rows: list[dict] = []
    gagal: list[str] = []

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(
                walk_forward_screening_single, t, args.years, holding_days,
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
    path_out = os.path.join(args.output_dir, f"layer_audit_screening_{ts}{tag}{mode_suffix}.csv")
    df_sinyal.to_csv(path_out, index=False)

    print(f"\n📁 File tersimpan: {path_out}")
    print("💡 Setelah semua batch selesai, gabungkan dengan analyze_layer_audit_screening.py")


if __name__ == "__main__":
    main()
