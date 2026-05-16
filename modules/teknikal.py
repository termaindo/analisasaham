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

# KOREKSI: data_loader.py ada di /utils/, bukan /modules/
from utils.data_loader import (
    get_full_stock_data,
    get_liquid_stocks,
    is_ticker_liquid,
    get_ticker_row,
    PRE_LIQUID_PATH,
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: STATUS SYARIAH
# ─────────────────────────────────────────────────────────────────────────────

def get_syariah_status(ticker_bersih: str) -> str:
    """
    Lookup status syariah dari liquid_stocks.csv (prioritas) atau
    pre_liquid_stocks.csv (fallback). Return string label siap tampil.
    """
    # Coba liquid_stocks dulu
    liquid_df = get_liquid_stocks()
    row = get_ticker_row(ticker_bersih, liquid_df)

    # Fallback ke pre_liquid jika tidak ditemukan
    if row is None and not liquid_df.empty is False:
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

def translate_sector(sector_en):
    """Terjemahkan nama sektor dari Bahasa Inggris ke Bahasa Indonesia."""
    mapping = {
        "Financial Services":    "Jasa Keuangan",
        "Basic Materials":       "Bahan Baku & Tambang",
        "Energy":                "Energi",
        "Communication Services":"Telekomunikasi",
        "Consumer Cyclical":     "Konsumsi Siklikal",
        "Consumer Defensive":    "Konsumsi Non-Siklikal",
        "Healthcare":            "Kesehatan",
        "Industrials":           "Industri",
        "Real Estate":           "Properti",
        "Technology":            "Teknologi",
        "Utilities":             "Utilitas",
    }
    return mapping.get(sector_en, sector_en)


# ─────────────────────────────────────────────────────────────────────────────
# ANALISA SENTIMEN BERITA
# ─────────────────────────────────────────────────────────────────────────────

def analyze_news_sentiment(ticker_symbol):
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
                if bw in title_lower: score += 1
            for bear_w in bearish_words:
                if bear_w in title_lower: score -= 1

        if score > 0:   return "Positif", latest_title
        elif score < 0: return "Negatif", latest_title
        else:           return "Netral",  latest_title
    except Exception:
        return "Netral", "Gagal memuat berita."


# ─────────────────────────────────────────────────────────────────────────────
# KALKULASI INDIKATOR TEKNIKAL
# ─────────────────────────────────────────────────────────────────────────────

def calculate_technical_pro(df):
    """Hitung semua indikator teknikal yang dibutuhkan modul ini."""
    df['MA20']  = df['Close'].rolling(20).mean()
    df['MA50']  = df['Close'].rolling(50).mean()
    df['MA200'] = df['Close'].rolling(200).mean()

    delta = df['Close'].diff()
    gain  = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))

    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD']        = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist']   = df['MACD'] - df['Signal_Line']

    df['BB_Mid']   = df['MA20']
    df['BB_Std']   = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + (2 * df['BB_Std'])
    df['BB_Lower'] = df['BB_Mid'] - (2 * df['BB_Std'])

    high_low   = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close  = np.abs(df['Low']  - df['Close'].shift())
    df['ATR']  = (
        pd.concat([high_low, high_close, low_close], axis=1)
        .max(axis=1).rolling(14).mean()
    )

    df['Vol_MA20']     = df['Volume'].rolling(20).mean()
    df['Typical_Price']= (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP_20']      = (
        (df['Typical_Price'] * df['Volume']).rolling(20).sum()
        / df['Volume'].rolling(20).sum()
    )
    df['EMA9']  = df['Close'].ewm(span=9,  adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['Value'] = df['Close'] * df['Volume']

    return df


# ─────────────────────────────────────────────────────────────────────────────
# GENERATOR PDF
# ─────────────────────────────────────────────────────────────────────────────

def generate_pdf_fpdf(data, logo_path="logo_expert_stock_pro.png"):
    """Bangun PDF laporan analisa teknikal menggunakan fpdf."""
    pdf = FPDF()
    pdf.add_page()

    status_syariah_teks = "Syariah" if "✅" in data['syariah'] else "Non-Syariah"

    # 1. HEADER BOX HITAM
    pdf.set_fill_color(20, 20, 20)
    pdf.rect(0, 0, 210, 25, 'F')

    if not os.path.exists(logo_path):
        if os.path.exists("../logo_expert_stock_pro.png"):
            logo_path = "../logo_expert_stock_pro.png"

    if os.path.exists(logo_path):
        pdf.set_fill_color(218, 165, 32)
        pdf.rect(10, 3, 19, 19, 'F')
        pdf.image(logo_path, x=10.5, y=3.5, w=18, h=18)

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    pdf.set_xy(35, 8)
    pdf.cell(0, 10, "Expert Stock Pro - Analisa Teknikal Pro", ln=True)
    pdf.set_y(28)

    # 2. HYPERLINK SUMBER
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(0, 0, 255)
    pdf.cell(0, 5, "Sumber: https://s.id/pintarsaham", ln=True, align='C',
             link="https://s.id/pintarsaham")
    pdf.ln(2)

    # 3. NAMA SAHAM & PERUSAHAAN
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 20)
    aman_nama = data['nama_perusahaan'].encode('latin-1', 'replace').decode('latin-1')
    pdf.cell(0, 8, f"{data['ticker']} - {aman_nama}", ln=True, align='C')

    # 4. INFO SEKTOR & SYARIAH
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, f"Sektor: {data['sektor']} | Status: {status_syariah_teks}",
             ln=True, align='C')
    pdf.ln(2)

    # 5. INFO TANGGAL & HARGA
    pdf.set_font("Arial", 'B', 10)
    waktu_analisa = data.get('waktu', datetime.now().strftime("%d-%m-%Y %H:%M"))
    pdf.cell(0, 5, f"Analisa: {waktu_analisa} | Harga: Rp {data['harga']:,.0f}",
             ln=True, align='R')
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
    pdf.ln(5)

    # KONTEN UTAMA
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt=f"SKOR TEKNIKAL: {data['score']}/100", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, txt=f"Sinyal: {data['signal']}", ln=True)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 6, txt=f"Catatan: {data['confidence']}", ln=True)
    pdf.ln(3)

    # DIMENSI 1
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 7, txt="1. TREND ANALYSIS", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, txt=f"- Trend Utama (Daily)  : {data['main_trend']}", ln=True)
    pdf.cell(0, 5, txt=f"- Trend Wkly/Monthly : {data['weekly_trend']}", ln=True)
    pdf.cell(0, 5, txt=f"- Support / Resist     : Rp {data['sup_level']:,.0f} / Rp {data['res_level']:,.0f}", ln=True)
    pdf.ln(3)

    # DIMENSI 2
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 7, txt="2. INDIKATOR TEKNIKAL", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, txt=f"- Posisi MA   : {data['posisi_ma']}", ln=True)
    pdf.cell(0, 5, txt=f"- RSI         : {data['rsi_text']}", ln=True)
    pdf.cell(0, 5, txt=f"- MACD        : {data['macd_text']}", ln=True)
    pdf.cell(0, 5, txt=f"- Volatilitas : {data['volatilitas']}", ln=True)
    pdf.ln(3)

    # DIMENSI 3
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 7, txt="3. PATTERN RECOGNITION", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, txt=f"- Candlestick   : {data['candlestick']}", ln=True)
    pdf.cell(0, 5, txt=f"- Chart Pattern : Potensi Konsolidasi / Channeling", ln=True)
    pdf.cell(0, 5, txt=f"- Divergence    : {data['divergence']}", ln=True)
    pdf.ln(3)

    # DIMENSI 4
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 7, txt="4. MOMENTUM & STRENGTH", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, txt=f"- Momentum : {data['momentum']}", ln=True)
    pdf.cell(0, 5, txt=f"- Pressure : {data['pressure']}", ln=True)
    pdf.ln(3)

    # DIMENSI 5
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, txt="5. TRADING PLAN & POSITION SIZING", ln=True)

    if data['score'] < 70:
        pdf.set_font("Arial", 'I', 11)
        pdf.set_text_color(220, 53, 69)
        pdf.multi_cell(0, 6, txt="Tidak Disarankan untuk Melakukan Trading dulu, karena belum didukung oleh indikator teknikal yang memadai.")
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_font("Arial", '', 11)
        pdf.cell(0, 6, txt=f"Harga Saat Ini : Rp {data['harga']:,.0f}", ln=True)
        pdf.cell(0, 6, txt=f"Area Entry     : Rp {data['entry_bawah']:,.0f} - Rp {data['entry_atas']:,.0f} ({data['caption_entry']})", ln=True)
        pdf.cell(0, 6, txt=f"Stop Loss      : Rp {data['sl_final']:,.0f} (-{data['risk_pct']:.1f}%) ({data['caption_sl']})", ln=True)
        pdf.cell(0, 6, txt=f"Target         : Rp {data['tp_final']:,.0f} (+{data['tp_pct']:.1f}%) ({data['caption_tp']})", ln=True)
        pdf.ln(2)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 6, txt="* POSITION SIZING (UKURAN LOT MAKSIMAL)", ln=True)
        pdf.set_font("Arial", '', 11)
        pdf.cell(0, 6, txt=f"Rekomendasi Aman  : {data['final_lot']} LOT", ln=True)
        pdf.set_font("Arial", 'I', 9)
        pdf.cell(0, 5,
                 txt=f"(Dihitung secara otomatis berdasarkan Max Risk Rp {data['max_risiko']:,.0f} "
                     f"dan Max Portofolio 15% dari Modal Rp {data['total_modal']:,.0f})",
                 ln=True)
    pdf.ln(5)

    # DIMENSI 6
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, txt="6. ANALISA SENTIMEN BERITA", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, txt=f"Status Sentimen: {data['sentiment']}", ln=True)
    pdf.set_font("Arial", 'I', 10)
    aman_headline = data['headline'].encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 6, txt=f"Headline Terakhir: {aman_headline}")

    pdf.ln(15)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.set_font("Arial", 'I', 8)
    disclaimer_pdf = (
        "DISCLAIMER: Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan "
        "algoritma indikator teknikal dan fundamental. Seluruh informasi yang disajikan bukan "
        "merupakan ajakan, rekomendasi pasti, atau paksaan untuk membeli/menjual saham. "
        "Keputusan investasi dan trading sepenuhnya menjadi tanggung jawab pribadi masing-masing "
        "investor. Selalu terapkan manajemen risiko yang baik dan Do Your Own Research (DYOR) "
        "dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal."
    )
    pdf.multi_cell(0, 4, txt=disclaimer_pdf)

    return bytes(pdf.output(dest='S').encode('latin1'))


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_teknikal():
    """Entry point modul analisa teknikal — dipanggil dari app.py."""
    # JANGAN panggil st.set_page_config() di sini — sudah ada di app.py

    # --- TAMPILAN WEB & LOGO ---
    logo_file = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_file):
        logo_file = "../logo_expert_stock_pro.png"

    if os.path.exists(logo_file):
        with open(logo_file, "rb") as f:
            encoded_img = base64.b64encode(f.read()).decode()
        st.markdown(
            f'<div style="display:flex;justify-content:center;margin-bottom:10px;">'
            f'<img src="data:image/png;base64,{encoded_img}" width="150"></div>',
            unsafe_allow_html=True
        )

    st.markdown(
        "<h1 style='text-align:center;'>📈 Analisa Teknikal Pro (6 Dimensi Lengkap)</h1>",
        unsafe_allow_html=True
    )
    st.markdown("---")

    # --- INPUT ---
    st.markdown("### ⚙️ Pengaturan Manajemen Risiko (Position Sizing)")
    col_inp, col_mod, col_rsk = st.columns([1, 1, 1])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Contoh: BBRI):", value="BBRI").upper()
    with col_mod:
        total_modal_input = st.number_input(
            "Total Modal Investasi (Rp):",
            min_value=100_000, value=10_000_000, step=1_000_000, format="%d"
        )
    with col_rsk:
        max_risiko_input = st.number_input(
            "Maks Risiko / Kerugian (Rp):",
            min_value=10_000, value=250_000, step=50_000, format="%d"
        )

    ticker_bersih = ticker_input.strip().upper().replace(".JK", "")
    ticker        = ticker_bersih + ".JK"

    if st.button(f"Jalankan Analisa Lengkap {ticker_bersih}"):
        with st.spinner("Mengevaluasi tren, indikator, pola, risiko, dan sentimen berita..."):

            data = get_full_stock_data(ticker)
            df   = data['history']
            info = data.get('info', {})

            if df.empty or len(df) < 200:
                st.error("Data tidak mencukupi untuk analisa MA200. Mohon coba saham lain.")
                return

            df        = calculate_technical_pro(df)
            last      = df.iloc[-1]
            prev_1    = df.iloc[-2]
            prev_5    = df.iloc[-5]
            curr_price = last['Close']
            atr        = last['ATR']

            # Sentimen berita
            sentimen_status, sentimen_headline = analyze_news_sentiment(ticker)

            # ── STATUS SYARIAH — lookup dari liquid/pre_liquid ──────────────
            # Koreksi: tidak ada fungsi is_syariah() global; pakai get_syariah_status()
            status_syariah = get_syariah_status(ticker_bersih)

            # ── INFO HEADER ─────────────────────────────────────────────────
            nama_perusahaan = info.get('longName', ticker_bersih)
            sektor_mentah   = info.get('sector', 'Sektor Tidak Diketahui')
            sektor_id       = translate_sector(sektor_mentah)

            # ── SCORING KOMPREHENSIF (100 POIN) ─────────────────────────────
            score = 0

            # i) Tren Utama (30 poin)
            if curr_price > last['MA200']: score += 10
            if curr_price > last['MA50']:  score += 10
            if curr_price > last['MA20']:  score += 10

            # ii) Konfirmasi Volume & Likuiditas (20 poin)
            curr_vol  = last['Volume']   if not pd.isna(last['Volume'])   else 0
            avg_vol20 = last['Vol_MA20'] if not pd.isna(last['Vol_MA20']) else 0
            vwap_val  = last['VWAP_20']  if not pd.isna(last['VWAP_20'])  else curr_price

            if curr_vol > avg_vol20:    score += 10
            if curr_price > vwap_val:   score += 10

            # iii) Kekuatan Momentum (20 poin)
            if 50 <= last['RSI'] <= 70:             score += 5
            if last['RSI'] > prev_1['RSI']:         score += 5
            if last['MACD'] > last['Signal_Line']:  score += 10

            # iv) Agresivitas Aksi Harga (20 poin)
            if last['EMA9'] > last['EMA21']:        score += 10
            if curr_price > prev_1['Close']:        score += 10

            # v) Volatilitas & Risiko (10 poin)
            if curr_price > last['MA20'] and curr_price <= last['BB_Upper']:
                score += 10

            # ── TIER SINYAL ─────────────────────────────────────────────────
            if score >= 85:
                signal     = "BOLEH TRADING"
                confidence = "Boleh Trading sesuai Trading Plan yang sudah dibuatkan."
            elif score >= 70:
                signal     = "HATI-HATI"
                confidence = (
                    "Indikator cukup mendukung untuk saham ini dimasukkan dalam daftar "
                    "pantauan ('watch list'), atau boleh trading dengan lot sebagian dulu."
                )
            else:
                signal     = "DILARANG TRADING"
                confidence = (
                    "Tidak Disarankan untuk melakukan trading dulu, karena belum didukung "
                    "oleh indikator teknikal yang memadai."
                )

            # ── TAMPILAN HEADER ─────────────────────────────────────────────
            st.markdown(
                f"<h2 style='text-align:center;color:#4ade80;'>"
                f"🏢 {ticker_bersih} - {nama_perusahaan}</h2>",
                unsafe_allow_html=True
            )
            st.markdown(
                f"<h5 style='text-align:center;margin-top:-15px;color:#a3a3a3;'>"
                f"Sektor: {sektor_id} | {status_syariah}</h5>",
                unsafe_allow_html=True
            )
            st.write("")

            st.header("🏆 SKOR TEKNIKAL")
            st.progress(score / 100.0)

            teks_hasil = f"**Skor: {score}/100** — Sinyal: **{signal}**\n\n*{confidence}*"
            if score >= 85:   st.success(teks_hasil)
            elif score >= 70: st.warning(teks_hasil)
            else:             st.error(teks_hasil)

            st.markdown("---")

            # ── VARIABEL ANALISA ─────────────────────────────────────────────
            main_trend    = "UPTREND" if curr_price > last['MA200'] else "DOWNTREND"
            weekly_trend  = "Bullish" if last['MA50'] > prev_5['MA50'] else "Bearish"
            res_level     = df['High'].tail(20).max()
            sup_level     = df['Low'].tail(20).min()
            arah_rsi      = "↗️ Naik" if last['RSI'] > prev_1['RSI'] else "↘️ Turun"
            is_div        = (
                "Terdeteksi (Bullish)"
                if (curr_price < prev_5['Close'] and last['RSI'] > prev_5['RSI'])
                else "Tidak Terdeteksi"
            )

            if last['Close'] > prev_1['Close']:   market_pressure = "Buying Pressure (Naik)"
            elif last['Close'] < prev_1['Close']: market_pressure = "Selling Pressure (Turun)"
            else:                                 market_pressure = "Neutral (Stagnan)"

            posisi_ma_pdf  = "Di atas MA20 (Kuning)" if curr_price > last['MA20'] else "Di bawah MA20 (Kuning)"
            rsi_status     = 'Overbought' if last['RSI'] > 70 else ('Oversold' if last['RSI'] < 30 else 'Neutral')
            arah_rsi_pdf   = "Naik" if last['RSI'] > prev_1['RSI'] else "Turun"
            macd_teks      = 'Bullish Cross' if last['MACD'] > last['Signal_Line'] else 'Bearish'
            bb_range_curr  = last['BB_Upper'] - last['BB_Lower']
            bb_range_avg   = (df['BB_Upper'] - df['BB_Lower']).mean()
            volatilitas_teks = 'Tinggi' if bb_range_curr > bb_range_avg else 'Rendah'
            pattern_teks   = (
                "Doji"
                if abs(last['Open'] - last['Close']) < (last['High'] - last['Low']) * 0.1
                else "Normal"
            )
            momentum_teks  = 'Kuat' if last['RSI'] > 50 else 'Lemah'

            # ── TRADING PLAN BERDASARKAN SKOR ───────────────────────────────
            entry_atas   = curr_price
            caption_entry = caption_sl = caption_tp = ""

            if score >= 85:
                diskon_entry = curr_price * 0.96
                entry_bawah  = max(last['EMA9'], diskon_entry)
                avg_entry    = (entry_atas + entry_bawah) / 2
                sl_atr       = avg_entry - (2.5 * atr)
                sl_hard      = avg_entry * 0.92
                sl_final     = max(sl_atr, sl_hard)
                risk_nominal = avg_entry - sl_final
                tp_final     = avg_entry + (risk_nominal * 2)
                caption_entry = "Maks Koreksi 4% / EMA9"
                caption_sl    = "Maks Risk 8% / 2.5x ATR"
                caption_tp    = "Risk/Reward Ratio 1 : 2.0"

            elif score >= 70:
                diskon_entry = curr_price * 0.985
                vwap_now     = last['VWAP_20'] if not pd.isna(last['VWAP_20']) else curr_price
                entry_bawah  = max(vwap_now, diskon_entry)
                avg_entry    = (entry_atas + entry_bawah) / 2
                sl_atr       = avg_entry - (1.5 * atr)
                sl_hard      = avg_entry * 0.97
                sl_final     = max(sl_atr, sl_hard)
                risk_nominal = avg_entry - sl_final
                tp_final     = avg_entry + (risk_nominal * 1.5)
                caption_entry = "Maks Koreksi 1.5% / VWAP"
                caption_sl    = "Maks Risk 3% / 1.5x ATR"
                caption_tp    = "Risk/Reward Ratio 1 : 1.5"

            else:
                entry_bawah = avg_entry = sl_final = tp_final = curr_price

            risk_pct_riil = ((avg_entry - sl_final) / avg_entry) * 100 if avg_entry > 0 else 0
            tp_pct_riil   = ((tp_final  - avg_entry) / avg_entry) * 100 if avg_entry > 0 else 0

            # ── POSITION SIZING ──────────────────────────────────────────────
            if score >= 70:
                risk_per_share     = avg_entry - sl_final
                max_lembar_risk    = (max_risiko_input / risk_per_share) if risk_per_share > 0 else 0
                max_lembar_capital = (0.15 * total_modal_input) / avg_entry if avg_entry > 0 else 0
                final_lot          = int(min(max_lembar_risk, max_lembar_capital) // 100)
            else:
                max_lembar_risk = max_lembar_capital = 0
                final_lot = 0

            # ── CHART ────────────────────────────────────────────────────────
            fig = make_subplots(
                rows=3, cols=1, shared_xaxes=True,
                vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2]
            )
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'], name="Price"
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df.index, y=df['MA20'],
                line=dict(color='yellow', width=2), name="MA20"
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df.index, y=df['MA200'],
                line=dict(color='purple', width=2), name="MA200"
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df.index, y=df['BB_Upper'],
                line=dict(color='rgba(173,216,230,0.2)'), name="BB Upper"
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df.index, y=df['BB_Lower'],
                line=dict(color='rgba(173,216,230,0.2)'),
                fill='tonexty', name="BB Lower"
            ), row=1, col=1)
            fig.add_trace(go.Bar(
                x=df.index, y=df['MACD_Hist'], name="MACD Hist"
            ), row=2, col=1)
            fig.add_trace(go.Scatter(
                x=df.index, y=df['RSI'],
                line=dict(color='white'), name="RSI"
            ), row=3, col=1)

            fig.update_layout(
                height=900, template="plotly_dark",
                xaxis_rangeslider_visible=False
            )
            st.plotly_chart(fig, use_container_width=True)

            # ── PENYAJIAN DATA ───────────────────────────────────────────────
            st.markdown("---")
            c1, c2 = st.columns(2)

            with c1:
                st.subheader("1. TREND ANALYSIS")
                st.write(f"• **Trend Utama (Daily):** {main_trend}")
                st.write(f"• **Trend Weekly/Monthly:** {weekly_trend}")
                st.write(f"• **Support/Resist:** Rp {sup_level:,.0f} / Rp {res_level:,.0f}")

                st.subheader("2. INDIKATOR TEKNIKAL")
                st.write(f"• **Posisi MA:** Harga {'di atas' if curr_price > last['MA20'] else 'di bawah'} MA20 Kuning")
                st.write(f"• **RSI:** {last['RSI']:.1f} ({arah_rsi} | {rsi_status})")
                st.write(f"• **MACD:** {macd_teks}")
                st.write(f"• **Volatilitas:** {volatilitas_teks}")

            with c2:
                st.subheader("3. PATTERN RECOGNITION")
                st.write(f"• **Candlestick:** {pattern_teks}")
                st.write("• **Chart Pattern:** Potensi Konsolidasi / Channeling")
                st.write(f"• **Divergence:** {is_div}")

                st.subheader("4. MOMENTUM & STRENGTH")
                st.write(f"• **Momentum:** {momentum_teks}")
                st.write(f"• **Pressure:** {market_pressure}")

                st.subheader("6. SENTIMEN BERITA (Dimensi Tambahan)")
                if sentimen_status == "Positif":
                    st.success(f"• **Sentimen:** {sentimen_status}\n\n• **Headline:** {sentimen_headline}")
                elif sentimen_status == "Negatif":
                    st.error(f"• **Sentimen:** {sentimen_status}\n\n• **Headline:** {sentimen_headline}")
                else:
                    st.info(f"• **Sentimen:** {sentimen_status}\n\n• **Headline:** {sentimen_headline}")

            st.markdown("---")
            st.subheader("5. TRADING PLAN & POSITION SIZING")

            if score < 70:
                st.error("🚨 **Tidak Disarankan untuk Melakukan Trading dulu, karena belum didukung oleh indikator teknikal yang memadai.**")
            else:
                st.write(f"#### Harga Saat Ini: Rp {int(curr_price):,.0f}")
                s1, s2, s3 = st.columns(3)
                with s1:
                    st.metric("AREA ENTRY", f"Rp {int(entry_bawah):,.0f} - {int(entry_atas):,.0f}")
                    st.caption(caption_entry)
                with s2:
                    st.error(f"**STOP LOSS**\n\n**Rp {int(sl_final):,.0f} (-{risk_pct_riil:.1f}%)**")
                    st.caption(caption_sl)
                with s3:
                    st.success(f"**TARGET PROFIT**\n\n**Rp {int(tp_final):,.0f} (+{tp_pct_riil:.1f}%)**")
                    st.caption(caption_tp)

                st.markdown("<br>", unsafe_allow_html=True)
                st.info(
                    f"💡 **KALKULASI UKURAN LOT MAKSIMAL (POSITION SIZING)**\n"
                    f"Dihitung berdasarkan Modal **Rp {total_modal_input:,.0f}** "
                    f"& Maks Risiko **Rp {max_risiko_input:,.0f}**"
                )
                col_ps1, col_ps2, col_ps3 = st.columns(3)
                with col_ps1:
                    st.metric("Risk-Based Limit", f"{int(max_lembar_risk):,.0f} Lembar")
                    st.caption("Batas Berdasarkan Toleransi Kerugian")
                with col_ps2:
                    st.metric("Capital-Based Limit (15%)", f"{int(max_lembar_capital):,.0f} Lembar")
                    st.caption("Batas Hindari All-In")
                with col_ps3:
                    st.success(f"**FINAL MAX LOT: {final_lot} LOT**")
                    st.caption("Diambil Angka Paling Konservatif")

            st.markdown("---")

            # ── PDF ──────────────────────────────────────────────────────────
            pdf_data = {
                'ticker':          ticker_bersih,
                'nama_perusahaan': nama_perusahaan,
                'sektor':          sektor_id,
                'syariah':         status_syariah,
                'waktu':           datetime.now().strftime("%d-%m-%Y %H:%M"),
                'harga':           curr_price,
                'score':           score,
                'signal':          signal,
                'confidence':      confidence,
                'main_trend':      main_trend,
                'weekly_trend':    weekly_trend,
                'sup_level':       sup_level,
                'res_level':       res_level,
                'posisi_ma':       posisi_ma_pdf,
                'rsi_text':        f"{last['RSI']:.1f} ({arah_rsi_pdf} | {rsi_status})",
                'macd_text':       macd_teks,
                'volatilitas':     volatilitas_teks,
                'candlestick':     pattern_teks,
                'divergence':      is_div,
                'momentum':        momentum_teks,
                'pressure':        market_pressure,
                'entry_bawah':     entry_bawah,
                'entry_atas':      entry_atas,
                'sl_final':        sl_final,
                'risk_pct':        risk_pct_riil,
                'tp_final':        tp_final,
                'tp_pct':          tp_pct_riil,
                'caption_entry':   caption_entry,
                'caption_sl':      caption_sl,
                'caption_tp':      caption_tp,
                'sentiment':       sentimen_status,
                'headline':        sentimen_headline,
                'total_modal':     total_modal_input,
                'max_risiko':      max_risiko_input,
                'final_lot':       final_lot,
            }

            pdf_bytes = generate_pdf_fpdf(pdf_data)
            if pdf_bytes:
                st.download_button(
                    label="📄 Unduh Laporan Analisa (PDF)",
                    data=pdf_bytes,
                    file_name=f"ExpertStockPro_Teknikal_{ticker_bersih}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

            st.warning(
                "⚠️ **DISCLAIMER:** Laporan analisa ini dihasilkan secara otomatis menggunakan "
                "perhitungan algoritma indikator teknikal dan fundamental. Seluruh informasi yang "
                "disajikan bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk "
                "membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi "
                "tanggung jawab pribadi masing-masing investor. Selalu terapkan manajemen risiko "
                "yang baik dan *Do Your Own Research* (DYOR) dan pertimbangkan profil risiko "
                "sebelum mengambil keputusan di pasar modal."
            )
