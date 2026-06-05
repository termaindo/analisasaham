"""
screening.py
============
Modul Screening Day Trade & Swing Trade.

Universe saham: dibaca dari liquid_stocks.csv (prioritas) atau
pre_liquid_stocks.csv (fallback) via get_liquid_stocks().

Versi ini disesuaikan penuh dengan MODUL_SCREENING.md:
─────────────────────────────────────────────────────────
Pre-filter:
- OBV Divergence negatif = gugur mandiri
  (OBV[-1] <= rata-rata OBV 5 candle sebelumnya — lebih robust dari titik tunggal)
- CMF(20) <= -0.15 = gugur mandiri (diperlunak dari -0.1)

Day Trade scoring (interval 15m):
1. RVOL tier: >=2.5 -> 20 poin; >=1.2 -> 10 poin; <1.2 -> 0
2. Harga vs VWAP: Close > VWAP DAN VWAP[i] > VWAP[i-1] -> 20 poin
3. Supertrend (10,2) tier: fresh cross -> 20; sustained >3 (window 10 candle) -> 15; bearish -> 0
4. MACD Golden Cross (dalam 3 candle) -> 5 poin
5. MACD Histogram naik -> 5 poin
6. RSI(9) Momentum range 45-70 -> 7.5 poin
7. RSI(9) Trend: naik konsisten 3 candle berturut -> 7.5 poin
8. PSAR bullish -> 5 poin
9. VPT Trend: slope EMA(10) VPT positif >= 3 dari 5 candle terakhir -> 10 poin
MTF Bonus: daily MA check (+10/+5/-15)
Bonus Sektor Hot: +10 (post-processing)

Swing Trade scoring (interval 1d):
1. Supertrend (10,3) tier: fresh cross -> 20; sustained >3 (window 10 candle) -> 15; bearish -> 0
2. MA Structure: Close>EMA20>EMA50>EMA200 -> 20; Close>EMA50 & EMA20>EMA50 -> 10; else -> 0
3. MACD Golden Cross (dalam 5 candle) -> 7.5 poin
4. MACD Histogram naik -> 7.5 poin
5. RVOL tier: >=2.5 -> 15; >=1.2 -> 10; <1.2 -> 0
6. RSI(14) Momentum range 45-70 -> 10 poin
7. RSI(14) Trend: naik konsisten 3 candle berturut -> 10 poin
8. PSAR bullish -> 5 poin
9. VPT Trend: slope EMA(10) VPT positif >= 3 dari 5 candle terakhir -> 5 poin
Bonus MACD Early Recovery: Hist > 0 tapi MACD < Signal -> +10
Penalti RSI Overbought (>75): -15
Bonus Sektor Hot: +10 (post-processing)

Stale warning: >= 2 hari.
"""

import streamlit as st
import pandas as pd
import numpy as np
import pytz
import os
import holidays
import plotly.express as px
import concurrent.futures
from datetime import datetime
from fpdf import FPDF

from utils.data_loader import (
    get_full_stock_data,
    get_liquid_stocks,
    get_value_ma20,
    is_ticker_liquid,
    get_ticker_row,
    PRE_LIQUID_PATH,
    LIQUID_PATH,
)

# -----------------------------------------------------------------------------
# KONSTANTA
# -----------------------------------------------------------------------------

RSI_PERIOD_DAY      = 9
RSI_PERIOD_SWING    = 14
RSI_OVERBOUGHT      = 75
RSI_MOM_LOW         = 45
RSI_MOM_HIGH        = 70

MACD_FAST           = 12
MACD_SLOW           = 26
MACD_SIGNAL_PERIOD  = 9

EMA_SHORT           = 20
EMA_MID             = 50
EMA_LONG            = 200

RVOL_HIGH           = 2.5
RVOL_MID            = 1.2

MC_MIN_IDR          = 500_000_000_000
USD_TO_IDR          = 16_000
MC_MIN_USD          = MC_MIN_IDR / USD_TO_IDR

# Pre-filter thresholds (diperlunak agar tidak terlalu agresif saat pasar koreksi)
CMF_THRESHOLD       = -0.15   # semula -0.1
OBV_LOOKBACK        = 5       # jumlah candle untuk rata-rata OBV referensi

SL_MULT_DAY         = 1.8
SL_MULT_SWING       = 2.5
MAX_LOSS_PCT_DAY    = 0.03
MAX_LOSS_PCT_SWING  = 0.08
RR_MIN_DAY          = 1.5
RR_MIN_SWING        = 2.0
MAX_ALLOC_PCT       = 0.15

SCORE_MIN_ENTRY     = 70
RRR_MIN_ENTRY       = 1.4
SECTOR_HOT_THRESHOLD = 70

# Window untuk deteksi candles_above Supertrend (Sustained vs Fresh Cross)
ST_SUSTAINED_WINDOW = 10   # semula 4 (sama dengan window fresh-cross), sekarang dipisah

_TZ_WIB = pytz.timezone("Asia/Jakarta")


# -----------------------------------------------------------------------------
# LOAD UNIVERSE
# -----------------------------------------------------------------------------

# Threshold filter universe trading — harus konsisten dengan admin_panel.py profil "trading"
_TRADING_MIN_VALUE_MA20 = 2_000_000_000
_TRADING_MIN_ROE        = 10.0


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def load_universe() -> tuple[list[str], pd.DataFrame]:
    """
    Muat universe saham dari liquid_stocks.csv (prioritas) atau
    pre_liquid_stocks.csv (fallback).
    Return: (saham_list, df_universe)
    """
    df_liquid = get_liquid_stocks()
    if not df_liquid.empty:
        df = _normalize_universe_columns(df_liquid)

        # Filter trading: hanya ticker dengan Value_MA20 >= 2M dan ROE >= 10%.
        # Dilakukan di sini (bukan di process_single_stock) agar saham profil
        # dividen yang lolos threshold lebih rendah tidak masuk antrian API call.
        # Filter hanya aktif jika kolom tersedia — agar tidak crash saat
        # liquid_stocks.csv belum di-enrich ulang.
        if "Value_MA20" in df.columns:
            df = df[
                df["Value_MA20"].notna() &
                (pd.to_numeric(df["Value_MA20"], errors="coerce") >= _TRADING_MIN_VALUE_MA20)
            ]
        if "ROE" in df.columns:
            df = df[
                df["ROE"].notna() &
                (pd.to_numeric(df["ROE"], errors="coerce") >= _TRADING_MIN_ROE)
            ]

        saham_list = [
            (t if t.endswith(".JK") else t + ".JK")
            for t in df["Kode Saham"].astype(str).str.strip().tolist()
        ]
        return saham_list, df

    try:
        df = pd.read_csv(PRE_LIQUID_PATH, sep=None, engine="python")
        df = _normalize_universe_columns(df)
        saham_list = [
            (t if t.endswith(".JK") else t + ".JK")
            for t in df["Kode Saham"].astype(str).str.strip().tolist()
        ]
        st.sidebar.warning(
            "liquid_stocks.csv belum tersedia. "
            "Menggunakan pre_liquid_stocks.csv sebagai fallback — "
            "data enrichment (Value_MA20, ROE, dll) tidak tersedia."
        )
        return saham_list, df
    except FileNotFoundError:
        st.error(f"File universe tidak ditemukan: {PRE_LIQUID_PATH}")
        return [], pd.DataFrame()
    except Exception as e:
        st.error(f"Gagal membaca universe saham: {e}")
        return [], pd.DataFrame()


def clear_load_universe_cache() -> None:
    """
    Clear cache load_universe().
    Dipanggil dari admin_panel.py setelah admin upload liquid_stocks.csv baru ke GitHub
    dan menekan tombol 'Clear cache' — agar screening langsung membaca file terbaru
    tanpa harus menunggu TTL 24 jam habis.
    """
    load_universe.clear()


def _normalize_universe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalisasi nama kolom DataFrame universe ke standar liquid_stocks.csv."""
    df = df.copy()
    df.columns = df.columns.str.strip()
    rename_map: dict = {}
    for col in df.columns:
        c = col.lower().strip().lstrip("\ufeff")
        if c in ("ticker", "kode saham", "kode", "saham"):
            rename_map[col] = "Kode Saham"
        elif c in ("sektor", "sector"):
            rename_map[col] = "Sektor"
        elif c == "syariah":
            rename_map[col] = "Syariah"
        elif c in ("mktcap", "mkt cap", "mkt_cap", "market cap", "market_cap"):
            rename_map[col] = "MktCap"
        elif c.startswith("roe"):
            rename_map[col] = "ROE"
        elif c.startswith("roa"):
            rename_map[col] = "ROA"
        elif c.startswith("npm") or "profit margin" in c:
            rename_map[col] = "NPM"
        elif "value_ma20" in c or "value ma20" in c:
            rename_map[col] = "Value_MA20"
        elif "median_per_3y" in c or "median per 3y" in c:
            rename_map[col] = "Median_PER_3Y"
        elif "median_pbv_3y" in c or "median pbv 3y" in c:
            rename_map[col] = "Median_PBV_3Y"
    df = df.rename(columns=rename_map)
    if "Kode Saham" in df.columns:
        df["Kode Saham"] = (
            df["Kode Saham"].astype(str).str.strip().str.replace(".JK", "", regex=False)
        )
    return df


# -----------------------------------------------------------------------------
# LOOKUP HELPERS
# -----------------------------------------------------------------------------

def get_sector_from_universe(ticker_bersih: str, df_universe: pd.DataFrame) -> str:
    """Ambil nama sektor ticker dari df_universe."""
    if df_universe.empty or "Sektor" not in df_universe.columns:
        return "Lainnya"
    mask = df_universe["Kode Saham"].astype(str).str.strip() == ticker_bersih
    rows = df_universe[mask]
    return rows.iloc[0]["Sektor"] if not rows.empty else "Lainnya"


def is_syariah_from_universe(ticker_bersih: str, df_universe: pd.DataFrame) -> bool:
    """Cek apakah ticker masuk daftar saham syariah."""
    if df_universe.empty or "Syariah" not in df_universe.columns:
        return False
    mask = df_universe["Kode Saham"].astype(str).str.strip() == ticker_bersih
    rows = df_universe[mask]
    if rows.empty:
        return False
    return str(rows.iloc[0]["Syariah"]).strip().lower() in ("ya", "yes", "true", "1")


def get_fundamental_from_universe(ticker_bersih: str, df_universe: pd.DataFrame) -> dict:
    """Ambil ROE, ROA, NPM, Value_MA20 dari df_universe jika tersedia."""
    result = {
        "ROE": None, "ROA": None, "NPM": None, "Value_MA20": None,
        "Median_PER_3Y": None, "Median_PBV_3Y": None,
    }
    if df_universe.empty:
        return result
    mask = df_universe["Kode Saham"].astype(str).str.strip() == ticker_bersih
    rows = df_universe[mask]
    if rows.empty:
        return result
    row = rows.iloc[0]
    for key in ("ROE", "ROA", "NPM"):
        if key in row.index:
            try:
                val = str(row[key]).replace("%", "").replace(",", ".").strip()
                result[key] = float(val)
            except Exception:
                pass
    for key in ("Value_MA20", "Median_PER_3Y", "Median_PBV_3Y"):
        if key in row.index:
            try:
                result[key] = float(row[key])
            except Exception:
                pass
    return result


# -----------------------------------------------------------------------------
# FORMAT RUPIAH
# -----------------------------------------------------------------------------

def format_rp(angka) -> str:
    """Format angka ke string Rupiah dengan pemisah ribuan titik."""
    if isinstance(angka, str):
        return angka
    try:
        return f"{int(angka):,}".replace(",", ".")
    except Exception:
        return str(angka)


# -----------------------------------------------------------------------------
# HELPER PDF: SANITASI STRING NON-LATIN-1
# -----------------------------------------------------------------------------

_LATIN1_MAP = {
    "\u2013": "-",    # en-dash
    "\u2014": "-",    # em-dash
    "\u2192": "->",   # arrow kanan
    "\u2190": "<-",   # arrow kiri
    "\u2191": "^",    # arrow atas
    "\u2193": "v",    # arrow bawah
    "\u2018": "'",    # left single quote
    "\u2019": "'",    # right single quote
    "\u201c": '"',    # left double quote
    "\u201d": '"',    # right double quote
    "\u2026": "...",  # ellipsis
    "\u00d7": "x",    # multiplication sign
    "\u00b0": " deg", # degree sign
}

def _safe_latin1(text: str) -> str:
    """
    Sanitasi string agar aman untuk FPDF (latin-1).
    Ganti karakter Unicode umum ke ASCII, lalu strip sisanya.
    """
    for char, repl in _LATIN1_MAP.items():
        text = text.replace(char, repl)
    return text.encode("latin-1", "ignore").decode("latin-1")


# -----------------------------------------------------------------------------
# AUDIO ALERT
# -----------------------------------------------------------------------------

def play_alert_sound() -> None:
    """Putar suara notifikasi saat ada sinyal kuat (skor >= 85)."""
    audio_html = """
    <audio autoplay>
      <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3"
              type="audio/mpeg">
    </audio>
    """
    st.components.v1.html(audio_html, height=0)


# -----------------------------------------------------------------------------
# ANALISA ROTASI SEKTOR
# -----------------------------------------------------------------------------

def analyze_sector_momentum(full_results_df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    """
    Hitung rata-rata skor per sektor dari seluruh ticker yang lolos pre-filter.
    Sektor dengan Avg_Score >= 70 ditetapkan sebagai leading_sectors (Sector Hot).
    """
    if full_results_df.empty:
        return pd.DataFrame(), []
    sector_summary = (
        full_results_df.groupby("Sektor")
        .agg({"Skor": "mean", "Ticker": "count"})
        .rename(columns={"Ticker": "Jumlah_Saham", "Skor": "Avg_Score"})
        .sort_values("Avg_Score", ascending=False)
    )
    leading_sectors = sector_summary[
        sector_summary["Avg_Score"] >= SECTOR_HOT_THRESHOLD
    ].index.tolist()
    return sector_summary, leading_sectors


# -----------------------------------------------------------------------------
# GENERATOR PDF
# -----------------------------------------------------------------------------

def export_to_pdf(
    hasil_lolos: list,
    trade_mode: str,
    session: str,
    sector_report: pd.DataFrame,
    logo_path: str = "assets/logo_expert_stock_pro.png",
) -> bytes:
    """Generate laporan PDF dari hasil screening."""
    pdf = FPDF()
    pdf.add_page()

    pdf.set_fill_color(20, 20, 20)
    pdf.rect(0, 0, 210, 25, "F")
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=10, y=3, w=18, h=18)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 16)
    pdf.set_xy(35, 8)
    pdf.cell(0, 10, _safe_latin1("Expert Stock Pro - Screening Saham Harian Pro"), ln=True)
    pdf.set_y(28)
    pdf.set_font("Arial", "I", 10)
    pdf.set_text_color(0, 0, 255)
    pdf.cell(0, 5, "Sumber: https://s.id/pintarsaham", ln=True, align="C",
             link="https://s.id/pintarsaham")
    pdf.ln(3)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 8, _safe_latin1(f"Strategi: {trade_mode} | Sesi: {session}"), ln=True, align="C")
    waktu_cetak = datetime.now(_TZ_WIB).strftime("%d-%m-%Y %H:%M WIB")
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 5, _safe_latin1(f"Dicetak: {waktu_cetak}"), ln=True, align="R")
    pdf.ln(2)

    if not sector_report.empty:
        pdf.set_fill_color(220, 235, 255)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(190, 7, "  MARKET OVERVIEW (SEKTOR TERKUAT HARI INI)", 0, ln=True, fill=True)
        pdf.set_font("Arial", "", 9)
        top_sectors = ", ".join(sector_report.index[:3].tolist())
        pdf.multi_cell(190, 6, _safe_latin1(f" Aliran dana terbesar: {top_sectors}"))
        pdf.ln(3)

    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(190, 8, "A. TOP 3 PRIORITAS TRANSAKSI", 0, ln=True, fill=True)
    pdf.ln(2)

    for item in hasil_lolos[:3]:
        pdf.set_font("Arial", "B", 10)
        pdf.cell(
            190, 6,
            _safe_latin1(
                f"{item['Ticker']} - {item['Sektor']} | Syariah: {item['Syariah']} | "
                f"Quality: {item['Quality']} | Score: {item['Skor']}/100"
            ),
            ln=True,
        )
        pdf.set_font("Arial", "", 9)
        pdf.cell(60, 5, _safe_latin1(f"Entry: {item['Entry']}"), 0)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(65, 5, _safe_latin1(f"TP Target: Rp {format_rp(item['TP'])} ({item['Pct_Reward']})"), 0)
        pdf.set_text_color(200, 0, 0)
        pdf.cell(65, 5, _safe_latin1(f"Stop Loss: Rp {format_rp(item['SL'])} ({item['Pct_Risk']})"), ln=True)
        pdf.set_text_color(0, 0, 0)
        status_pdf = _safe_latin1(
            item["Status"].replace("\U0001f525", "").replace("\U0001f3af", "").strip()
        )
        pdf.set_font("Arial", "B", 8)
        pdf.cell(190, 5, _safe_latin1(f"Batas Alokasi Maksimal: {item['Lot_Maks']} ({status_pdf})"), ln=True)
        pdf.set_font("Arial", "I", 8)
        pdf.multi_cell(190, 4, _safe_latin1(f"Logic: {item['Logic']}"))
        pdf.ln(2)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(2)

    watchlist = hasil_lolos[3:10]
    if watchlist:
        pdf.ln(3)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(190, 8, "B. RADAR WATCHLIST (RANK 4-10)", 0, ln=True, fill=True)
        pdf.ln(2)
        for w in watchlist:
            pdf.set_font("Arial", "B", 9)
            pdf.cell(
                190, 5,
                _safe_latin1(
                    f"{w['Ticker']} ({w['Sektor'][:20]}) | Syariah: {w['Syariah']} | "
                    f"Quality: {w['Quality']} | Skor: {w['Skor']}"
                ),
                ln=True,
            )
            pdf.set_font("Arial", "", 8)
            pdf.cell(40, 5, _safe_latin1(f"Entry: {w['Entry']}"), 0)
            pdf.set_text_color(0, 128, 0)
            pdf.cell(50, 5, _safe_latin1(f"TP: Rp {format_rp(w['TP'])} ({w['Pct_Reward']})"), 0)
            pdf.set_text_color(200, 0, 0)
            pdf.cell(50, 5, _safe_latin1(f"SL: Rp {format_rp(w['SL'])} ({w['Pct_Risk']})"), 0)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(50, 5, _safe_latin1(f"Maks: {w['Lot_Maks']}"), ln=True)
            pdf.set_font("Arial", "I", 7)
            pdf.multi_cell(190, 4, _safe_latin1(f"Logic: {w['Logic']}"))
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(190, 5, "DISCLAIMER:", ln=True)
    pdf.set_font("Arial", "I", 7)
    pdf.multi_cell(
        190, 4,
        "Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma "
        "indikator teknikal dan fundamental. Bukan merupakan ajakan, rekomendasi pasti, atau "
        "paksaan untuk membeli/menjual saham. Keputusan investasi sepenuhnya menjadi tanggung "
        "jawab pribadi investor. Selalu terapkan manajemen risiko yang baik dan DYOR.",
    )
    return pdf.output(dest="S").encode("latin-1", "ignore")


# -----------------------------------------------------------------------------
# HELPER: HAPUS CANDLE KOSONG
# -----------------------------------------------------------------------------

def drop_empty_candles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Hapus baris dengan Close <= 0, Volume <= 0, atau salah satunya NaN.
    Dipanggil untuk semua interval SEBELUM calculate_indicators().
    """
    mask = (
        df["Close"].notna() & (df["Close"] > 0) &
        df["Volume"].notna() & (df["Volume"] > 0)
    )
    return df[mask].copy()


# -----------------------------------------------------------------------------
# HELPER: CARI VALID ILOC
# -----------------------------------------------------------------------------

def find_valid_last_iloc(
    df: pd.DataFrame,
    indicator_cols: list[str] | None = None,
) -> int | None:
    """Scan mundur; kembalikan iloc candle terakhir yang valid dan sudah warm-up."""
    if indicator_cols is None:
        indicator_cols = []
    for i in range(len(df) - 1, -1, -1):
        row = df.iloc[i]
        if row["Close"] <= 0 or row["Volume"] <= 0:
            continue
        if any(pd.isna(row.get(col, np.nan)) for col in indicator_cols):
            continue
        return i
    return None


def find_valid_prev_iloc(
    df: pd.DataFrame,
    from_iloc: int,
    indicator_cols: list[str] | None = None,
) -> int:
    """Scan mundur dari from_iloc - 1; kembalikan iloc candle valid sebelumnya."""
    if indicator_cols is None:
        indicator_cols = []
    for i in range(from_iloc - 1, -1, -1):
        row = df.iloc[i]
        if row["Close"] <= 0 or row["Volume"] <= 0:
            continue
        if any(pd.isna(row.get(col, np.nan)) for col in indicator_cols):
            continue
        return i
    return from_iloc


# -----------------------------------------------------------------------------
# HELPER: HITUNG STALE DAYS
# -----------------------------------------------------------------------------

def compute_stale_days(df: pd.DataFrame, valid_iloc: int, interval: str) -> int:
    """Hitung berapa hari kalender candle valid terakhir tertinggal dari hari ini (WIB)."""
    try:
        candle_ts = df.index[valid_iloc]
        if candle_ts.tzinfo is None:
            candle_ts = candle_ts.tz_localize("UTC").tz_convert(_TZ_WIB)
        else:
            candle_ts = candle_ts.tz_convert(_TZ_WIB)
        today_wib  = pd.Timestamp.now(tz=_TZ_WIB)
        delta_days = (today_wib.normalize() - candle_ts.normalize()).days
        return max(delta_days, 0)
    except Exception:
        return 0


# -----------------------------------------------------------------------------
# KALKULASI VPT TREND (EMA slope)
# -----------------------------------------------------------------------------

def compute_vpt_trend(df: pd.DataFrame, valid_iloc: int) -> bool:
    """
    Hitung VPT Trend sesuai spesifikasi:
      VPT[i] = VPT[i-1] + Volume[i] * (Close[i] - Close[i-1]) / Close[i-1]
      EMA_VPT = EMA(10) dari series VPT
      slope[i] = EMA_VPT[i] - EMA_VPT[i-1]
      VPT_Trend = True jika >= 3 dari 5 slope terakhir positif.
    """
    try:
        vpt = (df["Close"].pct_change() * df["Volume"]).cumsum()
        ema_vpt = vpt.ewm(span=10, adjust=False).mean()
        slope = ema_vpt.diff()
        # Ambil 5 slope terakhir s.d. valid_iloc
        start = max(valid_iloc - 4, 1)
        recent_slopes = slope.iloc[start : valid_iloc + 1]
        return int((recent_slopes > 0).sum()) >= 3
    except Exception:
        return False


# -----------------------------------------------------------------------------
# KALKULASI RSI TREND (3 CANDLE CONSECUTIVE)
# -----------------------------------------------------------------------------

def compute_rsi_trend_3(df: pd.DataFrame, rsi_col: str, valid_iloc: int) -> bool:
    """
    Return True jika RSI naik di setiap candle selama 3 candle terakhir
    (slope positif konsisten): RSI[i-2] < RSI[i-1] < RSI[i].
    """
    try:
        if valid_iloc < 2:
            return False
        r0 = df[rsi_col].iloc[valid_iloc - 2]
        r1 = df[rsi_col].iloc[valid_iloc - 1]
        r2 = df[rsi_col].iloc[valid_iloc]
        return bool(r0 < r1 < r2)
    except Exception:
        return False


# -----------------------------------------------------------------------------
# HELPER: SUPERTREND TIER
# -----------------------------------------------------------------------------

def compute_supertrend_score(
    df: pd.DataFrame,
    valid_iloc: int,
    score_fresh: float,
    score_sustained: float,
) -> tuple[float, str]:
    """
    Hitung skor Supertrend tier dan alasan teksnya.

    Logika:
    - Fresh cross: window 4 candle (valid_iloc-3 s.d. valid_iloc).
      Bullish saat ini DAN ada candle bearish di window tersebut -> fresh cross.
    - Sustained bullish: window ST_SUSTAINED_WINDOW candle.
      Bullish saat ini, tidak ada fresh cross, dan candles_above > 3 di window lebar.
    - Bearish / tidak memenuhi: 0 poin.

    Return: (poin, alasan_string)
    """
    if int(df["Supertrend_Dir"].iloc[valid_iloc]) != 1:
        return 0.0, ""

    # Deteksi fresh cross: window sempit 4 candle
    fc_start  = max(valid_iloc - 3, 0)
    fc_series = df["Supertrend_Dir"].iloc[fc_start : valid_iloc + 1]
    is_fresh  = bool((fc_series == -1).any())

    if is_fresh:
        return score_fresh, f"Supertrend Fresh Cross Bullish +{int(score_fresh)}"

    # Deteksi sustained: window lebar ST_SUSTAINED_WINDOW candle
    sw_start      = max(valid_iloc - (ST_SUSTAINED_WINDOW - 1), 0)
    sw_series     = df["Supertrend_Dir"].iloc[sw_start : valid_iloc + 1]
    candles_above = int((sw_series == 1).sum())
    if candles_above > 3:
        return score_sustained, f"Supertrend Sustained Bullish +{int(score_sustained)}"

    return 0.0, ""


# -----------------------------------------------------------------------------
# KALKULASI SUPERTREND
# -----------------------------------------------------------------------------

def calculate_supertrend(
    df: pd.DataFrame, period: int = 10, multiplier: float = 2.0
) -> pd.DataFrame:
    """Hitung Supertrend; tambahkan kolom Supertrend + Supertrend_Dir ke df."""
    hl2        = (df["High"] + df["Low"]) / 2
    high_low   = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close  = np.abs(df["Low"]  - df["Close"].shift())
    tr         = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr        = tr.rolling(period).mean()

    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)
    supertrend = pd.Series(index=df.index, dtype=float)
    direction  = pd.Series(index=df.index, dtype=int)

    for i in range(1, len(df)):
        if df["Close"].iloc[i] > upper_band.iloc[i - 1]:
            direction.iloc[i] = 1
        elif df["Close"].iloc[i] < lower_band.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
            if direction.iloc[i] == 1 and lower_band.iloc[i] < lower_band.iloc[i - 1]:
                lower_band.iloc[i] = lower_band.iloc[i - 1]
            if direction.iloc[i] == -1 and upper_band.iloc[i] > upper_band.iloc[i - 1]:
                upper_band.iloc[i] = upper_band.iloc[i - 1]
        supertrend.iloc[i] = (
            lower_band.iloc[i] if direction.iloc[i] == 1 else upper_band.iloc[i]
        )

    df = df.copy()
    df["Supertrend"]     = supertrend
    df["Supertrend_Dir"] = direction
    return df


# -----------------------------------------------------------------------------
# KALKULASI PSAR
# -----------------------------------------------------------------------------

def calculate_psar(
    df: pd.DataFrame,
    af_start: float = 0.02,
    af_step: float  = 0.02,
    af_max: float   = 0.2,
) -> pd.DataFrame:
    """Hitung Parabolic SAR; tambahkan kolom PSAR + PSAR_Bull ke df."""
    high  = df["High"].values
    low   = df["Low"].values
    close = df["Close"].values
    n     = len(df)
    psar  = close.copy()
    bull  = True
    af    = af_start
    hp    = high[0]
    lp    = low[0]

    for i in range(2, n):
        if bull:
            psar[i] = psar[i - 1] + af * (hp - psar[i - 1])
            psar[i] = min(psar[i], low[i - 1], low[max(0, i - 2)])
            if low[i] < psar[i]:
                bull    = False
                psar[i] = hp
                lp      = low[i]
                af      = af_start
            else:
                if high[i] > hp:
                    hp = high[i]
                    af = min(af + af_step, af_max)
        else:
            psar[i] = psar[i - 1] + af * (lp - psar[i - 1])
            psar[i] = max(psar[i], high[i - 1], high[max(0, i - 2)])
            if high[i] > psar[i]:
                bull    = True
                psar[i] = lp
                hp      = high[i]
                af      = af_start
            else:
                if low[i] < lp:
                    lp = low[i]
                    af = min(af + af_step, af_max)

    df = df.copy()
    df["PSAR"]      = psar
    df["PSAR_Bull"] = df["Close"] > df["PSAR"]
    return df


# -----------------------------------------------------------------------------
# KALKULASI INDIKATOR TEKNIKAL
# -----------------------------------------------------------------------------

def calculate_indicators(df: pd.DataFrame, trade_mode: str) -> pd.DataFrame:
    """
    Hitung semua indikator teknikal sesuai mode trading.
    df harus sudah melalui drop_empty_candles() terlebih dahulu.
    """
    df = df.copy()

    # ATR
    high_low   = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close  = np.abs(df["Low"]  - df["Close"].shift())
    df["ATR"]  = (
        pd.concat([high_low, high_close, low_close], axis=1)
        .max(axis=1)
        .rolling(14)
        .mean()
    )

    # MACD
    ema12             = df["Close"].ewm(span=MACD_FAST,          adjust=False).mean()
    ema26             = df["Close"].ewm(span=MACD_SLOW,          adjust=False).mean()
    df["MACD"]        = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=MACD_SIGNAL_PERIOD, adjust=False).mean()
    df["MACD_Hist"]   = df["MACD"] - df["MACD_Signal"]

    if trade_mode == "Day Trading":
        # Supertrend (10, 2)
        df = calculate_supertrend(df, period=10, multiplier=2.0)
        # VWAP rolling 5 candle (intraday proxy)
        df["VWAP"] = (
            (df["Close"] * df["Volume"]).rolling(5).sum()
            / df["Volume"].rolling(5).sum()
        )
        # RSI periode 9
        delta     = df["Close"].diff()
        gain      = delta.where(delta > 0, 0).rolling(RSI_PERIOD_DAY).mean()
        loss      = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD_DAY).mean()
        df["RSI"] = 100 - (100 / (1 + (gain / loss)))
        df = calculate_psar(df)

    else:  # Swing Trading
        # Supertrend (10, 3)
        df = calculate_supertrend(df, period=10, multiplier=3.0)
        # EMA 20, 50, 200
        df["EMA20"]  = df["Close"].ewm(span=EMA_SHORT, adjust=False).mean()
        df["EMA50"]  = df["Close"].ewm(span=EMA_MID,   adjust=False).mean()
        df["EMA200"] = df["Close"].ewm(span=EMA_LONG,  adjust=False).mean()
        # RSI periode 14
        delta     = df["Close"].diff()
        gain      = delta.where(delta > 0, 0).rolling(RSI_PERIOD_SWING).mean()
        loss      = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD_SWING).mean()
        df["RSI"] = 100 - (100 / (1 + (gain / loss)))
        df = calculate_psar(df)

    return df


# -----------------------------------------------------------------------------
# MARKET SESSION
# -----------------------------------------------------------------------------

def get_market_session() -> tuple[str, str]:
    """Return (label_sesi, deskripsi_status) berdasarkan waktu WIB saat ini."""
    now = datetime.now(_TZ_WIB)
    if now.weekday() >= 5:
        return "AKHIR PEKAN", "Tutup."
    if now.date() in holidays.ID(years=now.year):
        return "LIBUR NASIONAL", "Tutup."
    t = now.hour + now.minute / 60
    if t < 9.0:
        return "PRA-PASAR", "Wait."
    elif t <= 16.0:
        return "LIVE MARKET", "Trading."
    else:
        return "PASCA-PASAR", "Analysis."


# -----------------------------------------------------------------------------
# COLS UNTUK WARM-UP CHECK
# -----------------------------------------------------------------------------

_INDICATOR_COLS_DAY   = ["ATR", "RSI", "MACD", "Supertrend_Dir", "VWAP"]
_INDICATOR_COLS_SWING = ["ATR", "RSI", "MACD", "Supertrend_Dir", "EMA20", "EMA50", "EMA200"]
_INDICATOR_COLS_DAILY = ["MA20_D", "MA50_D"]


# -----------------------------------------------------------------------------
# WORKER MULTITHREADING — PROSES SATU TICKER
# -----------------------------------------------------------------------------

def process_single_stock(
    ticker: str,
    trade_mode: str,
    mtf_filter: bool,
    df_universe: pd.DataFrame,
) -> dict | None:
    """
    Analisa satu ticker; kembalikan dict hasil atau None jika tidak lolos.

    Pre-filter (interval 1d) dijalankan terlebih dahulu, baru scoring
    per mode menggunakan interval yang sesuai.
    """
    ticker_bersih = ticker.replace(".JK", "")

    try:
        # ── PRE-FILTER: selalu gunakan interval 1d ──────────────────────────
        data_daily_pf = get_full_stock_data(ticker, interval="1d")
        hist_pf = data_daily_pf.get("history", pd.DataFrame())
        if hist_pf.empty:
            return None

        hist_pf = drop_empty_candles(hist_pf)
        if len(hist_pf) < 30:
            return None

        # --- OBV Divergence ---
        # Gugur jika OBV candle terakhir <= rata-rata OBV 5 candle sebelumnya.
        # Menggunakan rata-rata (bukan titik tunggal) agar lebih robust terhadap
        # fluktuasi harian dan kondisi pasar koreksi sementara.
        obv_vals = [0.0]
        for i in range(1, len(hist_pf)):
            c_now  = hist_pf["Close"].iloc[i]
            c_prev = hist_pf["Close"].iloc[i - 1]
            v_now  = hist_pf["Volume"].iloc[i]
            if c_now > c_prev:
                obv_vals.append(obv_vals[-1] + v_now)
            elif c_now < c_prev:
                obv_vals.append(obv_vals[-1] - v_now)
            else:
                obv_vals.append(obv_vals[-1])

        if len(obv_vals) > OBV_LOOKBACK:
            obv_ref_avg = float(np.mean(obv_vals[-(OBV_LOOKBACK + 1):-1]))
            if obv_vals[-1] <= obv_ref_avg:
                return None

        # --- CMF(20) ---
        # Threshold diperlunak ke CMF_THRESHOLD (-0.15) agar tidak terlalu agresif
        # saat pasar sedang koreksi ringan.
        hl   = hist_pf["High"] - hist_pf["Low"]
        mfm  = (
            ((hist_pf["Close"] - hist_pf["Low"]) - (hist_pf["High"] - hist_pf["Close"]))
            / hl.replace(0, np.nan)
        )
        cmf  = (mfm * hist_pf["Volume"]).rolling(20).sum() / hist_pf["Volume"].rolling(20).sum()
        cmf_last = cmf.dropna()
        if cmf_last.empty or float(cmf_last.iloc[-1]) <= CMF_THRESHOLD:
            return None

        # --- Value_MA20 ---
        sektor_nama    = get_sector_from_universe(ticker_bersih, df_universe)
        syariah_status = "Ya" if is_syariah_from_universe(ticker_bersih, df_universe) else "Tidak"
        fundamental    = get_fundamental_from_universe(ticker_bersih, df_universe)

        value_ma20 = fundamental.get("Value_MA20")
        if value_ma20 is None:
            value_ma20 = float(
                (hist_pf["Close"] * hist_pf["Volume"]).rolling(20).mean().iloc[-1]
            )
        if pd.isna(value_ma20) or value_ma20 <= 0:
            return None

        # --- Market Cap ---
        info = data_daily_pf.get("info", {})
        market_cap_usd = info.get("marketCap")
        if market_cap_usd is None or pd.isna(market_cap_usd):
            return None
        if market_cap_usd <= MC_MIN_USD:
            return None

        # --- ROE / ROA ---
        roe = fundamental["ROE"]
        roa = fundamental["ROA"]
        if roe is None:
            roe_raw = info.get("returnOnEquity")
            roe = float(roe_raw) * 100 if roe_raw is not None else None
        if roa is None:
            roa_raw = info.get("returnOnAssets")
            roa = float(roa_raw) * 100 if roa_raw is not None else None

        roe_valid = roe is not None and not pd.isna(roe)
        roa_valid = roa is not None and not pd.isna(roa)
        if roe_valid and roe <= 0:
            return None
        if roa_valid and roa <= 0:
            return None

        quality_label = "Rated" if (roe_valid or roa_valid) else "Unrated"

        # ── SCORING ──────────────────────────────────────────────────────────
        interval = "15m" if trade_mode == "Day Trading" else "1d"
        if trade_mode == "Day Trading":
            data = get_full_stock_data(ticker, interval="15m")
        else:
            data = data_daily_pf  # sudah ada, tidak perlu fetch ulang

        hist = data.get("history", pd.DataFrame())
        if hist.empty:
            return None

        hist = drop_empty_candles(hist)
        # Kebutuhan warm-up minimum: EMA200 dengan ewm(adjust=False) stabil di ~150 candle.
        # 210 terlalu konservatif dan menggugurkan saham liquid yang candle bersihnya
        # sedikit di bawah 210 akibat suspend atau libur bursa.
        min_candles = 150 if trade_mode == "Swing Trading" else 55
        if len(hist) < min_candles:
            return None

        ind_cols   = _INDICATOR_COLS_DAY if trade_mode == "Day Trading" else _INDICATOR_COLS_SWING
        df         = calculate_indicators(hist, trade_mode)
        valid_iloc = find_valid_last_iloc(df, indicator_cols=ind_cols)
        if valid_iloc is None:
            return None

        stale_days = compute_stale_days(df, valid_iloc, interval)
        last       = df.iloc[valid_iloc]
        curr_price = float(last["Close"])
        if curr_price <= 0:
            return None

        # Volume & RVOL
        vol_sma20 = df["Volume"].rolling(20).mean().iloc[valid_iloc]
        rvol      = float(last["Volume"]) / float(vol_sma20) if (vol_sma20 and vol_sma20 > 0) else 0.0

        score  = 0.0
        alasan = []

        # ── SCORING: DAY TRADING ─────────────────────────────────────────────
        if trade_mode == "Day Trading":

            # MTF filter: gugur sebelum skor dihitung
            if mtf_filter and int(last["Supertrend_Dir"]) != 1:
                return None

            # 1. RVOL tier
            if rvol >= RVOL_HIGH:
                score += 20; alasan.append(f"RVOL Tinggi ({rvol:.1f}x) +20")
            elif rvol >= RVOL_MID:
                score += 10; alasan.append(f"RVOL Moderat ({rvol:.1f}x) +10")

            # 2. Harga vs VWAP: Close > VWAP DAN VWAP[i] > VWAP[i-1]
            vwap_now  = float(last.get("VWAP", np.nan))
            vwap_prev = float(df["VWAP"].iloc[valid_iloc - 1]) if valid_iloc >= 1 else np.nan
            if (
                not pd.isna(vwap_now)
                and not pd.isna(vwap_prev)
                and curr_price > vwap_now
                and vwap_now > vwap_prev
            ):
                score += 20; alasan.append("Price > VWAP & VWAP Naik +20")

            # 3. Supertrend (10,2) tier
            st_pts, st_label = compute_supertrend_score(df, valid_iloc, 20.0, 15.0)
            if st_pts > 0:
                score += st_pts
                alasan.append(f"{st_label} (10,2)")

            # 4. MACD Golden Cross (dalam 3 candle terakhir)
            macd_gc_window = max(valid_iloc - 2, 0)
            macd_gc = False
            for k in range(macd_gc_window, valid_iloc + 1):
                if k == 0:
                    continue
                if df["MACD"].iloc[k] > df["MACD_Signal"].iloc[k] and \
                   df["MACD"].iloc[k - 1] <= df["MACD_Signal"].iloc[k - 1]:
                    macd_gc = True
                    break
            # juga lolos jika MACD > Signal pada candle terakhir (tanpa perlu baru cross)
            if not macd_gc and float(last["MACD"]) > float(last["MACD_Signal"]):
                macd_gc = True
            if macd_gc:
                score += 5; alasan.append("MACD Golden Cross +5")

            # 5. MACD Histogram naik
            if valid_iloc >= 1:
                hist_now  = float(df["MACD_Hist"].iloc[valid_iloc])
                hist_prev = float(df["MACD_Hist"].iloc[valid_iloc - 1])
                if hist_now > hist_prev:
                    score += 5; alasan.append("MACD Histogram Naik +5")

            # 6. RSI(9) Momentum: 45 - 70
            rsi_val = float(last["RSI"])
            if RSI_MOM_LOW <= rsi_val <= RSI_MOM_HIGH:
                score += 7.5; alasan.append(f"RSI Momentum ({rsi_val:.1f}) +7.5")

            # 7. RSI(9) Trend: 3 candle consecutive naik
            if compute_rsi_trend_3(df, "RSI", valid_iloc):
                score += 7.5; alasan.append("RSI Trend 3 Candle Naik +7.5")

            # 8. PSAR bullish
            if bool(last.get("PSAR_Bull", False)):
                score += 5; alasan.append("PSAR Bullish +5")

            # 9. VPT Trend (EMA slope)
            if compute_vpt_trend(df, valid_iloc):
                score += 10; alasan.append("VPT Trend Naik +10")

            # MTF Bonus: daily candle check
            try:
                data_daily_mtf = get_full_stock_data(ticker, interval="1d")
                df_daily       = data_daily_mtf.get("history", pd.DataFrame())
                if not df_daily.empty:
                    df_daily = drop_empty_candles(df_daily)
                if not df_daily.empty and len(df_daily) >= 55:
                    df_daily        = df_daily.copy()
                    df_daily["MA50_D"] = df_daily["Close"].rolling(50).mean()
                    df_daily["MA20_D"] = df_daily["Close"].rolling(20).mean()
                    vi_d = find_valid_last_iloc(df_daily, indicator_cols=_INDICATOR_COLS_DAILY)
                    if vi_d is not None:
                        ld = df_daily.iloc[vi_d]
                        if ld["Close"] > ld["MA50_D"] and ld["MA20_D"] > ld["MA50_D"]:
                            score += 10; alasan.append("Daily Uptrend (>MA50 & MA20>MA50) +10")
                        elif ld["Close"] > ld["MA50_D"]:
                            score += 5;  alasan.append("Daily Sideways (>MA50) +5")
                        # Downtrend harian: tidak beri bonus, tapi tidak aktif menghukum.
                        # Pre-filter OBV+CMF sudah menyaring tren — penalti -15 di sini
                        # adalah double punishment yang membunuh skor di pasar bearish.
            except Exception:
                pass

        # ── SCORING: SWING TRADING ───────────────────────────────────────────
        else:

            # MTF filter: Supertrend_Dir != 1 ATAU Close <= EMA50 -> gugur
            if mtf_filter:
                if int(last["Supertrend_Dir"]) != 1 or curr_price <= float(last["EMA50"]):
                    return None

            # 1. Supertrend (10,3) tier
            st_pts, st_label = compute_supertrend_score(df, valid_iloc, 20.0, 15.0)
            if st_pts > 0:
                score += st_pts
                alasan.append(f"{st_label} (10,3)")

            # 2. MA Structure tier
            ema20  = float(last["EMA20"])
            ema50  = float(last["EMA50"])
            ema200 = float(last["EMA200"])
            if curr_price > ema20 and ema20 > ema50 and ema50 > ema200:
                score += 20; alasan.append("MA Structure Tier 1 (Price>EMA20>EMA50>EMA200) +20")
            elif curr_price > ema50 and ema20 > ema50:
                score += 10; alasan.append("MA Structure Tier 2 (Price>EMA50 & EMA20>EMA50) +10")

            # 3. MACD Golden Cross (dalam 5 candle terakhir)
            macd_gc_window = max(valid_iloc - 4, 0)
            macd_gc = False
            for k in range(macd_gc_window, valid_iloc + 1):
                if k == 0:
                    continue
                if df["MACD"].iloc[k] > df["MACD_Signal"].iloc[k] and \
                   df["MACD"].iloc[k - 1] <= df["MACD_Signal"].iloc[k - 1]:
                    macd_gc = True
                    break
            if not macd_gc and float(last["MACD"]) > float(last["MACD_Signal"]):
                macd_gc = True
            if macd_gc:
                score += 7.5; alasan.append("MACD Golden Cross +7.5")

            # 4. MACD Histogram naik
            if valid_iloc >= 1:
                hist_now  = float(df["MACD_Hist"].iloc[valid_iloc])
                hist_prev = float(df["MACD_Hist"].iloc[valid_iloc - 1])
                if hist_now > hist_prev:
                    score += 7.5; alasan.append("MACD Histogram Naik +7.5")

            # 5. RVOL tier
            if rvol >= RVOL_HIGH:
                score += 15; alasan.append(f"RVOL Tinggi ({rvol:.1f}x) +15")
            elif rvol >= RVOL_MID:
                score += 10; alasan.append(f"RVOL Moderat ({rvol:.1f}x) +10")

            # 6. RSI(14) Momentum: 45 - 70
            rsi_val = float(last["RSI"])
            if RSI_MOM_LOW <= rsi_val <= RSI_MOM_HIGH:
                score += 10; alasan.append(f"RSI Momentum ({rsi_val:.1f}) +10")

            # 7. RSI(14) Trend: 3 candle consecutive naik
            if compute_rsi_trend_3(df, "RSI", valid_iloc):
                score += 10; alasan.append("RSI Trend 3 Candle Naik +10")

            # 8. PSAR bullish
            if bool(last.get("PSAR_Bull", False)):
                score += 5; alasan.append("PSAR Bullish +5")

            # 9. VPT Trend (EMA slope)
            if compute_vpt_trend(df, valid_iloc):
                score += 5; alasan.append("VPT Trend Naik +5")

            # Bonus: MACD Early Recovery
            # Histogram sudah berbalik positif (Hist > 0) TAPI MACD Line masih < Signal Line
            if valid_iloc >= 1:
                hist_now = float(df["MACD_Hist"].iloc[valid_iloc])
                macd_now = float(last["MACD"])
                sig_now  = float(last["MACD_Signal"])
                if hist_now > 0 and macd_now < sig_now:
                    score += 10; alasan.append("MACD Early Recovery (Hist>0, MACD<Signal) +10")

            # Penalti: RSI Overbought
            if rsi_val > RSI_OVERBOUGHT:
                score -= 15; alasan.append(f"RSI Overbought ({rsi_val:.1f}) -15")

        # Floor 0 dan cap 100 diterapkan di sini — mencegah skor negatif masuk raw_results
        score = min(max(round(score), 0), 100)
        return {
            "Ticker":    ticker_bersih,
            "Sektor":    sektor_nama,
            "Syariah":   syariah_status,
            "Quality":   quality_label,
            "Skor":      score,
            "Harga":     int(curr_price),
            "ATR":       float(last["ATR"]),
            "Alasan":    alasan,
            "RSI":       float(last["RSI"]),
            "StaleDays": stale_days,
            "Interval":  interval,
        }

    except Exception:
        return None


# -----------------------------------------------------------------------------
# SIDEBAR FILTER UNIVERSE
# -----------------------------------------------------------------------------

def apply_sidebar_filters(
    saham_list: list[str],
    df_universe: pd.DataFrame,
) -> list[str]:
    """Terapkan filter sektor, syariah, MktCap dari sidebar; return list terfilter."""
    if df_universe.empty:
        return saham_list

    if "Sektor" in df_universe.columns:
        semua_sektor   = sorted(df_universe["Sektor"].dropna().unique().tolist())
        pilihan_sektor = st.sidebar.multiselect("Filter Sektor", semua_sektor, default=semua_sektor)
    else:
        pilihan_sektor = []

    only_syariah = st.sidebar.checkbox("Hanya Saham Syariah", value=False)

    if "MktCap" in df_universe.columns:
        semua_mktcap   = sorted(df_universe["MktCap"].dropna().unique().tolist())
        pilihan_mktcap = st.sidebar.multiselect("Filter Market Cap", semua_mktcap, default=semua_mktcap)
    else:
        pilihan_mktcap = []

    filtered = []
    for ticker_jk in saham_list:
        t    = ticker_jk.replace(".JK", "")
        mask = df_universe["Kode Saham"].astype(str).str.strip() == t
        rows = df_universe[mask]
        if rows.empty:
            filtered.append(ticker_jk)
            continue
        row = rows.iloc[0]
        if pilihan_sektor and "Sektor" in row.index:
            if row["Sektor"] not in pilihan_sektor:
                continue
        if only_syariah and "Syariah" in row.index:
            if str(row["Syariah"]).strip().lower() not in ("ya", "yes", "true", "1"):
                continue
        if pilihan_mktcap and "MktCap" in row.index:
            if row["MktCap"] not in pilihan_mktcap:
                continue
        filtered.append(ticker_jk)

    return filtered


# -----------------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------------

def run_screening() -> None:
    """Entry point modul screening — dipanggil dari app.py."""
    saham_list, df_universe = load_universe()
    if not saham_list:
        st.stop()

    liquid_aktif = not get_liquid_stocks().empty
    if liquid_aktif:
        st.sidebar.success(
            f"Universe: **{len(saham_list)} saham** dari `liquid_stocks.csv`"
        )
    else:
        st.sidebar.warning(
            f"Universe: **{len(saham_list)} saham** dari `pre_liquid_stocks.csv` "
            f"(liquid_stocks.csv tidak tersedia atau kosong)"
        )

    saham_list = apply_sidebar_filters(saham_list, df_universe)
    if not saham_list:
        st.warning("Tidak ada saham yang cocok dengan filter yang dipilih.")
        st.stop()

    st.markdown("<h4 style='text-align: center;'>Pilih Mode Aplikasi</h4>",
                unsafe_allow_html=True)
    ui_mode = st.radio(
        "Tampilan Aplikasi:",
        ["🌱 Mode Praktis (Untuk Pemula)", "💼 Mode Pro (Indikator Lengkap)"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.markdown("---")

    if "Praktis" in ui_mode:
        st.markdown(
            "<h1 style='text-align: center;'>🔍 Asisten Saham Pintar</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align: center; color: gray;'>"
            "Mencarikan saham potensial secara otomatis.</p>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<h1 style='text-align: center;'>🔍 Screening Saham Harian Pro</h1>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    with st.expander("📖 Glosarium Istilah (Kamus Trader)"):
        st.markdown("""
        * **Entry:** Rentang harga yang disarankan untuk mulai membeli.
        * **TP (Take Profit):** Target harga untuk merealisasikan keuntungan.
        * **SL (Stop Loss):** Batas toleransi kerugian.
        * **ATR:** Indikator volatilitas harga.
        * **Maks Lot:** Rekomendasi porsi maksimal pembelian yang aman.
        * **RVOL:** Relative Volume — seberapa ramai dibanding rata-rata 20 hari.
        * **PSAR:** Parabolic SAR — konfirmasi arah tren.
        * **Supertrend:** Indikator tren berbasis ATR.
        """)

    if "Praktis" in ui_mode:
        st.write("### 1️⃣ Pilih Gaya Beli Anda")
        trade_mode_raw = st.radio(
            "Suka memantau layar setiap hari atau disimpan beberapa hari?",
            ["Day Trading (Beli Pagi, Jual Siang/Sore)",
             "Swing Trading (Beli & Simpan Beberapa Hari)"],
            horizontal=True,
        )
        trade_mode = "Day Trading" if "Day" in trade_mode_raw else "Swing Trading"
    else:
        st.info(
            "⏰ **Waktu Analisa Optimal:**\n"
            "- **Day Trading:** 09.30 - 11.00 WIB\n"
            "- **Swing Trading:** > 16.00 WIB"
        )
        trade_mode = st.radio(
            "Pilih Strategi Trading:", ["Day Trading", "Swing Trading"], horizontal=True
        )

    if "Praktis" in ui_mode:
        st.write("### 2️⃣ Kalkulator Keamanan Dana")
        mtf_filter   = True
        sector_boost = True
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            total_modal = st.number_input(
                "Berapa Total Uang Anda untuk Saham? (Rp):",
                min_value=1_000_000, value=10_000_000, step=1_000_000,
            )
        with col_m2:
            modal_risiko = st.number_input(
                "Batas maksimal uang yang rela hilang per saham? (Rp):",
                min_value=10_000, value=100_000, step=50_000,
            )
        batas_alokasi_rp = total_modal * MAX_ALLOC_PCT
        st.success(
            f"Sistem akan memastikan Anda tidak membeli saham melebihi "
            f"Rp {format_rp(batas_alokasi_rp)} per saham."
        )
    else:
        with st.expander("🛠️ Pengaturan Filter & Manajemen Risiko", expanded=False):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                mtf_filter   = st.checkbox("Hanya saham searah tren besar", value=True)
            with col_f2:
                sector_boost = st.checkbox("Hanya saham dari sektor yang kuat", value=True)
            st.markdown("---")
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                total_modal = st.number_input(
                    "Total Modal Portofolio (Rp):",
                    min_value=1_000_000, value=100_000_000, step=5_000_000,
                )
            with col_m2:
                modal_risiko = st.number_input(
                    "Nominal Maksimal Siap Rugi (Rp):",
                    min_value=10_000, value=1_000_000, step=50_000,
                )
            risiko_persen    = (modal_risiko / total_modal) * 100 if total_modal > 0 else 0
            batas_alokasi_rp = total_modal * MAX_ALLOC_PCT
            st.markdown(f"""
            <div style="background-color:#d4edda; border-left:5px solid #28a745;
                        padding:10px; border-radius:5px;">
                <p style="margin:0; font-size:12px; color:#155724;">
                    Total Modal: <b>Rp {format_rp(total_modal)}</b> |
                    Nominal Siap Rugi (<b>{risiko_persen:.1f}%</b>):
                    <b>Rp {format_rp(modal_risiko)}</b>
                </p>
            </div>""", unsafe_allow_html=True)

    session, status_desc = get_market_session()
    if "Tutup" in status_desc:
        st.error(f"🛑 **Bursa Saham Sedang Tutup ({session})**")
    elif "Wait" in status_desc:
        st.warning("⏳ **Bursa Saham Belum Buka (Sesi Pra-Pasar)**")
    elif "Analysis" in status_desc:
        st.info("🌙 **Bursa Saham Sudah Tutup (Sesi Pasca-Pasar)**")
    else:
        st.success("🟢 **Bursa Saham Sedang Buka (Live Market)**")

    st.markdown("---")

    tombol_cari = (
        "🚀 CARIKAN SAHAM UNTUK SAYA"
        if "Praktis" in ui_mode
        else f"🚀 JALANKAN ANALISA {trade_mode.upper()}"
    )

    if st.button(tombol_cari, use_container_width=True):
        raw_results    = []
        loading_header = st.empty()
        loading_header.write("### 🔄 Mesin sedang memilah saham. Mohon tunggu...")
        status_text  = st.empty()
        progress_bar = st.progress(0)
        total_saham  = len(saham_list)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(
                    process_single_stock, ticker, trade_mode, mtf_filter, df_universe
                ): ticker
                for ticker in saham_list
            }
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                completed += 1
                status_text.text(f"Memeriksa {completed} saham...")
                progress_bar.progress(completed / total_saham)
                result = future.result()
                if result is not None:
                    raw_results.append(result)

        loading_header.empty()
        status_text.empty()
        progress_bar.empty()

        df_all = pd.DataFrame(raw_results)
        sector_report, leading_sectors = analyze_sector_momentum(df_all)

        # Stale warning: >= 2 hari
        if not df_all.empty and "StaleDays" in df_all.columns:
            max_stale = int(df_all["StaleDays"].max())
            if max_stale >= 2:
                st.warning(
                    f"⚠️ **PERINGATAN: {max_stale} hari bursa libur.** — "
                    f"Data hari libur kosong sudah dihapus otomatis, "
                    f"tapi analisis indikator berisiko tidak akurat selama libur bursa. "
                    f"Sinyal tetap dapat dibaca sebagai persiapan sesi berikutnya."
                )

        final_picks = []
        sl_mult  = SL_MULT_DAY    if trade_mode == "Day Trading" else SL_MULT_SWING
        max_loss = MAX_LOSS_PCT_DAY if trade_mode == "Day Trading" else MAX_LOSS_PCT_SWING
        rr_min   = RR_MIN_DAY      if trade_mode == "Day Trading" else RR_MIN_SWING

        for stock in raw_results:
            f_score = stock["Skor"]

            # Bonus sektor (post-processing)
            if sector_boost and stock["Sektor"] in leading_sectors:
                f_score += 10
                stock["Alasan"].append(f"Sector Hot: {stock['Sektor']} +10")
            # Floor dan cap setelah bonus sektor
            f_score = min(max(round(f_score), 0), 100)

            # Kalkulasi SL, TP, RRR
            atr_sl      = int(stock["Harga"] - (sl_mult * stock["ATR"]))
            hard_cap_sl = int(stock["Harga"] * (1 - max_loss))
            sl          = max(atr_sl, hard_cap_sl)
            tp          = int(stock["Harga"] + (stock["Harga"] - sl) * rr_min)
            rrr         = (
                (tp - stock["Harga"]) / (stock["Harga"] - sl)
                if stock["Harga"] > sl else 0
            )

            # Lot maksimal
            risiko_per_lembar = stock["Harga"] - sl
            if risiko_per_lembar > 0:
                lembar_final = min(
                    modal_risiko / risiko_per_lembar,
                    batas_alokasi_rp / stock["Harga"],
                )
                lot_maksimal = int(lembar_final / 100)
            else:
                lot_maksimal = 0

            pct_risk   = ((stock["Harga"] - sl) / stock["Harga"]) * 100 if stock["Harga"] > 0 else 0
            pct_reward = ((tp - stock["Harga"]) / stock["Harga"]) * 100 if stock["Harga"] > 0 else 0

            if f_score >= SCORE_MIN_ENTRY and rrr >= RRR_MIN_ENTRY:
                final_picks.append({
                    "Ticker":         stock["Ticker"],
                    "Sektor":         stock["Sektor"],
                    "Skor":           f_score,
                    "Harga_Saat_Ini": int(stock["Harga"]),
                    "Syariah":        stock["Syariah"],
                    "Quality":        stock["Quality"],
                    "Entry":          f"Rp {format_rp(int(stock['Harga'] * 0.99))} - {format_rp(stock['Harga'])}",
                    "SL":             sl,
                    "TP":             tp,
                    "RRR":            f"{rrr:.1f}x",
                    "Status":         "FULL SIZING" if f_score >= 85 else "CICIL SEBAGIAN",
                    "Logic":          " | ".join(stock["Alasan"]),
                    "Lot_Maks":       f"{format_rp(lot_maksimal)} Lot",
                    "Pct_Risk":       f"-{pct_risk:.1f}%",
                    "Pct_Reward":     f"+{pct_reward:.1f}%",
                })

        final_picks.sort(key=lambda x: x["Skor"], reverse=True)
        st.session_state["final_picks"]   = final_picks[:10]
        st.session_state["sector_report"] = sector_report
        st.session_state["pdf_session"]   = session
        st.session_state["analysis_done"] = True

        if any(p["Skor"] >= 85 for p in st.session_state["final_picks"]):
            play_alert_sound()

    # ── TAMPILKAN HASIL ───────────────────────────────────────────────────────
    if st.session_state.get("analysis_done", False):
        res       = st.session_state.get("final_picks", [])
        top_3     = res[:3]
        watchlist = res[3:10]

        st.subheader("🌐 Kondisi Pasar Saat Ini")
        c1, c2 = st.columns([2, 1])
        with c1:
            sr = st.session_state.get("sector_report", pd.DataFrame())
            if not sr.empty:
                fig = px.bar(
                    sr.reset_index(),
                    x="Sektor", y="Avg_Score",
                    color="Avg_Score", color_continuous_scale="Greens",
                    title="Kekuatan Sektor Saat Ini",
                )
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.write("**Sektor Paling Ramai:**")
            if not sr.empty:
                for s in sr.index[:3]:
                    st.success(s)

        st.markdown("---")
        judul = (
            "🏆 Pilihan Terbaik Saat Ini"
            if "Praktis" in ui_mode
            else f"🏆 Top 3 Prioritas {trade_mode}"
        )
        st.header(judul)

        if top_3:
            cols = st.columns(len(top_3))
            for idx, item in enumerate(top_3):
                with cols[idx]:
                    st.markdown(f"### {item['Ticker']}")
                    st.write(f"**Sektor:** {item['Sektor']}")
                    st.write(f"**Syariah:** {item['Syariah']} | **Quality:** {item['Quality']}")
                    if "Praktis" in ui_mode:
                        st.info(f"🛒 **Beli di harga:** {item['Entry']}")
                        st.success(f"💰 **Jual Untung di:** Rp {format_rp(item['TP'])} ({item['Pct_Reward']})")
                        st.error(f"🛑 **Batas Aman:** Rp {format_rp(item['SL'])} ({item['Pct_Risk']})")
                        st.warning(f"📦 **Maksimal Beli:** {item['Lot_Maks']} ({item['Status']})")
                    else:
                        st.metric("Skor Institusi", f"{item['Skor']}/100 Pts", item["Status"])
                        st.write(f"**Target (TP):** Rp {format_rp(item['TP'])} ({item['Pct_Reward']})")
                        st.write(f"**Proteksi (SL):** Rp {format_rp(item['SL'])} ({item['Pct_Risk']})")
                        st.info(f"Area Entry: {item['Entry']}")
                        st.warning(f"🛡️ **Maks. Aman:** {item['Lot_Maks']}")
                        st.caption(f"💡 {item['Logic']}")
        else:
            st.warning(
                "Mesin belum menemukan saham yang benar-benar memenuhi kriteria saat ini. "
                "Coba jalankan ulang setelah jam 09.30 WIB atau ubah filter strategi."
            )

        if watchlist:
            st.markdown("---")
            st.subheader("📋 Daftar Cadangan (Peringkat 4-10)")
            df_watch = pd.DataFrame(watchlist).copy()
            df_watch["SL_tampil"] = df_watch.apply(
                lambda x: f"Rp {format_rp(x['SL'])} ({x['Pct_Risk']})", axis=1
            )
            df_watch["TP_tampil"] = df_watch.apply(
                lambda x: f"Rp {format_rp(x['TP'])} ({x['Pct_Reward']})", axis=1
            )
            if "Praktis" in ui_mode:
                df_watch = df_watch.rename(columns={
                    "Sektor":    "Industri",
                    "Entry":     "Area Beli",
                    "SL_tampil": "Jual Rugi (Batas Aman)",
                    "TP_tampil": "Jual Untung (Target)",
                })
                kolom_tampil = [
                    "Ticker", "Industri", "Syariah", "Quality",
                    "Area Beli", "Jual Rugi (Batas Aman)",
                    "Jual Untung (Target)", "Lot_Maks", "Status",
                ]
            else:
                df_watch = df_watch.rename(columns={"SL_tampil": "SL", "TP_tampil": "TP"})
                kolom_tampil = [
                    "Ticker", "Sektor", "Syariah", "Quality", "Skor",
                    "Status", "Entry", "SL", "TP", "RRR", "Lot_Maks",
                ]
            st.dataframe(df_watch[kolom_tampil], use_container_width=True, hide_index=True)

        st.markdown("<br><hr>", unsafe_allow_html=True)
        st.caption(
            "DISCLAIMER: Laporan ini dihasilkan otomatis oleh algoritma. "
            "Bukan rekomendasi beli/jual. Keputusan investasi adalah tanggung jawab Anda. "
            "Selalu DYOR dan terapkan manajemen risiko."
        )

        waktu_cetak_pdf = datetime.now(_TZ_WIB).strftime("%Y%m%d_%H%M")
        pdf_data = export_to_pdf(
            res, trade_mode,
            st.session_state.get("pdf_session", session),
            st.session_state.get("sector_report", pd.DataFrame()),
        )
        st.download_button(
            label="📥 UNDUH LAPORAN SCREENING LENGKAP (PDF)",
            data=pdf_data,
            file_name=f"ExpertStockPro_{trade_mode}_{waktu_cetak_pdf}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


if __name__ == "__main__":
    run_screening()
