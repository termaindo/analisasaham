import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import pytz
import os
import base64

try:
    from fpdf import FPDF
    _FPDF_AVAILABLE = True
except ImportError:
    _FPDF_AVAILABLE = False

# data_loader.py ada di /utils/
from utils.data_loader import get_full_stock_data, hitung_div_yield_normal


# =============================================================================
# BAGIAN 1 — HELPER: PEMBERSIH CANDLE LIBUR & AKSESOR AMAN
# =============================================================================

def clean_and_validate_history(df_raw: pd.DataFrame) -> tuple:
    """
    Buang baris libur/kosong dari history yfinance; deteksi dan drop candle
    hari ini yang masih parsial; hitung stale_days.

    Baris dianggap tidak valid jika Volume == 0 atau Close == 0/NaN.
    Candle hari ini dianggap parsial jika Volume-nya < 20% rata-rata Volume.

    Returns
    -------
    df_clean  : pd.DataFrame — hanya baris trading valid, index tz Asia/Jakarta
    stale_days: int          — jarak kalender candle valid terakhir ke hari ini
    stale_msg : str          — pesan siap tampil di st.warning / st.info
    """
    if df_raw is None or df_raw.empty:
        return pd.DataFrame(), 0, ""

    tz_jkt = pytz.timezone("Asia/Jakarta")

    # Normalise timezone ke Asia/Jakarta
    df = df_raw.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert(tz_jkt)
    else:
        df.index = df.index.tz_convert(tz_jkt)

    # Buang baris libur — Volume=0 atau Close=0/NaN
    mask_valid = (df["Volume"] > 0) & (df["Close"] > 0) & df["Close"].notna()
    df_clean = df[mask_valid].copy()

    if df_clean.empty:
        return df_clean, 0, "⚠️ Tidak ada data OHLCV valid setelah filter baris libur."

    # Drop candle hari ini jika masih parsial (volume < 20% rata-rata)
    today_jkt = datetime.now(tz_jkt).date()
    if df_clean.index[-1].date() == today_jkt:
        avg_vol  = df_clean["Volume"].iloc[:-1].mean()
        last_vol = df_clean["Volume"].iloc[-1]
        if avg_vol > 0 and last_vol < avg_vol * 0.20:
            df_clean = df_clean.iloc[:-1]

    if df_clean.empty:
        return df_clean, 0, "⚠️ Tidak ada candle valid tersisa setelah filter candle parsial."

    # Hitung stale days
    last_valid_date = df_clean.index[-1].date()
    stale_days = (today_jkt - last_valid_date).days

    if stale_days == 0:
        stale_msg = ""
    elif stale_days == 1:
        stale_msg = "ℹ️ Data per kemarin — pasar belum buka hari ini atau data yfinance belum tersedia."
    else:
        stale_msg = (
            f"⚠️ Candle valid terakhir: **{last_valid_date.strftime('%d %b %Y')}** "
            f"({stale_days} hari kalender yang lalu). "
            f"Kemungkinan ada libur panjang atau data yfinance terlambat. "
            f"Hasil analisa berdasarkan data tersebut."
        )

    return df_clean, stale_days, stale_msg


def safe_iloc(df: pd.DataFrame, col: str, pos: int, default: float = 0.0) -> float:
    """
    Ambil df[col].iloc[pos] secara aman.
    Kembalikan default jika IndexError, KeyError, atau nilai NaN.
    """
    try:
        val = df[col].iloc[pos]
        return default if pd.isna(val) else float(val)
    except (IndexError, KeyError):
        return default


# =============================================================================
# BAGIAN 2 — GENERATOR PDF
# =============================================================================

def clean_pdf_text(text: str) -> str:
    """Hapus karakter non-latin-1 agar tidak merusak FPDF."""
    return str(text).encode("latin-1", "ignore").decode("latin-1")


def export_analisa_cepat_to_pdf(
    ticker, company_name, sector, f_score, roe, lbl_solv, eps_g, rev_g,
    t_score, avg_value_ma20, rsi, sentiment, curr_per, div_yield,
    rekomen, curr, entry_bawah, entry_atas, tp, reward_pct,
    sl_final, risk_pct, alasan_tek,
    modal_awal, maks_risiko, max_lot, alasan_lot, sl_note,
) -> bytes:
    """Generate PDF analisa cepat dan kembalikan sebagai bytes latin-1."""
    if not _FPDF_AVAILABLE:
        return b""

    pdf = FPDF()
    pdf.add_page()

    safe_company   = clean_pdf_text(company_name)
    safe_sector    = clean_pdf_text(sector).title()
    safe_lbl_solv  = clean_pdf_text(lbl_solv)
    safe_sentiment = clean_pdf_text(sentiment)
    safe_rekomen   = clean_pdf_text(rekomen)
    safe_alasan    = clean_pdf_text(alasan_tek)

    logo_path = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_path):
        logo_path = "../logo_expert_stock_pro.png"

    # Header
    pdf.set_fill_color(20, 20, 20)
    pdf.rect(0, 0, 210, 25, "F")
    if os.path.exists(logo_path):
        pdf.set_fill_color(218, 165, 32)
        pdf.rect(10, 3, 19, 19, "F")
        pdf.image(logo_path, x=10.5, y=3.5, w=18, h=18)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 16)
    pdf.set_xy(35, 8)
    pdf.cell(0, 10, "Expert Stock Pro - Analisa Cepat Pro", ln=True)
    pdf.set_y(28)

    pdf.set_font("Arial", "I", 10)
    pdf.set_text_color(0, 0, 255)
    pdf.cell(0, 5, "Sumber: https://s.id/pintarsaham", ln=True, align="C",
             link="https://s.id/pintarsaham")
    pdf.ln(2)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 8, f"{ticker} - {safe_company}", ln=True, align="C")

    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, f"Sektor: {safe_sector} | Status: Perlu Cek ISSI/JII", ln=True, align="C")
    pdf.ln(2)

    pdf.set_font("Arial", "B", 10)
    waktu_analisa = datetime.now().strftime("%d-%m-%Y %H:%M WIB")
    pdf.cell(0, 5, f"Analisa: {waktu_analisa} | Harga: Rp {int(curr):,.0f}", ln=True, align="R")

    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
    pdf.ln(5)

    # Ringkasan Skor
    pdf.set_font("Arial", "B", 11)
    pdf.cell(190, 8, "1. Ringkasan Skor & Sentimen", ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(190, 6, (
        f"- Fundamental Score: {f_score}/100 "
        f"(ROE {roe:.1f}%, {safe_lbl_solv}, EPS Grw {eps_g:.1f}%, Rev Grw {rev_g:.1f}%)"
    ))
    pdf.multi_cell(190, 6,
        f"- Technical Score-Swing Trading: {t_score:g}/100 (Trigger: {safe_alasan})")
    pdf.cell(190, 6, f"- Valuasi Dasar: PER {curr_per:.1f}x | Div. Yield {div_yield:.2f}%", ln=True)
    pdf.cell(190, 6, f"- Sentiment Pasar: {safe_sentiment}", ln=True)
    pdf.ln(4)

    # Rekomendasi & Trading Plan
    pdf.set_font("Arial", "B", 11)
    label_section = ("2. Rekomendasi & Trading Plan" if t_score < 70
                     else "2. Rekomendasi, Trading Plan & Sizing (RRR 1:2)")
    pdf.cell(190, 8, label_section, ln=True)
    pdf.set_font("Arial", "", 10)

    if t_score >= 85:
        pdf.set_text_color(0, 150, 0)
    elif t_score >= 70:
        pdf.set_text_color(200, 150, 0)
    else:
        pdf.set_text_color(200, 0, 0)

    pdf.set_font("Arial", "B", 12)
    pdf.multi_cell(190, 6, f">> {safe_rekomen} <<")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 10)
    pdf.ln(2)

    if t_score < 70:
        pdf.set_text_color(200, 0, 0)
        pdf.multi_cell(190, 6,
            "Tidak Disarankan untuk Melakukan Trading dengan gaya Swing Trading dulu, "
            "karena belum didukung oleh indikator teknikal yang memadai.")
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.cell(190, 6,
            f"- Modal Maksimal: Rp {modal_awal:,.0f} | Risiko Maksimal: Rp {maks_risiko:,.0f}", ln=True)
        pdf.cell(190, 6, f"- Harga Sekarang: Rp {int(curr):,.0f}", ln=True)
        pdf.cell(190, 6,
            f"- Usulan Entry: Rp {int(entry_bawah):,.0f} - Rp {int(entry_atas):,.0f} "
            f"(Buy on Weakness -1%)", ln=True)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(190, 6, f"- Take Profit (TP): Rp {tp:,.0f} (+{reward_pct:.1f}%)", ln=True)
        pdf.set_text_color(200, 0, 0)
        pdf.cell(190, 6,
            f"- Stop Loss (SL): Rp {sl_final:,.0f} (-{risk_pct:.1f}%){sl_note}", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(190, 6, f"- Max Lot Pembelian: {max_lot} Lot ({alasan_lot})", ln=True)
        pdf.set_font("Arial", "", 10)

    pdf.ln(10)

    # Footer disclaimer
    pdf.set_y(-35)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(190, 5, "DISCLAIMER:", ln=True)
    pdf.set_font("Arial", "I", 7)
    pdf.multi_cell(190, 4, clean_pdf_text(
        "Semua informasi, analisa teknikal, analisa fundamental, ataupun sinyal trading dan "
        "analisa-analisa lain yang disediakan di modul ini hanya untuk tujuan edukasi dan "
        "informasi. Ini bukan merupakan rekomendasi, ajakan, atau nasihat keuangan untuk "
        "membeli atau menjual saham tertentu. Keputusan investasi sepenuhnya berada di tangan "
        "Anda. Harap lakukan riset Anda sendiri (Do Your Own Research) dan pertimbangkan "
        "profil risiko sebelum mengambil keputusan di pasar modal."
    ))

    return pdf.output(dest="S").encode("latin-1", "ignore")


# =============================================================================
# BAGIAN 3 — FUNGSI UTAMA MODUL
# =============================================================================

def run_analisa_cepat():
    """Entry point modul Analisa Cepat Pro."""

    # Logo & judul
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
    st.markdown("<h1 style='text-align:center;'>Analisa Cepat Pro</h1>", unsafe_allow_html=True)
    if not os.path.exists(logo_file):
        st.warning("⚠️ File logo belum ditemukan.")
    st.markdown("---")

    # Input
    st.markdown("### ⚙️ Konfigurasi Manajemen Risiko")
    col1, col2, col3 = st.columns(3)
    with col1:
        ticker_input = st.text_input("Kode Saham (Quick Scan):", value="BBCA").upper()
    with col2:
        modal_awal = st.number_input(
            "Total Modal Trading (Rp):", min_value=100_000, value=10_000_000, step=500_000)
    with col3:
        maks_risiko = st.number_input(
            "Maks. Nominal Risiko (Rp):", min_value=10_000, value=500_000, step=50_000)

    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"
    st.markdown("<br>", unsafe_allow_html=True)

    if not st.button(f"Jalankan Analisa {ticker_input}", type="primary"):
        return

    with st.spinner("Mengkalkulasi indikator teknikal & fundamental..."):

        # ── AMBIL DATA ────────────────────────────────────────────────────────
        data       = get_full_stock_data(ticker)
        info       = data["info"]
        df_raw     = data["history"]
        financials = data.get("financials", pd.DataFrame())
        cashflow   = data.get("cashflow",   pd.DataFrame())

        if df_raw is None or df_raw.empty or not info:
            st.error("Data gagal dimuat. Tunggu 1 menit lalu coba lagi atau ganti ticker.")
            return

        # ── BERSIHKAN CANDLE LIBUR & PARSIAL ─────────────────────────────────
        #
        # Setelah baris ini, df hanya berisi candle dengan Volume > 0 & Close > 0.
        # Efek pada semua referensi iloc di bawah:
        #   iloc[-1]  = candle trading valid terakhir  (bukan hari libur)
        #   iloc[-2]  = candle valid sebelumnya         (tidak ada gap libur)
        #   iloc[-6]  = 5 candle trading ke belakang    (bukan 5 hari kalender)
        # Dengan demikian perbandingan prev vs curr, OBV[-5], VPT[-3], dsb.
        # selalu membandingkan sesi trading nyata — bukan baris kosong.
        #
        df, stale_days, stale_msg = clean_and_validate_history(df_raw)

        if df.empty:
            st.error(
                "Tidak ada data candle valid untuk ticker ini setelah membersihkan baris libur.")
            return

        if stale_msg:
            st.warning(stale_msg)

        # Butuh minimal 27 baris untuk EMA26 + MACD Signal stabil
        MIN_ROWS = 27
        if len(df) < MIN_ROWS:
            st.error(
                f"Data terlalu sedikit ({len(df)} candle valid). "
                f"Minimal dibutuhkan {MIN_ROWS} candle. Coba ticker lain.")
            return

        # ── KALKULASI INDIKATOR — SEMUA PAKAI df BERSIH ──────────────────────

        df["MA20"]  = df["Close"].rolling(20).mean()
        df["MA50"]  = df["Close"].rolling(50).mean()
        df["MA200"] = df["Close"].rolling(200).mean()

        df["Value"]    = df["Close"] * df["Volume"]
        avg_value_ma20 = df["Value"].rolling(20).mean().iloc[-1]
        df["Vol_MA20"] = df["Volume"].rolling(20).mean()

        df["Typical_Price"] = (df["High"] + df["Low"] + df["Close"]) / 3
        df["VWAP_20"] = (
            (df["Typical_Price"] * df["Volume"]).rolling(20).sum()
            / df["Volume"].rolling(20).sum()
        )

        df["EMA9"]  = df["Close"].ewm(span=9,  adjust=False).mean()
        df["EMA21"] = df["Close"].ewm(span=21, adjust=False).mean()

        # MACD
        df["EMA12"]     = df["Close"].ewm(span=12, adjust=False).mean()
        df["EMA26"]     = df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD"]      = df["EMA12"] - df["EMA26"]
        df["Signal"]    = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Hist"] = df["MACD"] - df["Signal"]

        # RSI
        delta     = df["Close"].diff()
        gain      = delta.where(delta > 0, 0).rolling(14).mean()
        loss      = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df["RSI"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

        # ATR
        hl        = df["High"] - df["Low"]
        hc        = np.abs(df["High"] - df["Close"].shift())
        lc        = np.abs(df["Low"]  - df["Close"].shift())
        df["ATR"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

        # OBV
        obv = [0]
        for i in range(1, len(df)):
            if df["Close"].iloc[i] > df["Close"].iloc[i - 1]:
                obv.append(obv[-1] + df["Volume"].iloc[i])
            elif df["Close"].iloc[i] < df["Close"].iloc[i - 1]:
                obv.append(obv[-1] - df["Volume"].iloc[i])
            else:
                obv.append(obv[-1])
        df["OBV"] = obv

        # CMF & VPT
        mfm = (
            ((df["Close"] - df["Low"]) - (df["High"] - df["Close"]))
            / (df["High"] - df["Low"]).replace(0, np.nan)
        )
        df["CMF"] = (mfm * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum()
        df["VPT"] = (df["Close"].pct_change() * df["Volume"]).cumsum()

        # ── SUPERTREND (10, 3) ────────────────────────────────────────────────
        st_period     = 10
        st_multiplier = 3.0
        df["ST_ATR"]       = df["ATR"].rolling(st_period).mean()
        df["ST_UpperBand"] = ((df["High"] + df["Low"]) / 2) + (st_multiplier * df["ST_ATR"])
        df["ST_LowerBand"] = ((df["High"] + df["Low"]) / 2) - (st_multiplier * df["ST_ATR"])

        supertrend_dir = [np.nan] * len(df)
        final_upper    = list(df["ST_UpperBand"])
        final_lower    = list(df["ST_LowerBand"])

        for i in range(1, len(df)):
            if not (final_upper[i] < final_upper[i - 1] or
                    df["Close"].iloc[i - 1] > final_upper[i - 1]):
                final_upper[i] = final_upper[i - 1]
            if not (final_lower[i] > final_lower[i - 1] or
                    df["Close"].iloc[i - 1] < final_lower[i - 1]):
                final_lower[i] = final_lower[i - 1]

            if np.isnan(supertrend_dir[i - 1]):
                supertrend_dir[i] = 1 if df["Close"].iloc[i] > final_upper[i] else -1
            elif supertrend_dir[i - 1] == -1 and df["Close"].iloc[i] > final_upper[i]:
                supertrend_dir[i] = 1
            elif supertrend_dir[i - 1] == 1 and df["Close"].iloc[i] < final_lower[i]:
                supertrend_dir[i] = -1
            else:
                supertrend_dir[i] = supertrend_dir[i - 1]

        df["ST_Dir"] = supertrend_dir

        # ── PARABOLIC SAR ──────────────────────────────────────────────────────
        af_start  = 0.02
        af_step   = 0.02
        af_max    = 0.20
        psar_vals = [np.nan] * len(df)
        psar_bull = [True]  * len(df)

        if len(df) > 2:
            psar_vals[0] = df["Low"].iloc[0]
            psar_bull[0] = True
            ep = df["High"].iloc[0]
            af = af_start

            for i in range(1, len(df)):
                prev_psar = psar_vals[i - 1]
                prev_bull = psar_bull[i - 1]

                if prev_bull:
                    psar_vals[i] = prev_psar + af * (ep - prev_psar)
                    psar_vals[i] = min(
                        psar_vals[i],
                        df["Low"].iloc[i - 1],
                        df["Low"].iloc[max(0, i - 2)],
                    )
                    if df["Low"].iloc[i] < psar_vals[i]:
                        psar_bull[i] = False
                        psar_vals[i] = ep
                        ep           = df["Low"].iloc[i]
                        af           = af_start
                    else:
                        psar_bull[i] = True
                        if df["High"].iloc[i] > ep:
                            ep = df["High"].iloc[i]
                            af = min(af + af_step, af_max)
                else:
                    psar_vals[i] = prev_psar - af * (prev_psar - ep)
                    psar_vals[i] = max(
                        psar_vals[i],
                        df["High"].iloc[i - 1],
                        df["High"].iloc[max(0, i - 2)],
                    )
                    if df["High"].iloc[i] > psar_vals[i]:
                        psar_bull[i] = True
                        psar_vals[i] = ep
                        ep           = df["High"].iloc[i]
                        af           = af_start
                    else:
                        psar_bull[i] = False
                        if df["Low"].iloc[i] < ep:
                            ep = df["Low"].iloc[i]
                            af = min(af + af_step, af_max)

        df["PSAR_Bull"] = psar_bull

        # ── AMBIL NILAI AKHIR — SEMUA LEWAT safe_iloc ─────────────────────────
        #
        # Karena df sudah bersih dari baris libur:
        #   iloc[-1]  = candle trading valid terakhir
        #   iloc[-2]  = candle valid sebelumnya (prev1)
        #   iloc[-6]  = 5 candle trading ke belakang untuk OBV prev5
        #   iloc[-4]  = 3 candle trading ke belakang untuk VPT prev3
        # Tidak ada risiko membaca baris Volume=0 atau Close=0.
        #
        curr       = safe_iloc(df, "Close",    -1)

        ma20_val  = safe_iloc(df, "MA20",     -1)
        ma50_val  = safe_iloc(df, "MA50",     -1)
        ma200_val = safe_iloc(df, "MA200",    -1)
        ema21_val = safe_iloc(df, "EMA21",    -1)
        vwap_val  = safe_iloc(df, "VWAP_20",  -1)

        vol_curr  = safe_iloc(df, "Volume",   -1)
        vol_sma20 = safe_iloc(df, "Vol_MA20", -1)

        macd_val    = safe_iloc(df, "MACD",      -1)
        signal_val  = safe_iloc(df, "Signal",    -1)
        macd_hist   = safe_iloc(df, "MACD_Hist", -1)
        macd_prev   = safe_iloc(df, "MACD",      -2, default=macd_val)
        signal_prev = safe_iloc(df, "Signal",    -2, default=signal_val)
        hist_prev   = safe_iloc(df, "MACD_Hist", -2)

        rsi_curr = safe_iloc(df, "RSI", -1)
        rsi_prev = safe_iloc(df, "RSI", -2, default=rsi_curr)

        st_dir_curr    = safe_iloc(df, "ST_Dir", -1)
        st_dir_prev    = safe_iloc(df, "ST_Dir", -2, default=st_dir_curr)
        psar_bull_curr = bool(df["PSAR_Bull"].iloc[-1])

        # OBV: bandingkan candle terakhir vs 5 candle trading ke belakang
        obv_curr  = safe_iloc(df, "OBV", -1)
        obv_prev5 = safe_iloc(df, "OBV", -6, default=obv_curr)

        # VPT: bandingkan candle terakhir vs 3 candle trading ke belakang
        vpt_curr  = safe_iloc(df, "VPT", -1)
        vpt_prev3 = safe_iloc(df, "VPT", -4, default=vpt_curr)

        obv_trend_up = obv_curr > obv_prev5
        vpt_trend_up = vpt_curr > vpt_prev3
        rvol         = vol_curr / vol_sma20 if vol_sma20 > 0 else 0

        # Hitung berapa candle berturut-turut di atas Supertrend
        st_dir_series = df["ST_Dir"].dropna()
        candles_above = 0
        for d in reversed(st_dir_series.values[:-1]):
            if d == 1:
                candles_above += 1
            else:
                break

        # ── SCORING FUNDAMENTAL ───────────────────────────────────────────────
        f_score  = 0
        sector   = info.get("sector",   "") or ""
        industry = info.get("industry", "") or ""

        is_bank  = "Bank" in industry or sector == "Financial Services"
        is_infra = "Infrastructure" in industry or sector in [
            "Utilities", "Real Estate", "Industrials", "Energy", "Basic Materials"
        ]

        der_ratio = (info.get("debtToEquity", 0) or 0) / 100
        lbl_solv  = ""
        car, npl  = 0.0, 0.0
        ocf       = 0

        if is_bank:
            car = float(info.get("capitalAdequacyRatio", 18) or 18)
            npl = float(info.get("nonPerformingLoan",    2.5) or 2.5)
            if car > 20:     f_score += 10
            elif car >= 15:  f_score += 5
            if npl < 2:      f_score += 10
            elif npl <= 3.5: f_score += 5
            lbl_solv = f"CAR {car:.1f}% | NPL {npl:.1f}%"

        elif is_infra:
            if der_ratio < 1.5:    f_score += 10
            elif der_ratio <= 2.5: f_score += 5
            icr = 2.0
            try:
                ebit = (
                    financials.loc["EBIT"].iloc[0]
                    if "EBIT" in financials.index
                    else (financials.loc["Operating Income"].iloc[0]
                          if "Operating Income" in financials.index else 0)
                )
                interest = (
                    abs(financials.loc["Interest Expense"].iloc[0])
                    if "Interest Expense" in financials.index else 0
                )
                if interest > 0:
                    icr = ebit / interest
            except Exception:
                pass
            if icr > 3.0:    f_score += 10
            elif icr >= 1.5: f_score += 5
            lbl_solv = f"DER {der_ratio:.2f}x | ICR {icr:.1f}x"

        else:
            if der_ratio < 0.5:    f_score += 10
            elif der_ratio <= 1.0: f_score += 5
            cr = float(info.get("currentRatio", 0) or 0)
            if cr > 1.5:   f_score += 10
            elif cr >= 1.0: f_score += 5
            lbl_solv = f"DER {der_ratio:.2f}x | CR {cr:.2f}x"

        roe = (info.get("returnOnEquity", 0) or 0) * 100
        if roe > 15:   f_score += 10
        elif roe >= 10: f_score += 5

        npm = (info.get("profitMargins", 0) or 0) * 100
        if npm > 10:  f_score += 10
        elif npm >= 5: f_score += 5

        mean_pe_5y  = (info.get("trailingPE",   15) or 15)  * 0.95
        mean_pbv_5y = (info.get("priceToBook", 1.5) or 1.5) * 0.90

        curr_per = float(info.get("trailingPE",  0) or 0)
        if curr_per > 0 and mean_pe_5y > 0:
            pe_discount = ((mean_pe_5y - curr_per) / mean_pe_5y) * 100
            if pe_discount > 20:   f_score += 10
            elif pe_discount >= 0: f_score += 5

        curr_pbv = float(info.get("priceToBook", 0) or 0)
        if curr_pbv > 0 and mean_pbv_5y > 0:
            pbv_discount = ((mean_pbv_5y - curr_pbv) / mean_pbv_5y) * 100
            if pbv_discount > 20:   f_score += 10
            elif pbv_discount >= 0: f_score += 5

        eps_g = (info.get("earningsGrowth", 0) or 0) * 100
        if eps_g > 15:   f_score += 10
        elif eps_g >= 5:  f_score += 7
        elif eps_g > 0:   f_score += 3

        rev_g = (info.get("revenueGrowth", 0) or 0) * 100
        if rev_g > 10:  f_score += 10
        elif rev_g >= 0: f_score += 5

        try:
            if not cashflow.empty and not financials.empty:
                ocf = (cashflow.loc["Operating Cash Flow"].iloc[0]
                       if "Operating Cash Flow" in cashflow.index else 0)
                net_income = (financials.loc["Net Income"].iloc[0]
                              if "Net Income" in financials.index else 0)
                if ocf > net_income: f_score += 10
                elif ocf > 0:        f_score += 5
        except Exception:
            pass

        div_yield = hitung_div_yield_normal(info)
        if div_yield > 5:    f_score += 10
        elif div_yield >= 2:  f_score += 5

        # ── SCORING TEKNIKAL — SWING TRADING ──────────────────────────────────
        t_score    = 0
        alasan_tek = []

        # 1. Supertrend (10,3) — maks 20 poin
        if st_dir_curr == 1 and st_dir_prev != 1:
            t_score += 20
            alasan_tek.append("Supertrend Baru Bullish (10,3) +20")
        elif st_dir_curr == 1 and candles_above > 3:
            t_score += 15
            alasan_tek.append(f"Supertrend Bullish >{candles_above} candle (10,3) +15")

        # 2. MA Structure: Price > MA50 AND MA20 > MA50 — 15 poin
        if ma50_val > 0 and curr > ma50_val and ma20_val > ma50_val:
            t_score += 15
            alasan_tek.append("MA Structure (Price>MA50, MA20>MA50) +15")

        # 3. MACD Golden Cross — 7.5 poin
        if macd_val > signal_val and macd_prev <= signal_prev:
            t_score += 7.5
            alasan_tek.append("MACD Golden Cross +7.5")

        # 4. MACD Histogram Growing — 7.5 poin
        if macd_hist > hist_prev:
            t_score += 7.5
            alasan_tek.append("MACD Histogram Growing +7.5")

        # 5. Volume Spike > 1.2× MA20 — 10 poin
        if vol_sma20 > 0 and vol_curr > vol_sma20 * 1.2:
            t_score += 10
            alasan_tek.append("Volume Spike (>1.2x MA20) +10")

        # 6. RSI Momentum 50–75 — 7.5 poin
        if 50 <= rsi_curr <= 75:
            t_score += 7.5
            alasan_tek.append(f"RSI Momentum {rsi_curr:.1f} +7.5")

        # 7. RSI Rising — 7.5 poin
        if rsi_curr > rsi_prev:
            t_score += 7.5
            alasan_tek.append(f"RSI Rising ({rsi_prev:.1f}→{rsi_curr:.1f}) +7.5")

        # 8. PSAR Bullish — 5 poin
        if psar_bull_curr:
            t_score += 5
            alasan_tek.append("PSAR Konfirmasi Tren Naik +5")

        # 9. RVOL — maks 10 poin
        if rvol >= 2.5:
            t_score += 10
            alasan_tek.append(f"RVOL Tinggi ({rvol:.1f}x) +10")
        elif rvol >= 1.5:
            t_score += 6
            alasan_tek.append(f"RVOL Moderat ({rvol:.1f}x) +6")

        # 10. VPT Akumulasi Naik — 10 poin
        if vpt_trend_up:
            t_score += 10
            alasan_tek.append("VPT Akumulasi Naik +10")

        # 11. MACD Early Recovery — 10 poin
        if macd_val < 0 and macd_hist > hist_prev:
            t_score += 10
            alasan_tek.append("MACD Early Recovery +10")

        # 12. Penalti RSI Overbought > 75 — minus 15 poin
        if rsi_curr > 75:
            t_score -= 15
            alasan_tek.append(f"RSI Overbought ({rsi_curr:.1f}) -15")

        t_score     = min(round(t_score), 100)
        teks_alasan = ", ".join(alasan_tek) if alasan_tek else "Tidak ada sinyal kuat"

        # ── TRADING PLAN ───────────────────────────────────────────────────────
        atr = safe_iloc(df, "ATR", -1, default=curr * 0.02)

        entry_atas  = curr
        entry_bawah = curr * 0.99
        avg_entry   = (entry_atas + entry_bawah) / 2

        sl_atr      = avg_entry - (2.5 * atr)
        sl_hard_cap = avg_entry * 0.92

        if sl_hard_cap > sl_atr:
            sl_final = sl_hard_cap
            sl_note  = " (SL Hard Cap)"
        else:
            sl_final = sl_atr
            sl_note  = " (ATR SL)"

        tp         = avg_entry + (avg_entry - sl_final) * 2
        risk_pct   = ((avg_entry - sl_final) / avg_entry) * 100
        reward_pct = ((tp - avg_entry) / avg_entry) * 100

        # ── POSITION SIZING ────────────────────────────────────────────────────
        selisih_risiko  = max(avg_entry - sl_final, 1)
        max_shares_risk = maks_risiko / selisih_risiko
        max_shares_cap  = (0.15 * modal_awal) / avg_entry
        final_shares    = min(max_shares_risk, max_shares_cap)
        max_lot         = max(int(final_shares // 100), 0)
        alasan_lot      = ("Maks. Risiko per Trade"
                           if max_shares_risk < max_shares_cap
                           else "Maks. 15% dari Total Modal")

        # ── SENTIMEN ───────────────────────────────────────────────────────────
        if curr > ma50_val and curr > ma200_val:
            sentiment = "BULLISH (Sangat Kuat) 🐂"
        elif curr > ema21_val:
            sentiment = "MILD BULLISH (Jangka Pendek) 🐃"
        elif curr < ma200_val and ma200_val > 0:
            sentiment = "BEARISH (Hati-hati) 🐻"
        else:
            sentiment = "NEUTRAL / SIDEWAYS 😐"

        # ── REKOMENDASI & TRADING PLAN HTML ────────────────────────────────────
        company_name = info.get("longName", ticker)

        if t_score >= 85:
            rekomen   = "Boleh Trading → Silakan ambil posisi sesuai saran di bawah ini:"
            color_rec = "#00ff00"
            trading_plan_html = f"""
            <li><b>6. Trading Plan &amp; Sizing (Swing Target 1:2):</b><br>
                &bull; Harga Sekarang: Rp {int(curr):,.0f}<br>
                &bull; Usulan Entry: Rp {int(entry_bawah):,.0f} &ndash; Rp {int(entry_atas):,.0f}
                       (Buy on Weakness -1%)<br>
                &bull; Titik Target (TP): Rp {int(tp):,.0f} (Potensi Reward: +{reward_pct:.1f}%)<br>
                &bull; Batas Risiko (SL): Rp {int(sl_final):,.0f}
                       (Risiko Maks: -{risk_pct:.1f}%){sl_note}<br>
                &bull; <span style='color:#00e676;font-size:16px;'>
                       <b>Max Lot Pembelian: {max_lot} Lot</b> <i>({alasan_lot})</i></span>
            </li>"""

        elif t_score >= 70:
            rekomen   = ("Hati-hati → Masukkan ke daftar pantauan, "
                         "atau boleh trading dengan lot sebagian dulu.")
            color_rec = "#ffcc00"
            trading_plan_html = f"""
            <li><b>6. Trading Plan &amp; Sizing (Swing Target 1:2):</b><br>
                &bull; Harga Sekarang: Rp {int(curr):,.0f}<br>
                &bull; Usulan Entry: Rp {int(entry_bawah):,.0f} &ndash; Rp {int(entry_atas):,.0f}
                       (Buy on Weakness -1%)<br>
                &bull; Titik Target (TP): Rp {int(tp):,.0f} (Potensi Reward: +{reward_pct:.1f}%)<br>
                &bull; Batas Risiko (SL): Rp {int(sl_final):,.0f}
                       (Risiko Maks: -{risk_pct:.1f}%){sl_note}<br>
                &bull; <span style='color:#ffb300;font-size:16px;'>
                       <b>Max Lot Pembelian: {max_lot} Lot</b> <i>({alasan_lot})</i></span>
            </li>"""

        else:
            rekomen   = "Dilarang Trading → Belum didukung indikator teknikal yang memadai."
            color_rec = "#ff0000"
            trading_plan_html = (
                "<li><b>6. Trading Plan:</b><br>"
                "<span style='color:#ff5252;font-weight:bold;'>"
                "Tidak Disarankan untuk Melakukan Trading dulu, "
                "karena belum didukung oleh indikator teknikal yang memadai."
                "</span></li>"
            )

        # ── OUTPUT HTML ────────────────────────────────────────────────────────
        html_output = f"""
        <div style="background-color:#1e2b3e;padding:25px;border-radius:12px;
                    border-left:10px solid {color_rec};color:#e0e0e0;font-family:sans-serif;">
            <h3 style="margin-top:0;color:white;margin-bottom:5px;">{company_name} ({ticker})</h3>
            <p style="margin-top:0;font-size:14px;color:#b0bec5;margin-bottom:15px;">
                Sektor: <b>{sector.title()}</b> | Kategori Syariah: <b>Perlu Cek ISSI/JII</b>
            </p>
            <ul style="line-height:1.8;padding-left:20px;font-size:16px;">
                <li><b>1. Fundamental Score ({f_score}/100):</b>
                    ROE {roe:.1f}%, {lbl_solv}, EPS Grw {eps_g:.1f}%,
                    Arus Kas {'Positif' if ocf > 0 else 'Negatif'}.</li>
                <li><b>2. Technical Score-Swing Trading ({t_score:g}/100):</b>
                    Trigger &rarr; {teks_alasan}</li>
                <li><b>3. Sentiment Pasar:</b> <b>{sentiment}</b></li>
                <li><b>4. Rekomendasi Final:</b><br>
                    <span style="color:{color_rec};font-weight:bold;font-size:17px;">
                    {rekomen}</span></li>
                <li><b>5. Timeframe:</b> Swing Trading (Menengah)</li>
                {trading_plan_html}
            </ul>
        </div>
        """
        st.markdown(html_output, unsafe_allow_html=True)

        # ── EXPANDER DATA MENTAH ────────────────────────────────────────────────
        with st.expander("Lihat Detail Data Mentah"):
            last_candle_str = df.index[-1].strftime("%d %b %Y %H:%M %Z")
            st.write(f"**Candle valid terakhir :** {last_candle_str}")
            st.write(f"**Jumlah candle bersih  :** {len(df)}")
            if stale_days > 0:
                st.write(
                    f"**Stale days            :** {stale_days} hari kalender "
                    f"sejak candle valid terakhir ke hari ini"
                )
            st.write(f"Modal Terinput   : Rp {modal_awal:,.0f} | Maks Risiko: Rp {maks_risiko:,.0f}")
            st.write(f"Jarak Entry → SL : Rp {selisih_risiko:,.0f} per lembar")
            st.write(f"VWAP 20          : Rp {int(vwap_val):,.0f}")
            st.write(f"MACD             : {macd_val:.4f}  |  Signal: {signal_val:.4f}")
            st.write(f"RSI              : {rsi_curr:.1f}  |  ATR: {atr:.0f}")

        # ── DOWNLOAD PDF ─────────────────────────────────────────────────────────
        if _FPDF_AVAILABLE:
            pdf_data = export_analisa_cepat_to_pdf(
                ticker, company_name, sector, f_score, roe, lbl_solv, eps_g, rev_g,
                t_score, avg_value_ma20, rsi_curr, sentiment, curr_per, div_yield,
                rekomen, curr, entry_bawah, entry_atas, tp, reward_pct,
                sl_final, risk_pct, teks_alasan,
                modal_awal, maks_risiko, max_lot, alasan_lot, sl_note,
            )
            tanggal_cetak = datetime.now().strftime("%Y%m%d")
            nama_file_pdf = (
                f"ExpertStockPro_AnalisaCepat_"
                f"{ticker.replace('.JK', '')}_{tanggal_cetak}.pdf"
            )
            st.markdown("<br>", unsafe_allow_html=True)
            _, col_pdf, _ = st.columns([1, 2, 1])
            with col_pdf:
                st.download_button(
                    label="📄 Simpan Analisa Cepat (PDF)",
                    data=pdf_data,
                    file_name=nama_file_pdf,
                    mime="application/pdf",
                    use_container_width=True,
                )

        st.markdown("---")
        st.markdown(
            "**DISCLAIMER:** Semua informasi, analisa teknikal, analisa fundamental, "
            "ataupun sinyal trading dan analisa-analisa lain yang disediakan di modul ini "
            "hanya untuk tujuan edukasi dan informasi. Ini bukan merupakan rekomendasi, "
            "ajakan, atau nasihat keuangan untuk membeli atau menjual saham tertentu. "
            "Keputusan investasi sepenuhnya berada di tangan Anda. Harap lakukan riset "
            "Anda sendiri (*Do Your Own Research*) dan pertimbangkan profil risiko "
            "sebelum mengambil keputusan di pasar modal."
        )
