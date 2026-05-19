import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import base64
from datetime import datetime
import os
import yfinance as yf
from fpdf import FPDF

from utils.data_loader import (
    get_full_stock_data,
    get_liquid_stocks,
    is_ticker_liquid,
    get_ticker_row,
    PRE_LIQUID_PATH,
)

# ─────────────────────────────────────────────────────────────────────────────
# SANITIZER PDF — hapus semua karakter non-latin-1 sebelum masuk FPDF
# ─────────────────────────────────────────────────────────────────────────────

def _sanitize_pdf(text: str) -> str:
    """
    Ganti karakter Unicode dan emoji ke teks ASCII setara
    agar kompatibel dengan FPDF core fonts (latin-1).
    """
    if not isinstance(text, str):
        text = str(text)

    _MAP = {
        # Dash & quotes
        "\u2014": "-",    # em dash —
        "\u2013": "-",    # en dash –
        "\u2019": "'",    # right single quote
        "\u2018": "'",    # left single quote
        "\u201c": '"',    # left double quote
        "\u201d": '"',    # right double quote
        "\u2026": "...",  # ellipsis …
        # Arrows
        "\u2192": "->",   # →
        "\u2190": "<-",   # ←
        "\u2197": "(naik)",  # ↗
        "\u2198": "(turun)", # ↘
        "\ufe0f": "",     # variation selector (after emoji)
        "\u20e3": "",     # combining enclosing keycap
        # Status emoji
        "\u2705": "[OK]",    # ✅
        "\u274c": "[X]",     # ❌
        "\u26a0": "[!]",     # ⚠
        "\u2b50": "[*]",     # ⭐
        # Colored circles
        "\U0001f7e2": "[+]",  # 🟢
        "\U0001f534": "[-]",  # 🔴
        "\U0001f7e1": "[~]",  # 🟡
        "\U0001f7e0": "[!]",  # 🟠
        # Chart emoji
        "\U0001f4c8": "[UP]",  # 📈
        "\U0001f4c9": "[DN]",  # 📉
        "\U0001f525": "[!!]",  # 🔥
        "\U0001f3af": "[*]",   # 🎯
        "\U0001f4e6": "[BOX]", # 📦
        "\U0001f31f": "[*]",   # 🌟
        "\U0001f528": "[~]",   # 🔨
        "\U0001f4ca": "[=]",   # 📊
        "\U0001f4cb": "[-]",   # 📋
        "\U0001f4f0": "[>]",   # 📰
        "\U0001f4c4": "[PDF]", # 📄
        "\U0001f3e2": "[CO]",  # 🏢
        "\U0001f50d": "[?]",   # 🔍
        "\u26a1": "[!]",       # ⚡
        "\U0001f4c5": "[D]",   # 📅
        "\U0001f3c6": "[#]",   # 🏆
        "\u2714": "[v]",       # ✔
        "\u2718": "[x]",       # ✘
        # Lines / decorative
        "\u2500": "-",   # box drawing light horizontal ─
        "\u2502": "|",   # │
        "\u250c": "+",   # ┌
        "\u2510": "+",   # ┐
        "\u2514": "+",   # └
        "\u2518": "+",   # ┘
        # Math / misc
        "\u00d7": "x",   # ×
        "\u00f7": "/",   # ÷
        "\u2212": "-",   # minus sign −
        "\u00b1": "+/-", # ±
        "\u00b2": "^2",  # ²
        "\u00b3": "^3",  # ³
    }

    for char, repl in _MAP.items():
        text = text.replace(char, repl)

    # Fallback: hapus semua sisa karakter non-latin-1
    return text.encode("latin-1", "replace").decode("latin-1")


# ─────────────────────────────────────────────────────────────────────────────
# KONSTANTA
# ─────────────────────────────────────────────────────────────────────────────
RSI_OVERBOUGHT      = 70
RSI_OVERSOLD        = 30
STOCH_OVERBOUGHT    = 80
STOCH_OVERSOLD      = 20
ADX_TREND_STRONG    = 25
ADX_SIDEWAYS        = 20
VOLUME_SPIKE_RATIO  = 2.0
BB_PERIOD           = 20
BB_STD              = 2
MACD_FAST           = 12
MACD_SLOW           = 26
MACD_SIGNAL         = 9
RSI_PERIOD          = 14
STOCH_K             = 14
STOCH_D             = 3
STOCH_SMOOTH        = 3
ADX_PERIOD          = 14
ATR_PERIOD          = 14
SUPERTREND_DAY_P    = 7     # day trade
SUPERTREND_DAY_M    = 3.0
SUPERTREND_SWING_P  = 10    # swing trade
SUPERTREND_SWING_M  = 3.0
FIB_GOLDEN_LOW      = 0.618
FIB_GOLDEN_HIGH     = 0.786

# Bobot scoring (harus total 100)
W_TREND_EMA         = 15
W_TREND_SUPER       = 10
W_TREND_BB_MID      = 5
W_TREND_SAR         = 5
W_MOM_MACD_CROSS    = 15
W_MOM_MACD_DIV      = 12
W_MOM_RSI_DIV       = 12
W_MOM_RSI_NORM      = 8
W_MOM_STOCH         = 10
W_ENTRY_VOL         = 10
W_ENTRY_FIB         = 8
W_ENTRY_BB          = 7
W_ENTRY_CANDLE      = 7
# Penalti (dikurangkan jika kondisi buruk)
PEN_ADX_WEAK        = 20   # seluruh sinyal trend diabaikan
PEN_VOL_SEPI        = 10
PEN_RSI_OB          = 5
PEN_BB_UPPER        = 5


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: STATUS SYARIAH
# ─────────────────────────────────────────────────────────────────────────────

def get_syariah_status(ticker_bersih: str) -> str:
    """Lookup status syariah dari liquid_stocks.csv atau pre_liquid_stocks.csv."""
    liquid_df = get_liquid_stocks()
    row = get_ticker_row(ticker_bersih, liquid_df)
    if row is None:
        try:
            df_pre = pd.read_csv(PRE_LIQUID_PATH, sep=None, engine="python")
            row = get_ticker_row(ticker_bersih, df_pre)
        except Exception:
            row = None
    if row is not None and "Syariah" in row.index:
        val = str(row["Syariah"]).strip().lower()
        if val in ("ya", "yes", "true", "1"):
            return "✅ Syariah"
    return "✖️ Non-Syariah"


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: TERJEMAHAN SEKTOR
# ─────────────────────────────────────────────────────────────────────────────

def translate_sector(sector_en: str) -> str:
    """Terjemahkan nama sektor Bahasa Inggris ke Bahasa Indonesia."""
    mapping = {
        "Financial Services":     "Jasa Keuangan",
        "Basic Materials":        "Bahan Baku & Tambang",
        "Energy":                 "Energi",
        "Communication Services": "Telekomunikasi",
        "Consumer Cyclical":      "Konsumsi Siklikal",
        "Consumer Defensive":     "Konsumsi Non-Siklikal",
        "Healthcare":             "Kesehatan",
        "Industrials":            "Industri",
        "Real Estate":            "Properti",
        "Technology":             "Teknologi",
        "Utilities":              "Utilitas",
    }
    return mapping.get(sector_en, sector_en)


# ─────────────────────────────────────────────────────────────────────────────
# STALENESS CHECK — pastikan data candle yang dipakai adalah yang terakhir valid
# ─────────────────────────────────────────────────────────────────────────────

def _get_staleness_info(df: pd.DataFrame) -> dict:
    """
    Periksa apakah candle terakhir di DataFrame adalah data hari ini atau sudah stale.

    Masalah: yfinance kadang mengembalikan candle 'kosong' (Volume=0, OHLC=NaN atau
    sama semua) untuk hari ini jika pasar belum tutup atau hari libur. Ini menyebabkan
    Vol_Ratio = 0.00x dan indikator lain tidak akurat.

    Solusi:
    - Temukan candle terakhir yang Volume-nya > 0 dan Close tidak NaN.
    - Hitung selisih hari kalender antara candle valid terakhir vs hari ini.
    - Return dict dengan candle valid idx, jumlah hari stale, dan label warning.
    """
    today = pd.Timestamp.now().normalize()

    # Pastikan index bertipe datetime
    try:
        idx = pd.to_datetime(df.index).normalize()
    except Exception:
        idx = df.index

    # Cari baris terakhir dengan Volume > 0 dan Close tidak NaN
    valid_mask = (df['Volume'] > 0) & (df['Close'].notna()) & (df['Close'] > 0)
    valid_rows = df[valid_mask]

    if valid_rows.empty:
        # Fallback absolut: pakai baris terakhir apapun kondisinya
        last_valid_idx  = len(df) - 1
        last_valid_date = today
        stale_days      = 0
    else:
        last_valid_iloc = df.index.get_loc(valid_rows.index[-1])
        # get_loc bisa return slice jika ada duplikat — ambil int terakhir
        if isinstance(last_valid_iloc, slice):
            last_valid_iloc = last_valid_iloc.stop - 1
        elif hasattr(last_valid_iloc, '__len__'):
            last_valid_iloc = int(np.where(last_valid_iloc)[0][-1])
        last_valid_idx  = int(last_valid_iloc)
        try:
            last_valid_date = pd.to_datetime(valid_rows.index[-1]).normalize()
        except Exception:
            last_valid_date = today
        delta           = today - last_valid_date
        stale_days      = max(0, delta.days)

    # Label warning
    if stale_days == 0:
        warning = None
        label   = "Data terkini (hari ini)"
    elif stale_days == 1:
        warning = "⚠️ Data 1 hari lalu — pasar tutup kemarin (libur/weekend). Analisa berdasarkan candle terakhir yang valid."
        label   = f"Candle terakhir: {last_valid_date.strftime('%d %b %Y')} (1 hari lalu)"
    else:
        warning = (
            f"⚠️ Data {stale_days} hari lalu — pasar telah tutup selama {stale_days} hari "
            f"(libur panjang/weekend). Semua indikator dihitung dari candle terakhir yang valid "
            f"({last_valid_date.strftime('%d %b %Y')}). Volume Ratio dan sinyal intraday "
            f"tidak mencerminkan kondisi pasar saat ini."
        )
        label   = f"Candle terakhir: {last_valid_date.strftime('%d %b %Y')} ({stale_days} hari lalu)"

    return {
        "last_valid_iloc": last_valid_idx,
        "last_valid_date": last_valid_date,
        "stale_days":      stale_days,
        "warning":         warning,
        "label":           label,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ANALISA SENTIMEN BERITA
# ─────────────────────────────────────────────────────────────────────────────

def analyze_news_sentiment(ticker_symbol: str) -> tuple:
    """Analisa sentimen dari 5 berita terbaru yfinance."""
    try:
        tk   = yf.Ticker(ticker_symbol)
        news = tk.news
        if not news:
            return "Netral", "Tidak ada berita terbaru."

        bullish_words = [
            'laba', 'naik', 'tumbuh', 'akuisisi', 'dividen', 'ekspansi',
            'profit', 'bullish', 'lonjak', 'target', 'beli', 'buy',
            'investasi', 'positif',
        ]
        bearish_words = [
            'rugi', 'turun', 'anjlok', 'gagal', 'susut', 'bearish',
            'jual', 'sell', 'koreksi', 'denda', 'kasus', 'gugat',
            'inflasi', 'negatif',
        ]

        score = 0
        latest_title = news[0].get('title', 'Berita tidak tersedia')

        for n in news[:5]:
            title_lower = n.get('title', '').lower()
            for bw in bullish_words:
                if bw in title_lower:
                    score += 1
            for bear_w in bearish_words:
                if bear_w in title_lower:
                    score -= 1

        if score > 0:
            return "Positif", latest_title
        elif score < 0:
            return "Negatif", latest_title
        else:
            return "Netral", latest_title
    except Exception:
        return "Netral", "Gagal memuat berita."


# ─────────────────────────────────────────────────────────────────────────────
# KALKULASI INDIKATOR TEKNIKAL
# ─────────────────────────────────────────────────────────────────────────────

def _calc_supertrend(df: pd.DataFrame, period: int, multiplier: float) -> pd.Series:
    """Hitung Supertrend; return Series: True = Bullish, False = Bearish."""
    high   = df['High']
    low    = df['Low']
    close  = df['Close']

    # ATR
    hl  = high - low
    hc  = (high - close.shift()).abs()
    lc  = (low  - close.shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()

    hl2      = (high + low) / 2
    upper_b  = hl2 + multiplier * atr
    lower_b  = hl2 - multiplier * atr

    supertrend = pd.Series(index=df.index, dtype=float)
    direction  = pd.Series(index=df.index, dtype=bool)   # True = bullish

    for i in range(1, len(df)):
        prev_up = upper_b.iloc[i - 1]
        prev_lo = lower_b.iloc[i - 1]
        prev_cl = close.iloc[i - 1]

        upper_b.iloc[i] = (
            upper_b.iloc[i]
            if upper_b.iloc[i] < prev_up or prev_cl > prev_up
            else prev_up
        )
        lower_b.iloc[i] = (
            lower_b.iloc[i]
            if lower_b.iloc[i] > prev_lo or prev_cl < prev_lo
            else prev_lo
        )

        prev_dir = direction.iloc[i - 1] if i > 1 else True
        if prev_dir is False and close.iloc[i] > upper_b.iloc[i]:
            direction.iloc[i] = True
        elif prev_dir is True and close.iloc[i] < lower_b.iloc[i]:
            direction.iloc[i] = False
        else:
            direction.iloc[i] = prev_dir

        supertrend.iloc[i] = lower_b.iloc[i] if direction.iloc[i] else upper_b.iloc[i]

    return direction, supertrend


def _detect_candlestick(df: pd.DataFrame) -> str:
    """Deteksi pola candlestick satu dan dua candle terakhir."""
    if len(df) < 2:
        return "Normal"

    last = df.iloc[-1]
    prev = df.iloc[-2]

    o, h, l, c = last['Open'], last['High'], last['Low'], last['Close']
    po, ph, pl, pc = prev['Open'], prev['High'], prev['Low'], prev['Close']

    body     = abs(c - o)
    rng      = h - l
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l

    if rng == 0:
        return "Normal"

    # Doji
    if body <= rng * 0.1:
        return "Doji ⚠️"

    # Hammer (bullish)
    if (lower_shadow >= body * 2) and (upper_shadow <= body * 0.3) and (c > o):
        return "Hammer 🔨 (Bullish Reversal)"

    # Shooting Star (bearish)
    if (upper_shadow >= body * 2) and (lower_shadow <= body * 0.3) and (c < o):
        return "Shooting Star ⭐ (Bearish Reversal)"

    # Bullish Engulfing
    if (pc < po) and (c > o) and (c > po) and (o < pc):
        return "Bullish Engulfing 🟢 (Kuat Bullish)"

    # Bearish Engulfing
    if (pc > po) and (c < o) and (c < po) and (o > pc):
        return "Bearish Engulfing 🔴 (Kuat Bearish)"

    # Morning Star (butuh 3 candle)
    if len(df) >= 3:
        prev2 = df.iloc[-3]
        if (prev2['Close'] < prev2['Open']
                and abs(pc - po) <= (ph - pl) * 0.3
                and c > o and c > (prev2['Open'] + prev2['Close']) / 2):
            return "Morning Star 🌟 (Bullish Reversal Kuat)"

    # Inside Bar
    if (h < ph) and (l > pl):
        return "Inside Bar 📦 (Konsolidasi / Breakout Siap)"

    if c > o:
        return "Bullish Candle 🟢"
    elif c < o:
        return "Bearish Candle 🔴"
    return "Normal"


def _detect_macd_divergence(df: pd.DataFrame, lookback: int = 20) -> str:
    """Deteksi divergensi MACD vs harga dalam N candle terakhir."""
    if len(df) < lookback:
        return "Tidak Terdeteksi"

    sub       = df.tail(lookback)
    price_now = sub['Close'].iloc[-1]
    macd_now  = sub['MACD'].iloc[-1]
    price_low = sub['Close'].min()
    macd_low  = sub['MACD'].min()

    # Bullish divergence: harga buat lower low, MACD tidak
    price_idx_low = sub['Close'].idxmin()
    macd_idx_low  = sub['MACD'].idxmin()
    if (price_now < sub['Close'].iloc[0]
            and macd_now > sub['MACD'].iloc[0]
            and price_now < price_low * 1.01):
        return "Divergensi Bullish 📈 (Potensi Reversal Naik)"

    # Bearish divergence: harga buat higher high, MACD tidak
    price_high = sub['Close'].max()
    macd_high  = sub['MACD'].max()
    if (price_now > sub['Close'].iloc[0]
            and macd_now < sub['MACD'].iloc[0]
            and price_now > price_high * 0.99):
        return "Divergensi Bearish 📉 (Potensi Reversal Turun)"

    return "Tidak Terdeteksi"


def _detect_rsi_divergence(df: pd.DataFrame, lookback: int = 20) -> str:
    """Deteksi divergensi RSI vs harga."""
    if len(df) < lookback:
        return "Tidak Terdeteksi"

    sub       = df.tail(lookback)
    price_now = sub['Close'].iloc[-1]
    rsi_now   = sub['RSI'].iloc[-1]

    if (price_now < sub['Close'].iloc[0] and rsi_now > sub['RSI'].iloc[0]):
        return "Divergensi Bullish 📈"
    if (price_now > sub['Close'].iloc[0] and rsi_now < sub['RSI'].iloc[0]):
        return "Divergensi Bearish 📉"
    return "Tidak Terdeteksi"


def _calc_fibonacci(df: pd.DataFrame, lookback: int = 60) -> dict:
    """Hitung level Fibonacci dari swing high/low N candle terakhir."""
    sub       = df.tail(lookback)
    swing_high = sub['High'].max()
    swing_low  = sub['Low'].min()
    diff      = swing_high - swing_low

    levels = {
        "0.0":   swing_high,
        "0.236": swing_high - 0.236 * diff,
        "0.382": swing_high - 0.382 * diff,
        "0.5":   swing_high - 0.5   * diff,
        "0.618": swing_high - 0.618 * diff,
        "0.786": swing_high - 0.786 * diff,
        "1.0":   swing_low,
    }
    return levels, swing_high, swing_low


def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Hitung semua indikator teknikal untuk satu DataFrame (daily atau intraday).
    Return DataFrame dengan kolom-kolom indikator ditambahkan.
    """
    df = df.copy()

    # ── EMA ──────────────────────────────────────────────────────────────────
    df['EMA9']   = df['Close'].ewm(span=9,   adjust=False).mean()
    df['EMA20']  = df['Close'].ewm(span=20,  adjust=False).mean()
    df['EMA50']  = df['Close'].ewm(span=50,  adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()

    # ── MA (SMA) ─────────────────────────────────────────────────────────────
    df['MA20']   = df['Close'].rolling(20).mean()

    # ── BOLLINGER BANDS ───────────────────────────────────────────────────────
    df['BB_Mid']   = df['MA20']
    df['BB_Std']   = df['Close'].rolling(BB_PERIOD).std()
    df['BB_Upper'] = df['BB_Mid'] + BB_STD * df['BB_Std']
    df['BB_Lower'] = df['BB_Mid'] - BB_STD * df['BB_Std']
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Mid']

    # ── RSI ───────────────────────────────────────────────────────────────────
    delta = df['Close'].diff()
    gain  = delta.where(delta > 0, 0).rolling(RSI_PERIOD).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
    rs    = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))

    # ── MACD ──────────────────────────────────────────────────────────────────
    exp1           = df['Close'].ewm(span=MACD_FAST,   adjust=False).mean()
    exp2           = df['Close'].ewm(span=MACD_SLOW,   adjust=False).mean()
    df['MACD']        = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=MACD_SIGNAL, adjust=False).mean()
    df['MACD_Hist']   = df['MACD'] - df['Signal_Line']

    # ── STOCHASTIC (14,3,3) ───────────────────────────────────────────────────
    lo14       = df['Low'].rolling(STOCH_K).min()
    hi14       = df['High'].rolling(STOCH_K).max()
    raw_k      = 100 * (df['Close'] - lo14) / (hi14 - lo14).replace(0, np.nan)
    df['Stoch_K'] = raw_k.rolling(STOCH_SMOOTH).mean()
    df['Stoch_D'] = df['Stoch_K'].rolling(STOCH_D).mean()

    # ── ATR ───────────────────────────────────────────────────────────────────
    hl  = df['High'] - df['Low']
    hc  = (df['High'] - df['Close'].shift()).abs()
    lc  = (df['Low']  - df['Close'].shift()).abs()
    df['ATR'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(ATR_PERIOD).mean()

    # ── ADX / DMI ─────────────────────────────────────────────────────────────
    up_move   = df['High'].diff()
    down_move = -df['Low'].diff()
    plus_dm   = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm  = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    tr_raw    = pd.concat([hl, hc, lc], axis=1).max(axis=1)

    atr_adx   = tr_raw.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean()
    plus_di   = 100 * pd.Series(plus_dm,  index=df.index).ewm(alpha=1 / ADX_PERIOD, adjust=False).mean() / atr_adx
    minus_di  = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / ADX_PERIOD, adjust=False).mean() / atr_adx
    dx        = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    df['ADX']      = dx.ewm(alpha=1 / ADX_PERIOD, adjust=False).mean()
    df['Plus_DI']  = plus_di
    df['Minus_DI'] = minus_di

    # ── OBV ───────────────────────────────────────────────────────────────────
    direction_obv = np.sign(df['Close'].diff()).fillna(0)
    df['OBV']     = (direction_obv * df['Volume']).cumsum()

    # ── VWAP (rolling 20 periode — proxy untuk daily/intraday) ────────────────
    typical        = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP_20']  = (
        (typical * df['Volume']).rolling(20).sum()
        / df['Volume'].rolling(20).sum()
    )

    # ── VOLUME ────────────────────────────────────────────────────────────────
    df['Vol_MA20']     = df['Volume'].rolling(20).mean()
    df['Vol_Ratio']    = df['Volume'] / df['Vol_MA20'].replace(0, np.nan)

    # ── VALUE (Close × Volume) untuk likuiditas ───────────────────────────────
    df['Value']        = df['Close'] * df['Volume']
    df['Value_MA20']   = df['Value'].rolling(20).mean()

    # ── PARABOLIC SAR (implementasi manual) ───────────────────────────────────
    af_start = 0.02
    af_max   = 0.20
    sar      = [df['Low'].iloc[0]]
    ep       = [df['High'].iloc[0]]
    af       = [af_start]
    bull     = [True]

    for i in range(1, len(df)):
        prev_bull = bull[i - 1]
        prev_sar  = sar[i - 1]
        prev_ep   = ep[i - 1]
        prev_af   = af[i - 1]

        new_sar = prev_sar + prev_af * (prev_ep - prev_sar)

        if prev_bull:
            new_sar = min(new_sar, df['Low'].iloc[i - 1],
                          df['Low'].iloc[i - 2] if i >= 2 else df['Low'].iloc[i - 1])
            if df['Low'].iloc[i] < new_sar:
                bull.append(False)
                sar.append(prev_ep)
                ep.append(df['Low'].iloc[i])
                af.append(af_start)
            else:
                bull.append(True)
                sar.append(new_sar)
                new_ep = max(prev_ep, df['High'].iloc[i])
                ep.append(new_ep)
                af.append(min(prev_af + af_start if new_ep > prev_ep else prev_af, af_max))
        else:
            new_sar = max(new_sar, df['High'].iloc[i - 1],
                          df['High'].iloc[i - 2] if i >= 2 else df['High'].iloc[i - 1])
            if df['High'].iloc[i] > new_sar:
                bull.append(True)
                sar.append(prev_ep)
                ep.append(df['High'].iloc[i])
                af.append(af_start)
            else:
                bull.append(False)
                sar.append(new_sar)
                new_ep = min(prev_ep, df['Low'].iloc[i])
                ep.append(new_ep)
                af.append(min(prev_af + af_start if new_ep < prev_ep else prev_af, af_max))

    df['SAR']      = sar
    df['SAR_Bull'] = bull   # True = harga di atas SAR (bullish)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# SISTEM SCORING (BERLAPIS)
# ─────────────────────────────────────────────────────────────────────────────

def compute_score(df: pd.DataFrame, timeframe: str = "swing") -> dict:
    """
    Hitung skor teknikal berlapis (0–100) dan kembalikan dict berisi:
    - score, label, warna, go_nogo, detail per layer, simpulan SL/TP
    Timeframe: 'day' atau 'swing' (mempengaruhi parameter Supertrend).
    Candle yang digunakan selalu candle terakhir yang VALID (Volume>0, Close tidak NaN),
    bukan selalu iloc[-1] — untuk menghindari candle kosong hari libur/weekend.
    """
    # ── Gunakan candle terakhir yang valid, bukan selalu iloc[-1] ────────────
    staleness   = _get_staleness_info(df)
    valid_iloc  = staleness["last_valid_iloc"]

    # Pastikan ada minimal 2 candle valid sebelum valid_iloc untuk prev1 & prev5
    last  = df.iloc[valid_iloc]
    prev1 = df.iloc[max(0, valid_iloc - 1)]
    prev5 = df.iloc[max(0, valid_iloc - 5)]

    result = {
        "layer1_filter": {},
        "layer2_trend":  {},
        "layer3_momentum": {},
        "layer4_entry":  {},
        "score_raw":     0,
        "score":         0,
        "go_nogo":       True,
        "nogo_reason":   [],
        "staleness":     staleness,   # info candle stale untuk ditampilkan di UI
    }

    curr_price = last['Close']
    atr_val    = last['ATR']

    # ─────────────────────────────────────────────────────────────────────
    # SUPERTREND (hitung per call karena parameter beda per timeframe)
    # ─────────────────────────────────────────────────────────────────────
    st_period = SUPERTREND_DAY_P if timeframe == "day" else SUPERTREND_SWING_P
    st_mult   = SUPERTREND_DAY_M if timeframe == "day" else SUPERTREND_SWING_M
    st_dir, st_line = _calc_supertrend(df, st_period, st_mult)
    super_bull = bool(st_dir.iloc[-1])
    super_prev = bool(st_dir.iloc[-2]) if len(st_dir) > 1 else super_bull
    if super_bull and not super_prev:
        super_label = "Baru Crossover Bullish 🟢"
    elif not super_bull and super_prev:
        super_label = "Baru Crossover Bearish 🔴"
    elif super_bull:
        super_label = "Bullish 🟢"
    else:
        super_label = "Bearish 🔴"

    # ─────────────────────────────────────────────────────────────────────
    # FIBONACCI
    # ─────────────────────────────────────────────────────────────────────
    fib_levels, fib_high, fib_low = _calc_fibonacci(df)
    fib_618 = fib_levels["0.618"]
    fib_786 = fib_levels["0.786"]
    in_golden_zone = fib_786 <= curr_price <= fib_618

    # ─────────────────────────────────────────────────────────────────────
    # LAYER 1 — FILTER (GO / NO-GO)
    # ─────────────────────────────────────────────────────────────────────
    adx_val   = last['ADX']
    vol_ratio = last['Vol_Ratio']

    adx_ok  = adx_val >= ADX_SIDEWAYS
    vol_ok  = vol_ratio >= 0.8

    result["layer1_filter"]["ADX"] = {
        "nilai": f"{adx_val:.1f}",
        "label": (
            f"Trend Kuat Bullish (+DI>{last['Plus_DI']:.1f})" if adx_val >= ADX_TREND_STRONG and last['Plus_DI'] > last['Minus_DI']
            else f"Trend Kuat Bearish (-DI>{last['Minus_DI']:.1f})" if adx_val >= ADX_TREND_STRONG
            else f"Melemah ({adx_val:.1f} ↓)" if adx_val >= ADX_SIDEWAYS
            else f"Sideways/Ranging ⚠️ ({adx_val:.1f})"
        ),
        "ok": adx_ok,
    }
    result["layer1_filter"]["Volume"] = {
        "nilai": f"{vol_ratio:.2f}x",
        "label": (
            "Spike 🔥" if vol_ratio >= VOLUME_SPIKE_RATIO
            else "Normal ✅" if vol_ratio >= 1.0
            else "Sepi ⚠️"
        ),
        "ok": vol_ok,
    }

    if not adx_ok:
        result["go_nogo"]  = False
        result["nogo_reason"].append(
            f"ADX {adx_val:.1f} < {ADX_SIDEWAYS} — pasar sedang sideways, sinyal trend tidak valid."
        )
    if not vol_ok:
        result["go_nogo"]  = False
        result["nogo_reason"].append(
            f"Volume ratio {vol_ratio:.2f}x terlalu sepi — sinyal tidak terkonfirmasi volume."
        )

    # ─────────────────────────────────────────────────────────────────────
    # LAYER 2 — TREND CONFIRMATION (35 poin)
    # ─────────────────────────────────────────────────────────────────────
    score_trend = 0

    # EMA Stack (gradasi)
    ema_full_bull  = curr_price > last['EMA9'] > last['EMA20'] > last['EMA50'] > last['EMA200']
    ema_part_bull1 = curr_price > last['EMA20'] > last['EMA50']
    ema_part_bull2 = curr_price > last['EMA50']
    ema_full_bear  = curr_price < last['EMA9'] < last['EMA20'] < last['EMA50'] < last['EMA200']
    ema_part_bear1 = curr_price < last['EMA20'] < last['EMA50']

    if ema_full_bull:
        ema_pts, ema_label = W_TREND_EMA, "Full Bullish Alignment ✅ (Harga > EMA9 > 20 > 50 > 200)"
    elif ema_part_bull1:
        ema_pts, ema_label = 10, "Partial Bullish ✅ (Harga > EMA20 > EMA50)"
    elif ema_part_bull2:
        ema_pts, ema_label = 5, "Lemah Bullish (Harga > EMA50)"
    elif ema_full_bear:
        ema_pts, ema_label = -W_TREND_EMA, "Full Bearish Alignment 🔴 (Harga < EMA9 < 20 < 50 < 200)"
    elif ema_part_bear1:
        ema_pts, ema_label = -10, "Partial Bearish 🔴 (Harga < EMA20 < EMA50)"
    else:
        ema_pts, ema_label = 0, "Choppy/Mixed ⚠️"

    score_trend += ema_pts
    result["layer2_trend"]["EMA_Stack"] = {"poin": ema_pts, "label": ema_label}

    # Supertrend
    st_pts = W_TREND_SUPER if super_bull else -W_TREND_SUPER
    score_trend += st_pts
    result["layer2_trend"]["Supertrend"] = {
        "poin": st_pts,
        "label": super_label,
        "param": f"({st_period},{st_mult})",
    }

    # Harga vs BB Mid (SMA20)
    bb_mid_bull = curr_price > last['BB_Mid']
    bb_mid_pts  = W_TREND_BB_MID if bb_mid_bull else -W_TREND_BB_MID
    score_trend += bb_mid_pts
    result["layer2_trend"]["BB_Mid"] = {
        "poin": bb_mid_pts,
        "label": f"{'Di atas' if bb_mid_bull else 'Di bawah'} SMA20 ({last['BB_Mid']:,.0f})",
    }

    # Parabolic SAR
    sar_bull = bool(last['SAR_Bull'])
    sar_prev = bool(df.iloc[-2]['SAR_Bull'])
    if sar_bull and not sar_prev:
        sar_label = "Baru Flip Bullish 🟢"
    elif not sar_bull and sar_prev:
        sar_label = "Baru Flip Bearish 🔴"
    elif sar_bull:
        sar_label = f"Bullish 🟢 (SAR: {last['SAR']:,.0f})"
    else:
        sar_label = f"Bearish 🔴 (SAR: {last['SAR']:,.0f})"
    sar_pts = W_TREND_SAR if sar_bull else -W_TREND_SAR
    score_trend += sar_pts
    result["layer2_trend"]["Parabolic_SAR"] = {"poin": sar_pts, "label": sar_label}

    result["layer2_trend"]["_total"] = score_trend

    # ─────────────────────────────────────────────────────────────────────
    # LAYER 3 — MOMENTUM (40 poin)
    # ─────────────────────────────────────────────────────────────────────
    score_mom = 0

    # MACD
    macd_cross_bull  = (last['MACD'] > last['Signal_Line']) and (prev1['MACD'] <= prev1['Signal_Line'])
    macd_cross_bear  = (last['MACD'] < last['Signal_Line']) and (prev1['MACD'] >= prev1['Signal_Line'])
    macd_bull        = last['MACD'] > last['Signal_Line']
    macd_div         = _detect_macd_divergence(df)
    macd_div_bull    = "Bullish" in macd_div
    macd_div_bear    = "Bearish" in macd_div

    if macd_cross_bull:
        macd_pts, macd_label = W_MOM_MACD_CROSS, "Bullish Crossover Baru 🟢"
    elif macd_cross_bear:
        macd_pts, macd_label = -W_MOM_MACD_CROSS, "Bearish Crossover Baru 🔴"
    elif macd_div_bull:
        macd_pts, macd_label = W_MOM_MACD_DIV, macd_div
    elif macd_div_bear:
        macd_pts, macd_label = -W_MOM_MACD_DIV, macd_div
    elif macd_bull:
        macd_pts, macd_label = 8, "Bullish Momentum ✅"
    else:
        macd_pts, macd_label = -8, "Bearish Momentum 🔴"

    score_mom += macd_pts
    result["layer3_momentum"]["MACD"] = {
        "poin": macd_pts, "label": macd_label,
        "nilai": f"MACD:{last['MACD']:.3f} | Signal:{last['Signal_Line']:.3f} | Hist:{last['MACD_Hist']:.3f}",
    }

    # RSI
    rsi_val  = last['RSI']
    rsi_prev = prev1['RSI']
    rsi_div  = _detect_rsi_divergence(df)

    if "Divergensi Bullish" in rsi_div:
        rsi_pts, rsi_label = W_MOM_RSI_DIV, rsi_div
    elif "Divergensi Bearish" in rsi_div:
        rsi_pts, rsi_label = -W_MOM_RSI_DIV, rsi_div
    elif rsi_val > RSI_OVERBOUGHT:
        rsi_pts, rsi_label = -PEN_RSI_OB, f"Overbought ⚠️ ({rsi_val:.1f})"
    elif rsi_val < RSI_OVERSOLD:
        rsi_pts, rsi_label = 5, f"Oversold — Potensi Reversal ({rsi_val:.1f})"
    elif 40 <= rsi_val <= 60:
        arah_rsi = "↗️ Naik" if rsi_val > rsi_prev else "↘️ Turun"
        rsi_pts, rsi_label = W_MOM_RSI_NORM, f"Normal ({rsi_val:.1f} {arah_rsi})"
    else:
        arah_rsi = "↗️" if rsi_val > rsi_prev else "↘️"
        rsi_pts, rsi_label = 4, f"Netral ({rsi_val:.1f} {arah_rsi})"

    score_mom += rsi_pts
    result["layer3_momentum"]["RSI"] = {"poin": rsi_pts, "label": rsi_label}

    # Stochastic
    k_val    = last['Stoch_K']
    d_val    = last['Stoch_D']
    k_prev   = prev1['Stoch_K']
    d_prev   = prev1['Stoch_D']
    stoch_bull_cross = (k_val > d_val) and (k_prev <= d_prev)
    stoch_bear_cross = (k_val < d_val) and (k_prev >= d_prev)

    if stoch_bull_cross and k_val < STOCH_OVERSOLD + 10:
        stoch_pts, stoch_label = W_MOM_STOCH, f"Bullish Crossover dari Oversold 🟢 (%K:{k_val:.1f})"
    elif stoch_bear_cross and k_val > STOCH_OVERBOUGHT - 10:
        stoch_pts, stoch_label = -W_MOM_STOCH, f"Bearish Crossover dari Overbought 🔴 (%K:{k_val:.1f})"
    elif stoch_bull_cross:
        stoch_pts, stoch_label = 6, f"Bullish Crossover (%K:{k_val:.1f})"
    elif stoch_bear_cross:
        stoch_pts, stoch_label = -6, f"Bearish Crossover (%K:{k_val:.1f})"
    elif k_val > STOCH_OVERBOUGHT:
        stoch_pts, stoch_label = -3, f"Overbought ⚠️ (%K:{k_val:.1f})"
    elif k_val < STOCH_OVERSOLD:
        stoch_pts, stoch_label = 3, f"Oversold — Waspada (%K:{k_val:.1f})"
    else:
        stoch_pts, stoch_label = 0, f"Netral (%K:{k_val:.1f} | %D:{d_val:.1f})"

    score_mom += stoch_pts
    result["layer3_momentum"]["Stochastic"] = {"poin": stoch_pts, "label": stoch_label}

    result["layer3_momentum"]["_total"] = score_mom

    # ─────────────────────────────────────────────────────────────────────
    # LAYER 4 — ENTRY TRIGGER & KONTEKS (25 poin)
    # ─────────────────────────────────────────────────────────────────────
    score_entry = 0

    # Volume spike searah trend
    vol_spike = vol_ratio >= VOLUME_SPIKE_RATIO
    if vol_spike and (curr_price > prev1['Close']):
        vol_pts, vol_label = W_ENTRY_VOL, f"Volume Spike Bullish 🔥 ({vol_ratio:.1f}x)"
    elif vol_spike and (curr_price < prev1['Close']):
        vol_pts, vol_label = -W_ENTRY_VOL, f"Volume Spike Bearish 🔴 ({vol_ratio:.1f}x)"
    else:
        vol_pts, vol_label = 0, f"Volume Normal ({vol_ratio:.2f}x)"
    score_entry += vol_pts
    result["layer4_entry"]["Volume_Spike"] = {"poin": vol_pts, "label": vol_label}

    # Fibonacci Golden Zone
    if in_golden_zone:
        fib_pts, fib_label = W_ENTRY_FIB, f"Di Golden Zone 0.618–0.786 🎯 ({fib_786:,.0f}–{fib_618:,.0f})"
    elif curr_price < fib_786:
        fib_pts, fib_label = 4, f"Di bawah Golden Zone (Support Kuat)"
    elif curr_price > fib_618:
        fib_pts, fib_label = -4, f"Di atas Golden Zone (Resistance Area)"
    else:
        fib_pts, fib_label = 0, f"Di luar Golden Zone"
    score_entry += fib_pts
    result["layer4_entry"]["Fibonacci"] = {
        "poin": fib_pts, "label": fib_label,
        "levels": fib_levels,
    }

    # Bollinger Bands
    bb_width_curr = last['BB_Width']
    bb_width_avg  = df['BB_Width'].mean()
    squeeze       = bb_width_curr < bb_width_avg * 0.7
    at_upper      = curr_price >= last['BB_Upper'] * 0.99
    at_lower      = curr_price <= last['BB_Lower'] * 1.01

    if squeeze:
        bb_pts, bb_label = W_ENTRY_BB - 2, "Squeeze 📦 — Breakout Imminent"
    elif at_lower:
        bb_pts, bb_label = W_ENTRY_BB, f"Di Lower Band ({last['BB_Lower']:,.0f}) — Potensi Oversold"
    elif at_upper:
        bb_pts, bb_label = -PEN_BB_UPPER, f"Di Upper Band ({last['BB_Upper']:,.0f}) — Resistance"
    else:
        pos_pct = ((curr_price - last['BB_Lower']) / (last['BB_Upper'] - last['BB_Lower']) * 100) if (last['BB_Upper'] - last['BB_Lower']) > 0 else 50
        bb_pts, bb_label = 0, f"Di tengah band ({pos_pct:.0f}% dari bawah)"
    score_entry += bb_pts
    result["layer4_entry"]["Bollinger_Bands"] = {
        "poin": bb_pts, "label": bb_label,
        "upper": last['BB_Upper'], "lower": last['BB_Lower'], "mid": last['BB_Mid'],
    }

    # Candlestick pattern
    candle_pattern = _detect_candlestick(df)
    bullish_patterns = ["Hammer", "Bullish Engulfing", "Morning Star", "Bullish Candle"]
    bearish_patterns = ["Shooting Star", "Bearish Engulfing", "Bearish Candle"]
    is_bull_candle = any(p in candle_pattern for p in bullish_patterns)
    is_bear_candle = any(p in candle_pattern for p in bearish_patterns)

    if is_bull_candle:
        candle_pts = W_ENTRY_CANDLE
    elif is_bear_candle:
        candle_pts = -W_ENTRY_CANDLE
    else:
        candle_pts = 0
    score_entry += candle_pts
    result["layer4_entry"]["Candlestick"] = {"poin": candle_pts, "label": candle_pattern}

    result["layer4_entry"]["_total"] = score_entry

    # ─────────────────────────────────────────────────────────────────────
    # TOTAL SKOR (clamp ke -100 … +100)
    # ─────────────────────────────────────────────────────────────────────
    raw = score_trend + score_mom + score_entry
    result["score_raw"] = raw

    # Jika filter gagal, skor tidak dihitung penuh
    if not result["go_nogo"]:
        # Tetap hitung tapi beri penalti besar
        raw = min(raw - PEN_ADX_WEAK, 0) if not adx_ok else raw
        raw = raw - PEN_VOL_SEPI if not vol_ok else raw

    score_final = max(-100, min(100, raw))
    result["score"] = score_final

    # ─────────────────────────────────────────────────────────────────────
    # SIMPULAN & LABEL
    # ─────────────────────────────────────────────────────────────────────
    if not result["go_nogo"]:
        result["label"]  = "KONDISI TIDAK IDEAL"
        result["warna"]  = "#9E9E9E"
        result["signal"] = "TUNGGU — Kondisi Pasar Belum Mendukung"
        result["confidence"] = " | ".join(result["nogo_reason"])
    elif score_final >= 65:
        result["label"]  = "STRONG BUY"
        result["warna"]  = "#00C853"
        result["signal"] = "STRONG BUY — Konfirmasi Tinggi"
        result["confidence"] = "Mayoritas indikator selaras bullish. Entry dapat dipertimbangkan sesuai trading plan."
    elif score_final >= 35:
        result["label"]  = "BUY"
        result["warna"]  = "#69F0AE"
        result["signal"] = "BUY — Konfirmasi Cukup"
        result["confidence"] = "Sinyal beli dengan konfirmasi memadai. Tetap gunakan stop loss ketat."
    elif score_final >= 10:
        result["label"]  = "WATCH"
        result["warna"]  = "#FFD600"
        result["signal"] = "WATCH — Bias Bullish Lemah"
        result["confidence"] = "Belum ideal untuk entry. Pantau konfirmasi tambahan sebelum masuk."
    elif score_final >= -9:
        result["label"]  = "NEUTRAL"
        result["warna"]  = "#9E9E9E"
        result["signal"] = "NEUTRAL — Tidak Ada Sinyal Jelas"
        result["confidence"] = "Indikator saling bertentangan. Tunggu kejelasan arah."
    elif score_final >= -34:
        result["label"]  = "CAUTION"
        result["warna"]  = "#FF6D00"
        result["signal"] = "CAUTION — Bias Bearish"
        result["confidence"] = "Tekanan jual mendominasi. Hindari entry beli baru."
    elif score_final >= -64:
        result["label"]  = "SELL/AVOID"
        result["warna"]  = "#D50000"
        result["signal"] = "SELL / AVOID"
        result["confidence"] = "Sinyal bearish kuat. Jika pegang posisi, pertimbangkan exit."
    else:
        result["label"]  = "STRONG SELL"
        result["warna"]  = "#B71C1C"
        result["signal"] = "STRONG SELL — Konfirmasi Tinggi"
        result["confidence"] = "Tekanan jual sangat dominan. Exit posisi dan hindari buy."

    # ─────────────────────────────────────────────────────────────────────
    # PARAMETER SL & TP (berbasis ATR)
    # ─────────────────────────────────────────────────────────────────────
    if timeframe == "day":
        sl_mult_buy  = 1.5
        tp1_mult     = 1.5
        tp2_mult     = 3.0
    else:
        sl_mult_buy  = 2.0
        tp1_mult     = 2.0
        tp2_mult     = 4.0

    entry_price = curr_price
    sl  = entry_price - sl_mult_buy * atr_val
    tp1 = entry_price + tp1_mult    * atr_val
    tp2 = entry_price + tp2_mult    * atr_val

    result["trading_plan"] = {
        "entry":  entry_price,
        "sl":     sl,
        "tp1":    tp1,
        "tp2":    tp2,
        "atr":    atr_val,
        "atr_pct": (atr_val / entry_price * 100) if entry_price > 0 else 0,
        "sl_pct": ((entry_price - sl) / entry_price * 100) if entry_price > 0 else 0,
        "tp1_pct": ((tp1 - entry_price) / entry_price * 100) if entry_price > 0 else 0,
        "tp2_pct": ((tp2 - entry_price) / entry_price * 100) if entry_price > 0 else 0,
        "rr1":    tp1_mult / sl_mult_buy,
        "rr2":    tp2_mult / sl_mult_buy,
    }

    # ─────────────────────────────────────────────────────────────────────
    # INFO TAMBAHAN (untuk tabel panel)
    # ─────────────────────────────────────────────────────────────────────
    result["info"] = {
        "price":         curr_price,
        "vwap":          last.get('VWAP_20', curr_price),
        "value_ma20":    last.get('Value_MA20', 0),
        "vol_ratio":     vol_ratio,
        "adx":           adx_val,
        "plus_di":       last['Plus_DI'],
        "minus_di":      last['Minus_DI'],
        "rsi":           rsi_val,
        "macd":          last['MACD'],
        "signal_line":   last['Signal_Line'],
        "macd_hist":     last['MACD_Hist'],
        "stoch_k":       k_val,
        "stoch_d":       d_val,
        "atr":           atr_val,
        "atr_pct":       (atr_val / curr_price * 100) if curr_price > 0 else 0,
        "bb_upper":      last['BB_Upper'],
        "bb_mid":        last['BB_Mid'],
        "bb_lower":      last['BB_Lower'],
        "bb_width":      bb_width_curr,
        "ema9":          last['EMA9'],
        "ema20":         last['EMA20'],
        "ema50":         last['EMA50'],
        "ema200":        last['EMA200'],
        "sar":           last['SAR'],
        "sar_bull":      sar_bull,
        "super_bull":    super_bull,
        "super_line":    float(st_line.iloc[valid_iloc]),
        "obv":           last['OBV'],
        "obv_prev":      df['OBV'].iloc[max(0, valid_iloc - 5)],
        "candle":        candle_pattern,
        "fib_high":      fib_high,
        "fib_low":       fib_low,
        "fib_levels":    fib_levels,
        "in_golden":     in_golden_zone,
        "stale_days":    staleness["stale_days"],
        "stale_label":   staleness["label"],
        "stale_warning": staleness["warning"],
    }

    return result


# ─────────────────────────────────────────────────────────────────────────────
# CHART BUILDER — 2 panel: harga+EMA (atas) + Volume (bawah)
# ─────────────────────────────────────────────────────────────────────────────

def build_chart(df: pd.DataFrame, sc: dict, ticker: str, timeframe_label: str) -> go.Figure:
    """
    Bangun chart 2 panel:
    - Row 1 (70%): Candlestick + EMA9/20/50/200
    - Row 2 (30%): Volume bar + Vol MA20
    """
    info        = sc["info"]
    stale_days  = info.get("stale_days", 0)
    stale_label = info.get("stale_label", "")

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.72, 0.28],
        subplot_titles=(
            f"{ticker} — {timeframe_label}"
            + (f"  |  ⚠ {stale_label}" if stale_days > 0 else ""),
            "Volume",
        ),
    )

    # ── Row 1: Candlestick ────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'], high=df['High'],
        low=df['Low'],   close=df['Close'],
        name="Harga",
        increasing_line_color="#00C853",
        decreasing_line_color="#D50000",
        increasing_fillcolor="#00C853",
        decreasing_fillcolor="#D50000",
    ), row=1, col=1)

    # EMA 9 / 20 / 50 / 200
    ema_styles = [
        ('EMA9',   '#F9A825', 1.2, 'solid'),
        ('EMA20',  '#00BCD4', 1.5, 'solid'),
        ('EMA50',  '#FF7043', 1.5, 'solid'),
        ('EMA200', '#CE93D8', 2.0, 'solid'),
    ]
    for col_name, color, width, dash in ema_styles:
        if col_name in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col_name],
                line=dict(color=color, width=width, dash=dash),
                name=col_name, opacity=0.95,
            ), row=1, col=1)

    # Tandai candle terakhir yang valid jika data stale
    if stale_days > 0:
        valid_iloc  = sc["staleness"]["last_valid_iloc"]
        valid_date  = df.index[valid_iloc]
        valid_close = df['Close'].iloc[valid_iloc]
        fig.add_trace(go.Scatter(
            x=[valid_date],
            y=[valid_close],
            mode='markers',
            marker=dict(color='#FFD600', size=10, symbol='diamond',
                        line=dict(color='#FFFFFF', width=1.5)),
            name=f'Candle Terakhir Valid ({stale_label})',
            showlegend=True,
        ), row=1, col=1)

    # ── Row 2: Volume ─────────────────────────────────────────────────────────
    vol_colors = [
        '#00C853' if c >= o else '#D50000'
        for c, o in zip(df['Close'], df['Open'])
    ]
    fig.add_trace(go.Bar(
        x=df.index, y=df['Volume'],
        marker_color=vol_colors,
        name='Volume', opacity=0.65,
    ), row=2, col=1)

    if 'Vol_MA20' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df['Vol_MA20'],
            line=dict(color='#FFD600', width=1.5),
            name='Vol MA20',
        ), row=2, col=1)

    last_vol_ma20 = df['Vol_MA20'].dropna().iloc[-1] if 'Vol_MA20' in df.columns else None
    if last_vol_ma20:
        fig.add_hline(
            y=last_vol_ma20, row=2, col=1,
            line=dict(color='rgba(255,214,0,0.3)', width=1, dash='dot'),
        )

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_layout(
        height=620,
        template="plotly_dark",
        paper_bgcolor="#0D1117",
        plot_bgcolor="#0D1117",
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(size=10),
            bgcolor="rgba(13,17,23,0.7)",
        ),
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
    )

    for ax in ['xaxis', 'xaxis2', 'yaxis', 'yaxis2']:
        fig.update_layout(**{ax: dict(
            gridcolor='rgba(255,255,255,0.05)',
            zerolinecolor='rgba(255,255,255,0.1)',
        )})

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# TAMPILAN PANEL INDIKATOR (tabel ringkas)
# ─────────────────────────────────────────────────────────────────────────────

def _row_indikator(label: str, nilai: str, simpulan: str, warna_simpulan: str = "#FFFFFF"):
    """Render satu baris tabel indikator dengan warna simpulan."""
    st.markdown(
        f"""
        <div style='display:grid;grid-template-columns:160px 140px 1fr;
                    gap:8px;padding:6px 4px;border-bottom:1px solid #1E2A3A;
                    font-size:13px;align-items:center;'>
            <div style='color:#90CAF9;font-weight:600;'>{label}</div>
            <div style='color:#E0E0E0;font-family:monospace;'>{nilai}</div>
            <div style='color:{warna_simpulan};'>{simpulan}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_indicator_panel(sc: dict, df: pd.DataFrame):
    """Render seluruh panel indikator teknikal (selalu tampil, apapun skornya)."""
    info = sc["info"]
    l2   = sc["layer2_trend"]
    l3   = sc["layer3_momentum"]
    l4   = sc["layer4_entry"]
    l1   = sc["layer1_filter"]

    curr = info['price']

    st.markdown("#### 📊 Panel Indikator Teknikal Lengkap")

    stale_days  = info.get("stale_days", 0)
    stale_label = info.get("stale_label", "")
    if stale_days > 0:
        st.markdown(
            f"<div style='background:#1A2A1A;border:1px solid #FFD600;border-radius:4px;"
            f"padding:6px 10px;font-size:12px;color:#FFD600;margin-bottom:8px;'>"
            f"⚠️ <b>Acuan analisa:</b> {stale_label} — "
            f"semua indikator dihitung dari candle terakhir yang valid (Volume &gt; 0)."
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div style='background:#0D1B0D;border:1px solid #00C853;border-radius:4px;"
            f"padding:6px 10px;font-size:12px;color:#00C853;margin-bottom:8px;'>"
            f"✅ <b>Acuan analisa:</b> Data terkini hari ini."
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<div style='display:grid;grid-template-columns:160px 140px 1fr;"
        "gap:8px;padding:4px;background:#0D1B2A;border-radius:4px;"
        "font-size:11px;color:#607D8B;font-weight:700;'>"
        "<div>INDIKATOR</div><div>NILAI</div><div>SIMPULAN</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='color:#607D8B;font-size:11px;padding:6px 4px 2px;font-weight:700;'>── FILTER (GO/NO-GO) ──</div>", unsafe_allow_html=True)

    adx_ok  = l1["ADX"]["ok"]
    vol_ok  = l1["Volume"]["ok"]
    _row_indikator(
        "ADX/DMI (14)",
        f"{info['adx']:.1f} | +DI:{info['plus_di']:.1f} | -DI:{info['minus_di']:.1f}",
        l1["ADX"]["label"],
        "#00C853" if adx_ok else "#FF5252",
    )
    _row_indikator(
        "Volume Ratio",
        l1["Volume"]["nilai"],
        l1["Volume"]["label"],
        "#00C853" if vol_ok else "#FF5252",
    )
    _row_indikator(
        "Likuiditas",
        f"Rp {info['value_ma20']:,.0f}",
        f"{'✅ Likuid' if info['value_ma20'] > 0 else '⚠️ Cek Manual'}",
        "#00C853" if info['value_ma20'] > 1_000_000_000 else "#FFD600",
    )

    st.markdown("<div style='color:#607D8B;font-size:11px;padding:6px 4px 2px;font-weight:700;'>── TREND CONFIRMATION ──</div>", unsafe_allow_html=True)

    ema_poin = l2["EMA_Stack"]["poin"]
    _row_indikator(
        "EMA 9/20/50/200",
        f"9:{info['ema9']:,.0f} | 20:{info['ema20']:,.0f} | 50:{info['ema50']:,.0f} | 200:{info['ema200']:,.0f}",
        l2["EMA_Stack"]["label"],
        "#00C853" if ema_poin > 0 else ("#FF5252" if ema_poin < 0 else "#9E9E9E"),
    )
    st_poin = l2["Supertrend"]["poin"]
    _row_indikator(
        f"Supertrend {l2['Supertrend']['param']}",
        f"{info['super_line']:,.0f}",
        l2["Supertrend"]["label"],
        "#00C853" if st_poin > 0 else "#FF5252",
    )
    sar_poin = l2["Parabolic_SAR"]["poin"]
    _row_indikator(
        "Parabolic SAR",
        f"{info['sar']:,.0f}",
        l2["Parabolic_SAR"]["label"],
        "#00C853" if sar_poin > 0 else "#FF5252",
    )
    bb_mid_poin = l2["BB_Mid"]["poin"]
    _row_indikator(
        "Harga vs SMA20",
        f"Harga:{curr:,.0f} | SMA20:{info['bb_mid']:,.0f}",
        l2["BB_Mid"]["label"],
        "#00C853" if bb_mid_poin > 0 else "#FF5252",
    )

    vwap_bull = curr > info['vwap']
    _row_indikator(
        "VWAP (20 periode)",
        f"{info['vwap']:,.0f}",
        f"{'Di Atas VWAP ✅' if vwap_bull else 'Di Bawah VWAP ⚠️'}",
        "#00C853" if vwap_bull else "#FF6D00",
    )

    st.markdown("<div style='color:#607D8B;font-size:11px;padding:6px 4px 2px;font-weight:700;'>── MOMENTUM CONFIRMATION ──</div>", unsafe_allow_html=True)

    macd_poin = l3["MACD"]["poin"]
    _row_indikator(
        "MACD (12,26,9)",
        l3["MACD"]["nilai"],
        l3["MACD"]["label"],
        "#00C853" if macd_poin > 0 else ("#FF5252" if macd_poin < 0 else "#9E9E9E"),
    )
    rsi_poin = l3["RSI"]["poin"]
    _row_indikator(
        "RSI (14)",
        f"{info['rsi']:.1f}",
        l3["RSI"]["label"],
        "#00C853" if rsi_poin > 0 else ("#FF5252" if rsi_poin < 0 else "#9E9E9E"),
    )
    stoch_poin = l3["Stochastic"]["poin"]
    _row_indikator(
        "Stochastic (14,3,3)",
        f"%K:{info['stoch_k']:.1f} | %D:{info['stoch_d']:.1f}",
        l3["Stochastic"]["label"],
        "#00C853" if stoch_poin > 0 else ("#FF5252" if stoch_poin < 0 else "#9E9E9E"),
    )

    obv_up = info['obv'] > info['obv_prev']
    _row_indikator(
        "OBV (Volume Flow)",
        f"{info['obv']:,.0f}",
        f"{'OBV Naik — Akumulasi ✅' if obv_up else 'OBV Turun — Distribusi ⚠️'}",
        "#00C853" if obv_up else "#FF6D00",
    )

    st.markdown("<div style='color:#607D8B;font-size:11px;padding:6px 4px 2px;font-weight:700;'>── ENTRY TRIGGER & KONTEKS ──</div>", unsafe_allow_html=True)

    bb_poin  = l4["Bollinger_Bands"]["poin"]
    fib_poin = l4["Fibonacci"]["poin"]
    _row_indikator(
        "Bollinger Bands (20,2)",
        f"Upper:{info['bb_upper']:,.0f} | Mid:{info['bb_mid']:,.0f} | Lower:{info['bb_lower']:,.0f}",
        l4["Bollinger_Bands"]["label"],
        "#00C853" if bb_poin > 0 else ("#FF5252" if bb_poin < 0 else "#9E9E9E"),
    )
    _row_indikator(
        "Fibonacci",
        f"H:{info['fib_high']:,.0f} | L:{info['fib_low']:,.0f}",
        l4["Fibonacci"]["label"],
        "#00C853" if fib_poin > 0 else ("#FF5252" if fib_poin < 0 else "#9E9E9E"),
    )
    _row_indikator(
        "Candlestick",
        "—",
        info['candle'],
        "#00C853" if l4["Candlestick"]["poin"] > 0 else (
            "#FF5252" if l4["Candlestick"]["poin"] < 0 else "#9E9E9E"),
    )
    vol_poin = l4["Volume_Spike"]["poin"]
    _row_indikator(
        "Volume Spike",
        l1["Volume"]["nilai"],
        l4["Volume_Spike"]["label"],
        "#00C853" if vol_poin > 0 else ("#FF5252" if vol_poin < 0 else "#9E9E9E"),
    )

    _row_indikator(
        "ATR% (Volatilitas)",
        f"ATR: {info['atr']:,.0f} ({info['atr_pct']:.2f}%)",
        (
            "Volatilitas Rendah (<1%)" if info['atr_pct'] < 1
            else "Volatilitas Normal (1–3%)" if info['atr_pct'] < 3
            else "Volatilitas Tinggi (>3%) ⚠️"
        ),
        "#9E9E9E" if info['atr_pct'] < 1 else ("#00C853" if info['atr_pct'] < 3 else "#FF6D00"),
    )

    st.markdown("<br>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TRADING PLAN SECTION
# ─────────────────────────────────────────────────────────────────────────────

def render_trading_plan(sc: dict, total_modal: float, max_risiko: float):
    """Render Trading Plan dan Position Sizing. Selalu tampil apapun skornya."""
    plan  = sc["trading_plan"]
    score = sc["score"]
    label = sc["label"]
    warna = sc["warna"]

    st.markdown("---")
    st.markdown("#### 📋 Trading Plan & Position Sizing")

    st.markdown(
        f"""
        <div style='text-align:center;padding:16px;background:#0D1B2A;
                    border-radius:8px;border:2px solid {warna};margin-bottom:16px;'>
            <div style='font-size:36px;font-weight:900;color:{warna};'>{label}</div>
            <div style='font-size:18px;color:#E0E0E0;margin-top:4px;'>Skor: {score}/100</div>
            <div style='font-size:13px;color:#90CAF9;margin-top:8px;'>{sc["confidence"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if sc["go_nogo"] is False or score < 10:
        st.error(
            "🚨 **Kondisi Tidak Ideal untuk Entry** — Semua data indikator di atas "
            "tetap ditampilkan untuk referensi analisa. Trading plan di bawah "
            "**hanya sebagai ilustrasi** dan tidak direkomendasikan untuk dieksekusi saat ini."
        )
        st.markdown("---")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Entry (Harga Saat Ini)", f"Rp {plan['entry']:,.0f}")
    with c2:
        st.metric(
            "🛑 Stop Loss",
            f"Rp {plan['sl']:,.0f}",
            delta=f"-{plan['sl_pct']:.1f}%",
            delta_color="inverse",
        )
    with c3:
        st.metric("🎯 Target 1 (R:R 1:1)",  f"Rp {plan['tp1']:,.0f}",
                  delta=f"+{plan['tp1_pct']:.1f}%")

    c4, c5, c6 = st.columns(3)
    with c4:
        st.metric("🎯 Target 2 (R:R 1:2)",  f"Rp {plan['tp2']:,.0f}",
                  delta=f"+{plan['tp2_pct']:.1f}%")
    with c5:
        st.metric("ATR Saat Ini", f"{plan['atr']:,.0f} ({plan['atr_pct']:.2f}%)")
    with c6:
        st.metric("Risk/Reward", f"1:{plan['rr1']:.1f} / 1:{plan['rr2']:.1f}")

    if plan['entry'] > 0 and plan['sl'] > 0:
        risk_per_share     = plan['entry'] - plan['sl']
        max_lembar_risk    = (max_risiko / risk_per_share) if risk_per_share > 0 else 0
        max_lembar_capital = (0.15 * total_modal) / plan['entry']
        final_lot          = int(min(max_lembar_risk, max_lembar_capital) // 100)

        st.info(
            f"💡 **Position Sizing** — Modal: Rp {total_modal:,.0f} | "
            f"Maks Risiko: Rp {max_risiko:,.0f}"
        )
        p1, p2, p3 = st.columns(3)
        with p1:
            st.metric("Risk-Based Limit", f"{int(max_lembar_risk):,.0f} lembar")
            st.caption("Batas dari toleransi kerugian")
        with p2:
            st.metric("Capital-Based (15%)", f"{int(max_lembar_capital):,.0f} lembar")
            st.caption("Batas hindari all-in")
        with p3:
            if score >= 35:
                st.success(f"**MAX LOT: {final_lot} LOT**")
            else:
                st.warning(f"**MAX LOT: {final_lot} LOT** *(tidak direkomendasikan saat ini)*")
            st.caption("Angka paling konservatif")
    else:
        max_lembar_risk = max_lembar_capital = 0
        final_lot = 0

    return {
        "max_lembar_risk":    max_lembar_risk if plan['entry'] > 0 else 0,
        "max_lembar_capital": max_lembar_capital if plan['entry'] > 0 else 0,
        "final_lot":          final_lot,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GENERATOR PDF
# PERBAIKAN: Hapus "from fpdf.enums import XPos, YPos" — tidak kompatibel
# dengan fpdf v1.x yang mungkin terinstall di Streamlit Cloud lama.
# Ganti XPos.LMARGIN → "LMARGIN" dan YPos.NEXT → "NEXT" (string enum
# yang didukung fpdf2 >= 2.2 tanpa perlu import fpdf.enums).
# ─────────────────────────────────────────────────────────────────────────────

def generate_pdf_fpdf(data: dict, logo_path: str = "logo_expert_stock_pro.png") -> bytes:
    """
    Bangun PDF laporan analisa teknikal menggunakan fpdf2.
    Kompatibel dengan fpdf2 >= 2.2 tanpa import fpdf.enums.
    """
    # ── shortcut sanitizer ────────────────────────────────────────────────────
    def s(text) -> str:
        return _sanitize_pdf(str(text) if text is not None else "-")

    # ── layout konstanta ──────────────────────────────────────────────────────
    LM     = 10      # left margin mm
    RM     = 10      # right margin mm
    PW     = 210     # page width mm
    C1     = 44      # kolom label mm
    C2     = 48      # kolom nilai mm
    C3     = PW - LM - RM - C1 - C2   # kolom simpulan (~98mm)
    RH     = 5       # row height mm

    # ── helper: satu baris tabel 3-kolom ─────────────────────────────────────
    def row2(label_txt: str, val_txt, simpulan_txt):
        """
        Cetak baris: label | nilai | simpulan.
        Gunakan set_xy() eksplisit agar multi_cell kolom-3 tidak crash.
        """
        y0 = pdf.get_y()
        pdf.set_font("Helvetica", 'B', 9)
        pdf.set_xy(LM, y0)
        pdf.cell(C1, RH, s(label_txt))
        pdf.set_font("Helvetica", '', 9)
        pdf.set_xy(LM + C1, y0)
        pdf.cell(C2, RH, s(str(val_txt)))
        pdf.set_xy(LM + C1 + C2, y0)
        pdf.multi_cell(C3, RH, s(str(simpulan_txt)))

    # ── helper: header section ────────────────────────────────────────────────
    def section_header(title: str):
        pdf.set_fill_color(30, 42, 58)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", 'B', 10)
        # String enum "LMARGIN"/"NEXT" — bekerja di fpdf2 >= 2.2 tanpa import fpdf.enums
        pdf.cell(0, 7, s(title), new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", '', 9)

    # ── helper: cell dengan newline ───────────────────────────────────────────
    def cnl(w, h, txt, **kw):
        pdf.cell(w, h, s(txt), new_x="LMARGIN", new_y="NEXT", **kw)

    # ── init ──────────────────────────────────────────────────────────────────
    pdf = FPDF()
    pdf.set_margins(LM, 10, RM)
    pdf.add_page()

    syariah_raw = s(data.get('syariah', ''))
    status_syariah_teks = "Syariah" if "Syariah" in syariah_raw and "Non" not in syariah_raw else "Non-Syariah"

    # ── HEADER ────────────────────────────────────────────────────────────────
    pdf.set_fill_color(13, 17, 23)
    pdf.rect(0, 0, 210, 28, 'F')

    if not os.path.exists(logo_path) and os.path.exists("../logo_expert_stock_pro.png"):
        logo_path = "../logo_expert_stock_pro.png"
    if os.path.exists(logo_path):
        pdf.set_fill_color(218, 165, 32)
        pdf.rect(10, 4, 18, 18, 'F')
        pdf.image(logo_path, x=10.5, y=4.5, w=17, h=17)

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", 'B', 14)
    pdf.set_xy(33, 10)
    pdf.cell(0, 8, "Expert Stock Pro - Analisa Teknikal Pro")
    pdf.set_y(30)

    pdf.set_font("Helvetica", 'I', 9)
    pdf.set_text_color(0, 102, 204)
    cnl(0, 5, "Sumber: https://s.id/pintarsaham", align='C')
    pdf.ln(1)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", 'B', 16)
    cnl(0, 9, s(f"{data.get('ticker','?')} - {data.get('nama_perusahaan','')}"), align='C')

    pdf.set_font("Helvetica", '', 10)
    cnl(0, 5, s(f"Sektor: {data.get('sektor','-')} | Status: {status_syariah_teks}"), align='C')

    pdf.set_font("Helvetica", 'B', 9)
    cnl(0, 5,
        s(f"Analisa: {data.get('waktu','-')} | TF: {data.get('timeframe','-')} | "
          f"Harga: Rp {data.get('harga', 0):,.0f}"),
        align='R')

    pdf.line(LM, pdf.get_y() + 1, PW - RM, pdf.get_y() + 1)
    pdf.ln(4)

    # ── SKOR & SIMPULAN ───────────────────────────────────────────────────────
    score = data.get('score', 0)
    label = data.get('label', '-')
    warna_map = {
        "STRONG BUY":          (0, 200, 83),
        "BUY":                 (105, 240, 174),
        "WATCH":               (255, 214, 0),
        "NEUTRAL":             (158, 158, 158),
        "CAUTION":             (255, 109, 0),
        "SELL/AVOID":          (213, 0, 0),
        "STRONG SELL":         (183, 28, 28),
        "KONDISI TIDAK IDEAL": (100, 100, 100),
    }
    r, g, b = warna_map.get(label, (100, 100, 100))

    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", 'B', 13)
    cnl(0, 10, s(f"SKOR TEKNIKAL: {score}/100  |  {label}"), fill=True, align='C')

    pdf.set_font("Helvetica", 'I', 9)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(0, 5, s(f"Catatan: {data.get('confidence','-')}"))
    pdf.ln(2)

    # ── LAYER 1 ───────────────────────────────────────────────────────────────
    section_header("1. FILTER (GO / NO-GO)")
    l1 = data.get('layer1', {})
    row2("ADX/DMI (14)",  l1.get('adx_nilai', '-'), l1.get('adx_label', '-'))
    row2("Volume Ratio",  l1.get('vol_nilai', '-'),  l1.get('vol_label', '-'))
    row2("Likuiditas",    l1.get('liq_nilai', '-'),  l1.get('liq_label', '-'))
    pdf.ln(2)

    # ── LAYER 2 ───────────────────────────────────────────────────────────────
    section_header("2. TREND CONFIRMATION")
    l2 = data.get('layer2', {})
    row2("EMA Stack",      l2.get('ema_nilai', '-'),   l2.get('ema_label', '-'))
    row2("Supertrend",     l2.get('super_nilai', '-'), l2.get('super_label', '-'))
    row2("Parabolic SAR",  l2.get('sar_nilai', '-'),   l2.get('sar_label', '-'))
    row2("Harga vs SMA20", l2.get('sma_nilai', '-'),   l2.get('sma_label', '-'))
    row2("VWAP (20)",      l2.get('vwap_nilai', '-'),  l2.get('vwap_label', '-'))
    pdf.ln(2)

    # ── LAYER 3 ───────────────────────────────────────────────────────────────
    section_header("3. MOMENTUM CONFIRMATION")
    l3 = data.get('layer3', {})
    row2("MACD (12,26,9)",      l3.get('macd_nilai', '-'),  l3.get('macd_label', '-'))
    row2("RSI (14)",            l3.get('rsi_nilai', '-'),   l3.get('rsi_label', '-'))
    row2("Stochastic (14,3,3)", l3.get('stoch_nilai', '-'), l3.get('stoch_label', '-'))
    row2("OBV",                 l3.get('obv_nilai', '-'),   l3.get('obv_label', '-'))
    pdf.ln(2)

    # ── LAYER 4 ───────────────────────────────────────────────────────────────
    section_header("4. ENTRY TRIGGER & KONTEKS")
    l4 = data.get('layer4', {})
    row2("Bollinger Bands", l4.get('bb_nilai', '-'),      l4.get('bb_label', '-'))
    row2("Fibonacci",       l4.get('fib_nilai', '-'),     l4.get('fib_label', '-'))
    row2("Candlestick",     "-",                           l4.get('candle_label', '-'))
    row2("Volume Spike",    l1.get('vol_nilai', '-'),      l4.get('volspike_label', '-'))
    row2("ATR%",            l4.get('atr_nilai', '-'),      l4.get('atr_label', '-'))
    pdf.ln(2)

    # ── TRADING PLAN ──────────────────────────────────────────────────────────
    section_header("5. TRADING PLAN & POSITION SIZING")
    plan = data.get('plan', {})

    if score < 10:
        pdf.set_font("Helvetica", 'I', 9)
        pdf.set_text_color(180, 0, 0)
        pdf.multi_cell(0, 5,
            "Trading plan berikut adalah ILUSTRASI - tidak direkomendasikan "
            "untuk dieksekusi karena skor teknikal belum memadai.")
        pdf.set_text_color(0, 0, 0)

    row2("Harga Entry",    f"Rp {plan.get('entry', 0):,.0f}", "-")
    row2("Stop Loss",      f"Rp {plan.get('sl', 0):,.0f}",
         f"-{plan.get('sl_pct', 0):.1f}% dari entry")
    row2("Target 1 (TP1)", f"Rp {plan.get('tp1', 0):,.0f}",
         f"+{plan.get('tp1_pct', 0):.1f}% | R:R 1:{plan.get('rr1', 0):.1f}")
    row2("Target 2 (TP2)", f"Rp {plan.get('tp2', 0):,.0f}",
         f"+{plan.get('tp2_pct', 0):.1f}% | R:R 1:{plan.get('rr2', 0):.1f}")
    row2("ATR",
         f"{plan.get('atr', 0):,.0f} ({plan.get('atr_pct', 0):.2f}%)",
         "Dasar perhitungan SL dan TP")
    pdf.ln(2)

    pdf.set_font("Helvetica", 'B', 9)
    cnl(0, 5, "POSITION SIZING")
    row2("Modal",               f"Rp {data.get('total_modal', 0):,.0f}",                 "-")
    row2("Maks Risiko",         f"Rp {data.get('max_risiko', 0):,.0f}",                  "-")
    row2("Risk-Based Limit",    f"{int(data.get('max_lembar_risk', 0)):,.0f} lembar",    "-")
    row2("Capital-Based (15%)", f"{int(data.get('max_lembar_capital', 0)):,.0f} lembar", "-")
    row2("FINAL MAX LOT",       f"{data.get('final_lot', 0)} LOT",
         "Angka paling konservatif")
    pdf.ln(2)

    # ── SENTIMEN ──────────────────────────────────────────────────────────────
    section_header("6. SENTIMEN BERITA")
    cnl(0, 5, s(f"Status: {data.get('sentiment', '-')}"))
    pdf.multi_cell(0, 5, s(f"Headline: {data.get('headline', '-')}"))
    pdf.ln(8)

    # ── DISCLAIMER ────────────────────────────────────────────────────────────
    pdf.line(LM, pdf.get_y(), PW - RM, pdf.get_y())
    pdf.set_font("Helvetica", 'I', 7)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 4,
        "DISCLAIMER: Laporan ini dihasilkan secara otomatis menggunakan algoritma "
        "indikator teknikal. Bukan merupakan ajakan, rekomendasi pasti, atau paksaan "
        "untuk membeli/menjual saham. Keputusan investasi sepenuhnya menjadi tanggung "
        "jawab pribadi investor. Selalu terapkan manajemen risiko dan DYOR.")

    # fpdf2: output() return bytes langsung
    return pdf.output()


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_teknikal():
    """Entry point modul analisa teknikal — dipanggil dari app.py."""

    # ── LOGO ──────────────────────────────────────────────────────────────────
    logo_file = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_file):
        logo_file = "../logo_expert_stock_pro.png"
    if os.path.exists(logo_file):
        with open(logo_file, "rb") as f:
            encoded_img = base64.b64encode(f.read()).decode()
        st.markdown(
            f'<div style="display:flex;justify-content:center;margin-bottom:10px;">'
            f'<img src="data:image/png;base64,{encoded_img}" width="150"></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        "<h1 style='text-align:center;'>📈 Analisa Teknikal Pro</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:#90CAF9;'>Sistem Scoring Berlapis: "
        "Filter → Trend → Momentum → Entry Trigger</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── INPUT ─────────────────────────────────────────────────────────────────
    st.markdown("### ⚙️ Input & Manajemen Risiko")
    col_inp, col_mod, col_rsk = st.columns([1, 1, 1])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Contoh: BBRI):", value="BBRI").upper()
    with col_mod:
        total_modal_input = st.number_input(
            "Total Modal Investasi (Rp):",
            min_value=100_000, value=10_000_000, step=1_000_000, format="%d",
        )
    with col_rsk:
        max_risiko_input = st.number_input(
            "Maks Risiko / Kerugian (Rp):",
            min_value=10_000, value=250_000, step=50_000, format="%d",
        )

    ticker_bersih = ticker_input.strip().upper().replace(".JK", "")
    ticker_jk     = ticker_bersih + ".JK"

    if not st.button(f"🔍 Jalankan Analisa {ticker_bersih}", type="primary"):
        st.info("Masukkan kode saham dan klik tombol untuk menjalankan analisa.")
        return

    # ── FETCH DATA ────────────────────────────────────────────────────────────
    with st.spinner("Mengambil data..."):
        data_daily = get_full_stock_data(ticker_jk, interval="1d")
        df_daily   = data_daily.get('history', pd.DataFrame())
        info       = data_daily.get('info', {})

        try:
            tk_obj  = yf.Ticker(ticker_jk)
            df_m15  = tk_obj.history(period="60d", interval="15m")
            df_m15.index = df_m15.index.tz_localize(None) if df_m15.index.tzinfo else df_m15.index
        except Exception:
            df_m15 = pd.DataFrame()

    if df_daily.empty or len(df_daily) < 60:
        st.error("Data harian tidak mencukupi. Coba ticker lain.")
        return

    # ── KALKULASI ─────────────────────────────────────────────────────────────
    with st.spinner("Menghitung semua indikator..."):
        df_daily_calc = calculate_technical_indicators(df_daily)

        m15_ok = not df_m15.empty and len(df_m15) >= 50
        if m15_ok:
            df_m15_calc = calculate_technical_indicators(df_m15)
        else:
            df_m15_calc = None

        sc_swing = compute_score(df_daily_calc, timeframe="swing")
        sc_day   = compute_score(df_m15_calc, timeframe="day") if m15_ok else None

    # ── INFO HEADER ───────────────────────────────────────────────────────────
    nama_perusahaan = info.get('longName', ticker_bersih)
    sektor_id       = translate_sector(info.get('sector', 'Sektor Tidak Diketahui'))
    status_syariah  = get_syariah_status(ticker_bersih)
    sentimen_status, sentimen_headline = analyze_news_sentiment(ticker_jk)

    st.markdown(
        f"<h2 style='text-align:center;color:#4ade80;'>"
        f"🏢 {ticker_bersih} — {nama_perusahaan}</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<h5 style='text-align:center;margin-top:-15px;color:#a3a3a3;'>"
        f"Sektor: {sektor_id} | {status_syariah}</h5>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── TAB DAY TRADE vs SWING TRADE ─────────────────────────────────────────
    tab_swing, tab_day = st.tabs(["📅 Swing Trade (Daily)", "⚡ Day Trade (M15)"])

    # ═══════════════════════════════════════════════════════════════
    # TAB SWING TRADE
    # ═══════════════════════════════════════════════════════════════
    with tab_swing:
        st.markdown("##### Timeframe: Daily | Parameter Supertrend (10,3)")

        stale_warn_sw = sc_swing["info"].get("stale_warning")
        if stale_warn_sw:
            st.warning(stale_warn_sw)

        fig_swing = build_chart(df_daily_calc, sc_swing, ticker_bersih, "Daily")
        st.plotly_chart(fig_swing, use_container_width=True)

        render_indicator_panel(sc_swing, df_daily_calc)

        st.markdown("#### 📰 Sentimen Berita")
        if sentimen_status == "Positif":
            st.success(f"**{sentimen_status}** — {sentimen_headline}")
        elif sentimen_status == "Negatif":
            st.error(f"**{sentimen_status}** — {sentimen_headline}")
        else:
            st.info(f"**{sentimen_status}** — {sentimen_headline}")

        ps_swing = render_trading_plan(sc_swing, total_modal_input, max_risiko_input)

        # ── PDF SWING ────────────────────────────────────────────────────────
        st.markdown("---")
        info_sw  = sc_swing["info"]
        plan_sw  = sc_swing["trading_plan"]
        l1_sw    = sc_swing["layer1_filter"]
        l2_sw    = sc_swing["layer2_trend"]
        l3_sw    = sc_swing["layer3_momentum"]
        l4_sw    = sc_swing["layer4_entry"]

        pdf_data_swing = {
            "ticker":           ticker_bersih,
            "nama_perusahaan":  nama_perusahaan,
            "sektor":           sektor_id,
            "syariah":          status_syariah,
            "waktu":            datetime.now().strftime("%d-%m-%Y %H:%M"),
            "timeframe":        "Swing Trade — Daily",
            "harga":            info_sw['price'],
            "score":            sc_swing["score"],
            "label":            sc_swing["label"],
            "confidence":       sc_swing["confidence"],
            "sentiment":        sentimen_status,
            "headline":         sentimen_headline,
            "total_modal":      total_modal_input,
            "max_risiko":       max_risiko_input,
            "max_lembar_risk":  ps_swing["max_lembar_risk"],
            "max_lembar_capital": ps_swing["max_lembar_capital"],
            "final_lot":        ps_swing["final_lot"],
            "plan":             plan_sw,
            "layer1": {
                "adx_nilai":  l1_sw["ADX"]["nilai"],
                "adx_label":  l1_sw["ADX"]["label"],
                "vol_nilai":  l1_sw["Volume"]["nilai"],
                "vol_label":  l1_sw["Volume"]["label"],
                "liq_nilai":  f"Rp {info_sw['value_ma20']:,.0f}",
                "liq_label":  "Likuid" if info_sw['value_ma20'] > 1_000_000_000 else "Cek Manual",
            },
            "layer2": {
                "ema_nilai":   f"EMA9:{info_sw['ema9']:,.0f}|EMA20:{info_sw['ema20']:,.0f}|EMA50:{info_sw['ema50']:,.0f}|EMA200:{info_sw['ema200']:,.0f}",
                "ema_label":   l2_sw["EMA_Stack"]["label"],
                "super_nilai": f"{info_sw['super_line']:,.0f}",
                "super_label": l2_sw["Supertrend"]["label"],
                "sar_nilai":   f"{info_sw['sar']:,.0f}",
                "sar_label":   l2_sw["Parabolic_SAR"]["label"],
                "sma_nilai":   f"Harga:{info_sw['price']:,.0f}|SMA20:{info_sw['bb_mid']:,.0f}",
                "sma_label":   l2_sw["BB_Mid"]["label"],
                "vwap_nilai":  f"{info_sw['vwap']:,.0f}",
                "vwap_label":  "Di Atas VWAP" if info_sw['price'] > info_sw['vwap'] else "Di Bawah VWAP",
            },
            "layer3": {
                "macd_nilai":   l3_sw["MACD"]["nilai"],
                "macd_label":   l3_sw["MACD"]["label"],
                "rsi_nilai":    f"{info_sw['rsi']:.1f}",
                "rsi_label":    l3_sw["RSI"]["label"],
                "stoch_nilai":  f"%K:{info_sw['stoch_k']:.1f}|%D:{info_sw['stoch_d']:.1f}",
                "stoch_label":  l3_sw["Stochastic"]["label"],
                "obv_nilai":    f"{info_sw['obv']:,.0f}",
                "obv_label":    "OBV Naik (Akumulasi)" if info_sw['obv'] > info_sw['obv_prev'] else "OBV Turun (Distribusi)",
            },
            "layer4": {
                "bb_nilai":       f"U:{info_sw['bb_upper']:,.0f}|M:{info_sw['bb_mid']:,.0f}|L:{info_sw['bb_lower']:,.0f}",
                "bb_label":       l4_sw["Bollinger_Bands"]["label"],
                "fib_nilai":      f"H:{info_sw['fib_high']:,.0f}|L:{info_sw['fib_low']:,.0f}",
                "fib_label":      l4_sw["Fibonacci"]["label"],
                "candle_label":   l4_sw["Candlestick"]["label"],
                "volspike_label": l4_sw["Volume_Spike"]["label"],
                "atr_nilai":      f"{info_sw['atr']:,.0f} ({info_sw['atr_pct']:.2f}%)",
                "atr_label":      (
                    "Volatilitas Rendah (<1%)" if info_sw['atr_pct'] < 1
                    else "Volatilitas Normal (1-3%)" if info_sw['atr_pct'] < 3
                    else "Volatilitas Tinggi (>3%)"
                ),
            },
        }

        try:
            pdf_bytes_swing = generate_pdf_fpdf(pdf_data_swing)
            if pdf_bytes_swing:
                st.download_button(
                    label="📄 Unduh Laporan Swing Trade (PDF)",
                    data=pdf_bytes_swing,
                    file_name=f"ESP_Swing_{ticker_bersih}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
        except Exception as e:
            st.warning(f"⚠️ PDF tidak dapat dibuat: {e}")

    # ═══════════════════════════════════════════════════════════════
    # TAB DAY TRADE
    # ═══════════════════════════════════════════════════════════════
    with tab_day:
        st.markdown("##### Timeframe: M15 | Parameter Supertrend (7,3)")

        if not m15_ok or sc_day is None:
            st.warning(
                "⚠️ Data M15 tidak tersedia atau tidak mencukupi untuk ticker ini. "
                "yfinance membatasi data intraday untuk saham IDX. "
                "Gunakan tab Swing Trade sebagai alternatif."
            )
        else:
            stale_warn_dy = sc_day["info"].get("stale_warning")
            if stale_warn_dy:
                st.warning(stale_warn_dy)

            fig_day = build_chart(df_m15_calc, sc_day, ticker_bersih, "M15")
            st.plotly_chart(fig_day, use_container_width=True)

            render_indicator_panel(sc_day, df_m15_calc)

            st.markdown("#### 📰 Sentimen Berita")
            if sentimen_status == "Positif":
                st.success(f"**{sentimen_status}** — {sentimen_headline}")
            elif sentimen_status == "Negatif":
                st.error(f"**{sentimen_status}** — {sentimen_headline}")
            else:
                st.info(f"**{sentimen_status}** — {sentimen_headline}")

            ps_day = render_trading_plan(sc_day, total_modal_input, max_risiko_input)

            # ── PDF DAY ──────────────────────────────────────────────────────
            st.markdown("---")
            info_dy  = sc_day["info"]
            plan_dy  = sc_day["trading_plan"]
            l1_dy    = sc_day["layer1_filter"]
            l2_dy    = sc_day["layer2_trend"]
            l3_dy    = sc_day["layer3_momentum"]
            l4_dy    = sc_day["layer4_entry"]

            pdf_data_day = {
                "ticker":           ticker_bersih,
                "nama_perusahaan":  nama_perusahaan,
                "sektor":           sektor_id,
                "syariah":          status_syariah,
                "waktu":            datetime.now().strftime("%d-%m-%Y %H:%M"),
                "timeframe":        "Day Trade — M15",
                "harga":            info_dy['price'],
                "score":            sc_day["score"],
                "label":            sc_day["label"],
                "confidence":       sc_day["confidence"],
                "sentiment":        sentimen_status,
                "headline":         sentimen_headline,
                "total_modal":      total_modal_input,
                "max_risiko":       max_risiko_input,
                "max_lembar_risk":  ps_day["max_lembar_risk"],
                "max_lembar_capital": ps_day["max_lembar_capital"],
                "final_lot":        ps_day["final_lot"],
                "plan":             plan_dy,
                "layer1": {
                    "adx_nilai":  l1_dy["ADX"]["nilai"],
                    "adx_label":  l1_dy["ADX"]["label"],
                    "vol_nilai":  l1_dy["Volume"]["nilai"],
                    "vol_label":  l1_dy["Volume"]["label"],
                    "liq_nilai":  f"Rp {info_dy['value_ma20']:,.0f}",
                    "liq_label":  "Likuid" if info_dy['value_ma20'] > 0 else "Cek Manual",
                },
                "layer2": {
                    "ema_nilai":   f"EMA9:{info_dy['ema9']:,.0f}|EMA20:{info_dy['ema20']:,.0f}",
                    "ema_label":   l2_dy["EMA_Stack"]["label"],
                    "super_nilai": f"{info_dy['super_line']:,.0f}",
                    "super_label": l2_dy["Supertrend"]["label"],
                    "sar_nilai":   f"{info_dy['sar']:,.0f}",
                    "sar_label":   l2_dy["Parabolic_SAR"]["label"],
                    "sma_nilai":   f"Harga:{info_dy['price']:,.0f}|SMA20:{info_dy['bb_mid']:,.0f}",
                    "sma_label":   l2_dy["BB_Mid"]["label"],
                    "vwap_nilai":  f"{info_dy['vwap']:,.0f}",
                    "vwap_label":  "Di Atas VWAP" if info_dy['price'] > info_dy['vwap'] else "Di Bawah VWAP",
                },
                "layer3": {
                    "macd_nilai":   l3_dy["MACD"]["nilai"],
                    "macd_label":   l3_dy["MACD"]["label"],
                    "rsi_nilai":    f"{info_dy['rsi']:.1f}",
                    "rsi_label":    l3_dy["RSI"]["label"],
                    "stoch_nilai":  f"%K:{info_dy['stoch_k']:.1f}|%D:{info_dy['stoch_d']:.1f}",
                    "stoch_label":  l3_dy["Stochastic"]["label"],
                    "obv_nilai":    f"{info_dy['obv']:,.0f}",
                    "obv_label":    "OBV Naik (Akumulasi)" if info_dy['obv'] > info_dy['obv_prev'] else "OBV Turun (Distribusi)",
                },
                "layer4": {
                    "bb_nilai":       f"U:{info_dy['bb_upper']:,.0f}|M:{info_dy['bb_mid']:,.0f}|L:{info_dy['bb_lower']:,.0f}",
                    "bb_label":       l4_dy["Bollinger_Bands"]["label"],
                    "fib_nilai":      f"H:{info_dy['fib_high']:,.0f}|L:{info_dy['fib_low']:,.0f}",
                    "fib_label":      l4_dy["Fibonacci"]["label"],
                    "candle_label":   l4_dy["Candlestick"]["label"],
                    "volspike_label": l4_dy["Volume_Spike"]["label"],
                    "atr_nilai":      f"{info_dy['atr']:,.0f} ({info_dy['atr_pct']:.2f}%)",
                    "atr_label":      (
                        "Volatilitas Rendah (<1%)" if info_dy['atr_pct'] < 1
                        else "Volatilitas Normal (1-3%)" if info_dy['atr_pct'] < 3
                        else "Volatilitas Tinggi (>3%)"
                    ),
                },
            }

            try:
                pdf_bytes_day = generate_pdf_fpdf(pdf_data_day)
                if pdf_bytes_day:
                    st.download_button(
                        label="📄 Unduh Laporan Day Trade (PDF)",
                        data=pdf_bytes_day,
                        file_name=f"ESP_DayTrade_{ticker_bersih}_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
            except Exception as e:
                st.warning(f"⚠️ PDF tidak dapat dibuat: {e}")

    # ── DISCLAIMER ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.warning(
        "⚠️ **DISCLAIMER:** Laporan analisa ini dihasilkan secara otomatis menggunakan "
        "algoritma indikator teknikal. Bukan merupakan ajakan, rekomendasi pasti, atau "
        "paksaan untuk membeli/menjual saham. Keputusan investasi sepenuhnya menjadi "
        "tanggung jawab pribadi investor. Selalu terapkan manajemen risiko dan DYOR."
    )
