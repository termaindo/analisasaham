"""
screening.py
============
Modul Screening Day Trade & Swing Trade.

Universe saham: dibaca dari liquid_stocks.csv (prioritas) atau
pre_liquid_stocks.csv (fallback) via get_liquid_stocks() / load_universe().
Tidak ada lagi dependency ke Google Drive API atau universe.py.
"""

import streamlit as st
import pandas as pd
import numpy as np
import pytz
import os
import base64
import holidays
import plotly.express as px
import concurrent.futures
from datetime import datetime
from fpdf import FPDF

from data_loader import (
    get_full_stock_data,
    get_liquid_stocks,
    get_value_ma20,
    is_ticker_liquid,
    get_ticker_row,
    hitung_div_yield_normal,
    PRE_LIQUID_PATH,
    LIQUID_PATH,
)


# ─────────────────────────────────────────────────────────────────────────────
# LOAD UNIVERSE
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def load_universe() -> tuple[list[str], pd.DataFrame]:
    """
    Prioritas:
      1. liquid_stocks.csv  → sudah di-enrich (Value_MA20, ROE, ROA, dll)
      2. pre_liquid_stocks.csv → fallback jika liquid belum ada

    Mengembalikan (saham_list, df_universe).
    saham_list = list ticker dengan format XXXX.JK
    df_universe = DataFrame lengkap untuk lookup sektor, syariah, fundamental
    """
    # Coba liquid_stocks dulu
    df_liquid = get_liquid_stocks()
    if not df_liquid.empty:
        df = _normalize_universe_columns(df_liquid)
        saham_list = [
            (t if t.endswith(".JK") else t + ".JK")
            for t in df["Kode Saham"].astype(str).str.strip().tolist()
        ]
        return saham_list, df

    # Fallback ke pre_liquid_stocks
    try:
        df = pd.read_csv(PRE_LIQUID_PATH, sep=None, engine="python")
        df = _normalize_universe_columns(df)
        saham_list = [
            (t if t.endswith(".JK") else t + ".JK")
            for t in df["Kode Saham"].astype(str).str.strip().tolist()
        ]
        st.sidebar.warning(
            "⚠️ `liquid_stocks.csv` belum tersedia. "
            "Menggunakan `pre_liquid_stocks.csv` sebagai fallback — "
            "data enrichment (Value_MA20, ROE, dll) tidak tersedia."
        )
        return saham_list, df
    except FileNotFoundError:
        st.error(f"❌ File universe tidak ditemukan: {PRE_LIQUID_PATH}")
        return [], pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Gagal membaca universe saham: {e}")
        return [], pd.DataFrame()


def _normalize_universe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalisasi nama kolom DataFrame universe agar konsisten."""
    df = df.copy()
    df.columns = df.columns.str.strip()
    rename_map: dict = {}
    for col in df.columns:
        c = col.lower().strip().lstrip("\ufeff")
        if c in ("ticker", "kode saham", "kode", "saham"):
            rename_map[col] = "Kode Saham"
        elif c in ("sektor", "sector"):
            rename_map[col] = "Sektor"
        elif c in ("syariah",):
            rename_map[col] = "Syariah"
        elif c in ("mktcap", "mkt cap", "market cap", "market_cap"):
            rename_map[col] = "Mkt Cap"
        elif c.startswith("roe"):
            rename_map[col] = "ROE"
        elif c.startswith("roa"):
            rename_map[col] = "ROA"
        elif c.startswith("npm") or "profit margin" in c:
            rename_map[col] = "NPM"
        elif "value_ma20" in c or "value ma20" in c:
            rename_map[col] = "Value_MA20"
    df = df.rename(columns=rename_map)
    # Bersihkan .JK dari kolom Kode Saham
    if "Kode Saham" in df.columns:
        df["Kode Saham"] = df["Kode Saham"].astype(str).str.strip().str.replace(".JK", "", regex=False)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# LOOKUP HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_sector_from_universe(ticker_bersih: str, df_universe: pd.DataFrame) -> str:
    if df_universe.empty or "Sektor" not in df_universe.columns:
        return "Lainnya"
    mask = df_universe["Kode Saham"].astype(str).str.strip() == ticker_bersih
    rows = df_universe[mask]
    return rows.iloc[0]["Sektor"] if not rows.empty else "Lainnya"


def is_syariah_from_universe(ticker_bersih: str, df_universe: pd.DataFrame) -> bool:
    if df_universe.empty or "Syariah" not in df_universe.columns:
        return False
    mask = df_universe["Kode Saham"].astype(str).str.strip() == ticker_bersih
    rows = df_universe[mask]
    if rows.empty:
        return False
    return str(rows.iloc[0]["Syariah"]).strip().lower() in ("ya", "yes", "true", "1")


def get_fundamental_from_universe(ticker_bersih: str, df_universe: pd.DataFrame) -> dict:
    """Ambil ROE, ROA, NPM, Value_MA20 dari df_universe jika tersedia."""
    result = {"ROE": None, "ROA": None, "NPM": None, "Value_MA20": None}
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
    if "Value_MA20" in row.index:
        try:
            result["Value_MA20"] = float(row["Value_MA20"])
        except Exception:
            pass
    return result


def get_value_ma20_from_universe(ticker_bersih: str, df_universe: pd.DataFrame) -> float | None:
    fund = get_fundamental_from_universe(ticker_bersih, df_universe)
    return fund.get("Value_MA20")


# ─────────────────────────────────────────────────────────────────────────────
# FORMAT RUPIAH
# ─────────────────────────────────────────────────────────────────────────────

def format_rp(angka) -> str:
    if isinstance(angka, str):
        return angka
    return f"{int(angka):,}".replace(",", ".")


# ─────────────────────────────────────────────────────────────────────────────
# AUDIO ALERT
# ─────────────────────────────────────────────────────────────────────────────

def play_alert_sound() -> None:
    audio_html = """
    <audio autoplay>
      <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
    </audio>
    """
    st.components.v1.html(audio_html, height=0)


# ─────────────────────────────────────────────────────────────────────────────
# ANALISA ROTASI SEKTOR
# ─────────────────────────────────────────────────────────────────────────────

def analyze_sector_momentum(full_results_df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    if full_results_df.empty:
        return pd.DataFrame(), []
    sector_summary = (
        full_results_df.groupby("Sektor")
        .agg({"Skor": "mean", "Ticker": "count"})
        .rename(columns={"Ticker": "Jumlah_Saham", "Skor": "Avg_Score"})
        .sort_values("Avg_Score", ascending=False)
    )
    leading_sectors = sector_summary[sector_summary["Avg_Score"] >= 70].index.tolist()
    return sector_summary, leading_sectors


# ─────────────────────────────────────────────────────────────────────────────
# GENERATOR PDF
# ─────────────────────────────────────────────────────────────────────────────

def export_to_pdf(
    hasil_lolos: list,
    trade_mode: str,
    session: str,
    sector_report: pd.DataFrame,
    logo_path: str = "logo_expert_stock_pro.png",
) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(20, 20, 20)
    pdf.rect(0, 0, 210, 25, "F")
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=10, y=3, w=18, h=18)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 16)
    pdf.set_xy(35, 8)
    pdf.cell(0, 10, "Expert Stock Pro - Ultimate Alpha Report", ln=True)
    pdf.set_y(28)
    pdf.set_font("Arial", "I", 10)
    pdf.set_text_color(0, 0, 255)
    pdf.cell(0, 5, "Sumber: https://bit.ly/sahampintar", ln=True, align="C", link="https://bit.ly/sahampintar")
    pdf.ln(3)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 8, f"Strategi: {trade_mode} | Sesi: {session}", ln=True, align="C")
    tz = pytz.timezone("Asia/Jakarta")
    waktu_cetak = datetime.now(tz).strftime("%d-%m-%Y %H:%M WIB")
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 5, f"Dicetak: {waktu_cetak}", ln=True, align="R")
    pdf.ln(2)

    if not sector_report.empty:
        pdf.set_fill_color(220, 235, 255)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(190, 7, "  MARKET OVERVIEW (SEKTOR TERKUAT HARI INI)", 0, ln=True, fill=True)
        pdf.set_font("Arial", "", 9)
        top_sectors = ", ".join(sector_report.index[:3].tolist())
        pdf.multi_cell(190, 6, f" Aliran dana terbesar: {top_sectors}")
        pdf.ln(3)

    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(190, 8, "A. TOP 3 PRIORITAS TRANSAKSI", 0, ln=True, fill=True)
    pdf.ln(2)

    for item in hasil_lolos[:3]:
        pdf.set_font("Arial", "B", 10)
        pdf.cell(190, 6,
            f"{item['Ticker']} - {item['Sektor']} | Syariah: {item['Syariah']} | "
            f"Quality: {item['Quality']} | Score: {item['Skor']}/100",
            ln=True)
        pdf.set_font("Arial", "", 9)
        pdf.cell(60, 5, f"Entry: {item['Entry']}", 0)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(65, 5, f"TP Target: Rp {format_rp(item['TP'])} ({item['Pct_Reward']})", 0)
        pdf.set_text_color(200, 0, 0)
        pdf.cell(65, 5, f"Stop Loss: Rp {format_rp(item['SL'])} ({item['Pct_Risk']})", ln=True)
        pdf.set_text_color(0, 0, 0)
        status_pdf = item["Status"].replace("🔥", "").replace("🎯", "").strip()
        pdf.set_font("Arial", "B", 8)
        pdf.cell(190, 5, f"Batas Alokasi Maksimal: {item['Lot_Maks']} ({status_pdf})", ln=True)
        pdf.set_font("Arial", "I", 8)
        pdf.multi_cell(190, 4, f"Logic: {item['Logic']}")
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
            pdf.cell(190, 5,
                f"{w['Ticker']} ({w['Sektor'][:20]}) | Syariah: {w['Syariah']} | "
                f"Quality: {w['Quality']} | Skor: {w['Skor']}",
                ln=True)
            pdf.set_font("Arial", "", 8)
            pdf.cell(40, 5, f"Entry: {w['Entry']}", 0)
            pdf.set_text_color(0, 128, 0)
            pdf.cell(50, 5, f"TP: Rp {format_rp(w['TP'])} ({w['Pct_Reward']})", 0)
            pdf.set_text_color(200, 0, 0)
            pdf.cell(50, 5, f"SL: Rp {format_rp(w['SL'])} ({w['Pct_Risk']})", 0)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(50, 5, f"Maks: {w['Lot_Maks']}", ln=True)
            pdf.set_font("Arial", "I", 7)
            pdf.multi_cell(190, 4, f"Logic: {w['Logic']}")
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(190, 5, "DISCLAIMER:", ln=True)
    pdf.set_font("Arial", "I", 7)
    pdf.multi_cell(190, 4,
        "Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma "
        "indikator teknikal dan fundamental. Bukan merupakan ajakan, rekomendasi pasti, atau "
        "paksaan untuk membeli/menjual saham. Keputusan investasi sepenuhnya menjadi tanggung "
        "jawab pribadi investor. Selalu terapkan manajemen risiko yang baik dan DYOR.")
    return pdf.output(dest="S").encode("latin-1", "ignore")


# ─────────────────────────────────────────────────────────────────────────────
# KALKULASI INDIKATOR TEKNIKAL
# ─────────────────────────────────────────────────────────────────────────────

def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 2.0) -> pd.DataFrame:
    hl2 = (df["High"] + df["Low"]) / 2
    high_low   = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close  = np.abs(df["Low"]  - df["Close"].shift())
    tr  = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()

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
        supertrend.iloc[i] = lower_band.iloc[i] if direction.iloc[i] == 1 else upper_band.iloc[i]

    df["Supertrend"]     = supertrend
    df["Supertrend_Dir"] = direction
    return df


def calculate_psar(df: pd.DataFrame, af_start=0.02, af_step=0.02, af_max=0.2) -> pd.DataFrame:
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

    df["PSAR"]      = psar
    df["PSAR_Bull"] = df["Close"] > df["PSAR"]
    return df


def calculate_indicators(df: pd.DataFrame, trade_mode: str) -> pd.DataFrame:
    high_low   = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close  = np.abs(df["Low"]  - df["Close"].shift())
    df["ATR"]  = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"]        = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"]   = df["MACD"] - df["MACD_Signal"]

    if trade_mode == "Day Trading":
        df = calculate_supertrend(df, period=10, multiplier=2)
        df["VWAP"] = (
            (df["Close"] * df["Volume"]).rolling(5).sum()
            / df["Volume"].rolling(5).sum()
        )
        delta = df["Close"].diff()
        gain  = delta.where(delta > 0, 0).rolling(9).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(9).mean()
        df["RSI"] = 100 - (100 / (1 + (gain / loss)))
        df = calculate_psar(df)
    else:  # Swing Trading
        df = calculate_supertrend(df, period=10, multiplier=3)
        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA50"] = df["Close"].rolling(50).mean()
        delta = df["Close"].diff()
        gain  = delta.where(delta > 0, 0).rolling(14).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df["RSI"] = 100 - (100 / (1 + (gain / loss)))
        df = calculate_psar(df)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# MARKET SESSION
# ─────────────────────────────────────────────────────────────────────────────

def get_market_session() -> tuple[str, str]:
    tz  = pytz.timezone("Asia/Jakarta")
    now = datetime.now(tz)
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


# ─────────────────────────────────────────────────────────────────────────────
# WORKER MULTITHREADING
# ─────────────────────────────────────────────────────────────────────────────

def process_single_stock(
    ticker: str,
    trade_mode: str,
    mtf_filter: bool,
    df_universe: pd.DataFrame,
) -> dict | None:
    ticker_bersih = ticker.replace(".JK", "")
    try:
        interval = "15m" if trade_mode == "Day Trading" else "1d"
        data = get_full_stock_data(ticker, interval=interval)
        df   = calculate_indicators(data["history"], trade_mode)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        curr_price = last["Close"]

        sektor_nama    = get_sector_from_universe(ticker_bersih, df_universe)
        syariah_status = "Ya" if is_syariah_from_universe(ticker_bersih, df_universe) else "Tidak"

        fundamental = get_fundamental_from_universe(ticker_bersih, df_universe)
        roe = fundamental["ROE"]
        roa = fundamental["ROA"]

        # Fallback ke yfinance jika tidak ada di file
        if roe is None:
            roe_raw = data.get("info", {}).get("returnOnEquity")
            roe = roe_raw * 100 if roe_raw is not None else None
        if roa is None:
            roa_raw = data.get("info", {}).get("returnOnAssets")
            roa = roa_raw * 100 if roa_raw is not None else None

        # ── PRE-FILTER WAJIB ────────────────────────────────────────────────

        # 1. Likuiditas: Value_MA20 — pakai dari liquid_stocks jika ada
        value_ma20 = fundamental.get("Value_MA20")
        if value_ma20 is None:
            value_ma20 = (df["Close"] * df["Volume"]).rolling(20).mean().iloc[-1]
        if pd.isna(value_ma20) or value_ma20 <= 0:
            return None

        # 2. Market Cap > Rp 500 Miliar
        USD_TO_IDR    = 16_000
        MC_MIN_IDR    = 500_000_000_000
        MC_MIN_USD    = MC_MIN_IDR / USD_TO_IDR
        market_cap_usd = data.get("info", {}).get("marketCap")
        if market_cap_usd is None or pd.isna(market_cap_usd) or market_cap_usd <= MC_MIN_USD:
            return None

        # 3. Kesehatan (Quality): ROE dan ROA
        roe_valid = roe is not None and not pd.isna(roe)
        roa_valid = roa is not None and not pd.isna(roa)
        if roe_valid or roa_valid:
            if not ((not roe_valid) or (roe > 0)):
                return None
            if not ((not roa_valid) or (roa > 0)):
                return None
            quality_label = "Rated"
        else:
            quality_label = "Unrated"

        score  = 0
        alasan = []

        # ── BANDARMOLOGI ────────────────────────────────────────────────────
        obv = [0]
        for i in range(1, len(df)):
            if df["Close"].iloc[i] > df["Close"].iloc[i - 1]:
                obv.append(obv[-1] + df["Volume"].iloc[i])
            elif df["Close"].iloc[i] < df["Close"].iloc[i - 1]:
                obv.append(obv[-1] - df["Volume"].iloc[i])
            else:
                obv.append(obv[-1])
        df["OBV"] = obv

        mfm = (
            ((df["Close"] - df["Low"]) - (df["High"] - df["Close"]))
            / (df["High"] - df["Low"]).replace(0, np.nan)
        )
        df["CMF"] = (mfm * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum()
        df["VPT"] = (df["Close"].pct_change() * df["Volume"]).cumsum()

        obv_trend_up = df["OBV"].iloc[-1] > df["OBV"].iloc[-5]
        cmf_positive = df["CMF"].iloc[-1] > -0.1
        vpt_trend_up = df["VPT"].iloc[-1] > df["VPT"].iloc[-3]
        vol_sma20    = df["Volume"].rolling(20).mean().iloc[-1]
        rvol         = last["Volume"] / vol_sma20 if vol_sma20 > 0 else 0

        if not obv_trend_up and not cmf_positive:
            return None

        # ── SCORING ─────────────────────────────────────────────────────────
        if trade_mode == "Day Trading":
            if last["Volume"] > vol_sma20 * 1.2:
                score += 15; alasan.append("Volume Spike Kuat (>1.2x SMA20)")
            elif last["Volume"] > vol_sma20:
                score += 8;  alasan.append("Volume Spike (>SMA20)")
            if curr_price > last["VWAP"]:
                score += 15; alasan.append("Price > VWAP")
            st_dir_series  = df["Supertrend_Dir"].iloc[-5:]
            candles_above  = (st_dir_series == 1).sum()
            if last["Supertrend_Dir"] == 1 and prev["Supertrend_Dir"] != 1:
                score += 20; alasan.append("Supertrend Baru Bullish (10,2)")
            elif last["Supertrend_Dir"] == 1 and candles_above > 3:
                score += 15; alasan.append("Supertrend Bullish >3 Candle (10,2)")
            if last["MACD"] > last["MACD_Signal"] and prev["MACD"] <= prev["MACD_Signal"]:
                score += 10; alasan.append("MACD Golden Cross")
            if 45 <= last["RSI"] <= 70:
                score += 7.5; alasan.append(f"RSI Momentum ({last['RSI']:.1f})")
            if last["RSI"] > prev["RSI"]:
                score += 7.5; alasan.append(f"RSI Rising ({prev['RSI']:.1f}->{last['RSI']:.1f})")
            if last["PSAR_Bull"]:
                score += 5; alasan.append("PSAR Bullish")
            if rvol >= 2.5:
                score += 10; alasan.append(f"RVOL Tinggi ({rvol:.1f}x)")
            elif rvol >= 1.5:
                score += 6;  alasan.append(f"RVOL Moderat ({rvol:.1f}x)")
            if vpt_trend_up:
                score += 10; alasan.append("VPT Akumulasi Naik")
            # MTF konfirmasi daily
            try:
                data_daily = get_full_stock_data(ticker, interval="1d")
                df_daily   = data_daily["history"]
                if not df_daily.empty:
                    df_daily["MA50_D"] = df_daily["Close"].rolling(50).mean()
                    df_daily["MA20_D"] = df_daily["Close"].rolling(20).mean()
                    last_d = df_daily.iloc[-1]
                    if not pd.isna(last_d["MA50_D"]) and not pd.isna(last_d["MA20_D"]):
                        if last_d["Close"] > last_d["MA50_D"] and last_d["MA20_D"] > last_d["MA50_D"]:
                            score += 10; alasan.append("Daily Bullish (>MA50) +10")
                        elif last_d["Close"] > last_d["MA50_D"]:
                            score += 5;  alasan.append("Daily Sideways (>MA50) +5")
                        else:
                            score -= 15; alasan.append("Daily Downtrend (<MA50) -15")
            except Exception:
                pass
            if mtf_filter and last["Supertrend_Dir"] != 1:
                return None

        else:  # Swing Trading
            st_dir_series = df["Supertrend_Dir"].iloc[-5:]
            candles_above = (st_dir_series == 1).sum()
            if last["Supertrend_Dir"] == 1 and prev["Supertrend_Dir"] != 1:
                score += 20; alasan.append("Supertrend Baru Bullish (10,3)")
            elif last["Supertrend_Dir"] == 1 and candles_above > 3:
                score += 15; alasan.append("Supertrend Bullish >3 Hari (10,3)")
            if curr_price > last["MA50"] and last["MA20"] > last["MA50"]:
                score += 15; alasan.append("MA Structure (Price>MA50, MA20>MA50)")
            if last["MACD"] > last["MACD_Signal"] and prev["MACD"] <= prev["MACD_Signal"]:
                score += 7.5; alasan.append("MACD Golden Cross")
            if last["MACD_Hist"] > prev["MACD_Hist"]:
                score += 7.5; alasan.append("MACD Histogram Growing")
            if last["Volume"] > vol_sma20 * 1.2:
                score += 10; alasan.append("Volume Spike (>1.2x MA20)")
            if 50 <= last["RSI"] <= 70:
                score += 7.5; alasan.append(f"RSI Momentum ({last['RSI']:.1f})")
            if last["RSI"] > prev["RSI"]:
                score += 7.5; alasan.append(f"RSI Rising ({prev['RSI']:.1f}->{last['RSI']:.1f})")
            if last["PSAR_Bull"]:
                score += 5; alasan.append("PSAR Konfirmasi Tren Naik")
            if rvol >= 2.5:
                score += 10; alasan.append(f"RVOL Tinggi ({rvol:.1f}x)")
            elif rvol >= 1.5:
                score += 6;  alasan.append(f"RVOL Moderat ({rvol:.1f}x)")
            if vpt_trend_up:
                score += 10; alasan.append("VPT Akumulasi Naik")
            if last["MACD"] < 0 and last["MACD_Hist"] > prev["MACD_Hist"]:
                score += 10; alasan.append("MACD Early Recovery (+10)")
            if last["RSI"] > 75:
                score -= 15; alasan.append(f"RSI Overbought ({last['RSI']:.1f}) -15")
            if mtf_filter and not (last["Supertrend_Dir"] == 1 and curr_price > last["MA50"]):
                return None

        score = min(round(score), 100)
        return {
            "Ticker":  ticker_bersih,
            "Sektor":  sektor_nama,
            "Syariah": syariah_status,
            "Quality": quality_label,
            "Skor":    score,
            "Harga":   int(curr_price),
            "ATR":     last["ATR"],
            "Alasan":  alasan,
            "RSI":     last["RSI"],
        }
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# MODUL UTAMA
# ─────────────────────────────────────────────────────────────────────────────

def run_screening() -> None:
    st.set_page_config(page_title="🔍 Screening Saham Harian", layout="wide")

    saham_list, df_universe = load_universe()
    if not saham_list:
        st.stop()

    # Info sumber data di sidebar
    liquid_aktif = os.path.exists(LIQUID_PATH)
    if liquid_aktif:
        st.sidebar.success(
            f"📋 Universe: **{len(saham_list)} saham** dari `liquid_stocks.csv` ✅"
        )
    else:
        st.sidebar.warning(
            f"📋 Universe: **{len(saham_list)} saham** dari `pre_liquid_stocks.csv` "
            f"⚠️ *(enrichment belum tersedia)*"
        )

    st.markdown("<h4 style='text-align: center;'>Pilih Mode Aplikasi</h4>", unsafe_allow_html=True)
    ui_mode = st.radio(
        "👁️ Tampilan Aplikasi:",
        ["🌱 Mode Praktis (Untuk Pemula)", "💼 Mode Pro (Indikator Lengkap)"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.markdown("---")

    if "Praktis" in ui_mode:
        st.markdown("<h1 style='text-align: center;'>🔍 Asisten Saham Pintar</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Mencarikan saham potensial secara otomatis.</p>", unsafe_allow_html=True)
    else:
        st.markdown("<h1 style='text-align: center;'>🔍 Screening Saham Harian Pro</h1>", unsafe_allow_html=True)

    st.markdown("---")

    with st.expander("📖 Glosarium Istilah (Kamus Trader)"):
        st.markdown("""
        * **Entry:** Rentang harga yang disarankan untuk mulai membeli.
        * **TP (Take Profit):** Target harga untuk merealisasikan keuntungan.
        * **SL (Stop Loss):** Batas toleransi kerugian.
        * **ATR:** Indikator volatilitas harga.
        * **Maks Lot:** Rekomendasi porsi maksimal pembelian yang aman.
        """)

    if "Praktis" in ui_mode:
        st.write("### 1️⃣ Pilih Gaya Beli Anda")
        trade_mode_raw = st.radio(
            "Suka memantau layar setiap hari atau disimpan beberapa hari?",
            ["Day Trading (Beli Pagi, Jual Siang/Sore)", "Swing Trading (Beli & Simpan Beberapa Hari)"],
            horizontal=True,
        )
        trade_mode = "Day Trading" if "Day" in trade_mode_raw else "Swing Trading"
    else:
        st.info(
            "⏰ **Waktu Analisa Optimal:**\n"
            "- **Day Trading:** 09.30 - 11.00 WIB\n"
            "- **Swing Trading:** > 16.00 WIB"
        )
        trade_mode = st.radio("Pilih Strategi Trading:", ["Day Trading", "Swing Trading"], horizontal=True)

    if "Praktis" in ui_mode:
        st.write("### 2️⃣ Kalkulator Keamanan Dana")
        mtf_filter   = True
        sector_boost = True
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            total_modal  = st.number_input("Berapa Total Uang Anda untuk Saham? (Rp):", min_value=1_000_000, value=10_000_000, step=1_000_000)
        with col_m2:
            modal_risiko = st.number_input("Batas maksimal uang yang rela hilang per saham? (Rp):", min_value=10_000, value=100_000, step=50_000)
        batas_alokasi_rp = total_modal * 0.15
        st.success(f"Sistem akan memastikan Anda tidak membeli saham melebihi Rp {format_rp(batas_alokasi_rp)} per saham.")
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
                total_modal  = st.number_input("Total Modal Portofolio (Rp):", min_value=1_000_000, value=100_000_000, step=5_000_000)
            with col_m2:
                modal_risiko = st.number_input("Nominal Maksimal Siap Rugi (Rp):", min_value=10_000, value=1_000_000, step=50_000)
            risiko_persen    = (modal_risiko / total_modal) * 100 if total_modal > 0 else 0
            batas_alokasi_rp = total_modal * 0.15
            st.markdown(f"""
            <div style="background-color:#d4edda; border-left:5px solid #28a745; padding:10px; border-radius:5px;">
                <p style="margin:0; font-size:12px; color:#155724;">
                    Total Modal: <b>Rp {format_rp(total_modal)}</b> |
                    Nominal Siap Rugi (<b>{risiko_persen:.1f}%</b>): <b>Rp {format_rp(modal_risiko)}</b>
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

    if st.button(tombol_cari):
        raw_results    = []
        loading_header = st.empty()
        loading_header.write("### 🔄 Mesin sedang memilah saham. Mohon tunggu...")
        status_text = st.empty()
        progress_bar = st.progress(0)
        total_saham  = len(saham_list)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(process_single_stock, ticker, trade_mode, mtf_filter, df_universe): ticker
                for ticker in saham_list
            }
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                completed += 1
                status_text.text(f"Memeriksa {completed}/{total_saham} saham...")
                progress_bar.progress(completed / total_saham)
                result = future.result()
                if result is not None:
                    raw_results.append(result)

        loading_header.empty()
        status_text.empty()
        progress_bar.empty()

        df_all = pd.DataFrame(raw_results)
        sector_report, leading_sectors = analyze_sector_momentum(df_all)

        final_picks = []
        for stock in raw_results:
            f_score = stock["Skor"]
            if sector_boost and stock["Sektor"] in leading_sectors:
                f_score += 10
                stock["Alasan"].append(f"Sector Hot: {stock['Sektor']}")
            f_score = min(round(f_score), 100)

            sl_mult     = 1.8 if trade_mode == "Day Trading" else 2.5
            atr_sl      = int(stock["Harga"] - (sl_mult * stock["ATR"]))
            max_loss_pct = 0.03 if trade_mode == "Day Trading" else 0.08
            hard_cap_sl = int(stock["Harga"] * (1 - max_loss_pct))
            sl          = max(atr_sl, hard_cap_sl)
            rr_min      = 1.5 if trade_mode == "Day Trading" else 2.0
            tp          = int(stock["Harga"] + (stock["Harga"] - sl) * rr_min)
            rrr         = (tp - stock["Harga"]) / (stock["Harga"] - sl) if stock["Harga"] > sl else 0

            risiko_per_lembar = stock["Harga"] - sl
            if risiko_per_lembar > 0:
                lembar_final = min(modal_risiko / risiko_per_lembar, batas_alokasi_rp / stock["Harga"])
                lot_maksimal = int(lembar_final / 100)
            else:
                lot_maksimal = 0

            pct_risk   = ((stock["Harga"] - sl) / stock["Harga"]) * 100 if stock["Harga"] > 0 else 0
            pct_reward = ((tp - stock["Harga"]) / stock["Harga"]) * 100 if stock["Harga"] > 0 else 0

            if f_score >= 70 and rrr >= 1.4:
                final_picks.append({
                    "Ticker":         stock["Ticker"],
                    "Sektor":         stock["Sektor"],
                    "Skor":           f_score,
                    "Harga_Saat_Ini": int(stock["Harga"]),
                    "Syariah":        stock["Syariah"],
                    "Quality":        stock["Quality"],
                    "Entry":          f"Rp {format_rp(stock['Harga'] * 0.99)} - {format_rp(stock['Harga'])}",
                    "SL":             sl,
                    "TP":             tp,
                    "RRR":            f"{rrr:.1f}x",
                    "Status":         "🔥 FULL SIZING" if f_score >= 85 else "🎯 CICIL SEBAGIAN",
                    "Logic":          " | ".join(stock["Alasan"]),
                    "Lot_Maks":       f"{format_rp(lot_maksimal)} Lot",
                    "Pct_Risk":       f"-{pct_risk:.1f}%",
                    "Pct_Reward":     f"+{pct_reward:.1f}%",
                })

        final_picks.sort(key=lambda x: x["Skor"], reverse=True)
        st.session_state.final_picks    = final_picks[:10]
        st.session_state.sector_report  = sector_report
        st.session_state.pdf_session    = session
        st.session_state.analysis_done  = True

        if any(p["Skor"] >= 85 for p in st.session_state.final_picks):
            play_alert_sound()

    # ── Tampilkan Hasil ────────────────────────────────────────────────────────
    if st.session_state.get("analysis_done", False):
        res      = st.session_state.get("final_picks", [])
        top_3    = res[:3]
        watchlist = res[3:10]

        st.subheader("🌐 Kondisi Pasar Saat Ini")
        c1, c2 = st.columns([2, 1])
        with c1:
            if "sector_report" in st.session_state and not st.session_state.sector_report.empty:
                fig = px.bar(
                    st.session_state.sector_report.reset_index(),
                    x="Sektor", y="Avg_Score",
                    color="Avg_Score", color_continuous_scale="Greens",
                    title="Kekuatan Sektor Saat Ini",
                )
                st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.write("**Sektor Paling Ramai:**")
            if "sector_report" in st.session_state and not st.session_state.sector_report.empty:
                for s in st.session_state.sector_report.index[:3]:
                    st.success(s)

        st.markdown("---")
        st.header("🏆 Pilihan Terbaik Saat Ini" if "Praktis" in ui_mode else f"🏆 Top 3 Prioritas {trade_mode}")

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
            st.warning("Mesin belum menemukan saham yang benar-benar aman saat ini.")

        if watchlist:
            st.markdown("---")
            st.subheader("📋 Daftar Cadangan (Peringkat 4-10)")
            df_watch = pd.DataFrame(watchlist).copy()
            df_watch["SL"] = df_watch.apply(lambda x: f"Rp {format_rp(x['SL'])} ({x['Pct_Risk']})", axis=1)
            df_watch["TP"] = df_watch.apply(lambda x: f"Rp {format_rp(x['TP'])} ({x['Pct_Reward']})", axis=1)
            if "Praktis" in ui_mode:
                df_watch = df_watch.rename(columns={
                    "Sektor": "Industri", "Entry": "Area Beli",
                    "SL": "Jual Rugi (Batas Aman)", "TP": "Jual Untung (Target)",
                })
                kolom_tampil = ["Ticker", "Industri", "Syariah", "Quality", "Area Beli",
                                "Jual Rugi (Batas Aman)", "Jual Untung (Target)", "Lot_Maks", "Status"]
            else:
                kolom_tampil = ["Ticker", "Sektor", "Syariah", "Quality", "Skor",
                                "Status", "Entry", "SL", "TP", "RRR", "Lot_Maks"]
            st.dataframe(df_watch[kolom_tampil], use_container_width=True, hide_index=True)

        st.markdown("<br><hr>", unsafe_allow_html=True)
        st.caption("⚠️ **DISCLAIMER:** Laporan ini dihasilkan otomatis. Bukan rekomendasi beli/jual. Selalu DYOR.")

        tz = pytz.timezone("Asia/Jakarta")
        waktu_cetak_pdf = datetime.now(tz).strftime("%Y%m%d_%H%M")
        pdf_data = export_to_pdf(res, trade_mode, st.session_state.pdf_session, st.session_state.sector_report)
        st.download_button(
            label="📥 UNDUH LAPORAN SCREENING LENGKAP (PDF)",
            data=pdf_data,
            file_name=f"ExpertStockPro_{trade_mode}_{waktu_cetak_pdf}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )


if __name__ == "__main__":
    run_screening()
