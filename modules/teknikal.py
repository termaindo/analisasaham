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

# --- MENGGUNAKAN RELATIVE IMPORT SEBAGAI PENGAMAN ---
try:
    from modules.data_loader import get_full_stock_data
    from modules.universe import is_syariah
except ModuleNotFoundError:
    # Fallback jika dipanggil dari internal folder
    from .data_loader import get_full_stock_data
    from .universe import is_syariah

def translate_sector(sector_en):
    mapping = {
        "Financial Services": "Jasa Keuangan",
        "Basic Materials": "Bahan Baku & Tambang",
        "Energy": "Energi",
        "Communication Services": "Telekomunikasi",
        "Consumer Cyclical": "Konsumsi Siklikal",
        "Consumer Defensive": "Konsumsi Non-Siklikal",
        "Healthcare": "Kesehatan",
        "Industrials": "Industri",
        "Real Estate": "Properti",
        "Technology": "Teknologi",
        "Utilities": "Utilitas"
    }
    return mapping.get(sector_en, sector_en)

# --- FUNGSI DIMENSI KE-6: ANALISA SENTIMEN BERITA ---
def analyze_news_sentiment(ticker_symbol):
    try:
        tk = yf.Ticker(ticker_symbol)
        news = tk.news
        if not news:
            return "Netral", "Tidak ada berita terbaru."
        
        bullish_words = ['laba', 'naik', 'tumbuh', 'akuisisi', 'dividen', 'ekspansi', 'profit', 'bullish', 'lonjak', 'target', 'beli', 'buy', 'investasi', 'positif']
        bearish_words = ['rugi', 'turun', 'anjlok', 'gagal', 'susut', 'bearish', 'jual', 'sell', 'koreksi', 'denda', 'kasus', 'gugat', 'inflasi', 'negatif']
        
        score = 0
        latest_title = news[0].get('title', 'Berita tidak tersedia')
        
        for n in news[:5]: # Ambil maksimal 5 berita terbaru
            title_lower = n.get('title', '').lower()
            for bw in bullish_words:
                if bw in title_lower: score += 1
            for bear_w in bearish_words:
                if bear_w in title_lower: score -= 1
                
        if score > 0: return "Positif", latest_title
        elif score < 0: return "Negatif", latest_title
        else: return "Netral", latest_title
    except:
        return "Netral", "Gagal memuat berita."

# --- FUNGSI ANALISA TEKNIKAL MENDALAM ---
def calculate_technical_pro(df):
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA50'] = df['Close'].rolling(50).mean()
    df['MA200'] = df['Close'].rolling(200).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal_Line']
    
    df['BB_Mid'] = df['MA20']
    df['BB_Std'] = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + (2 * df['BB_Std'])
    df['BB_Lower'] = df['BB_Mid'] - (2 * df['BB_Std'])

    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP_20'] = (df['Typical_Price'] * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['Value'] = df['Close'] * df['Volume']
    
    return df

# --- FUNGSI PDF MENGGUNAKAN FPDF ---
def generate_pdf_fpdf(data, logo_path="logo_expert_stock_pro.png"):
    """Membangun PDF dari awal menggunakan fpdf dengan Header Box Hitam elegan"""
    pdf = FPDF()
    pdf.add_page()
    
    # Menghapus emoji untuk fpdf karena hanya mendukung Latin-1
    status_syariah_teks = "Syariah" if "✅" in data['syariah'] else "Non-Syariah"
    
    # --- 1. HEADER BOX HITAM ---
    pdf.set_fill_color(20, 20, 20)  # Warna Hitam (Almost Black)
    pdf.rect(0, 0, 210, 25, 'F')    # Lebar A4 = 210mm
    
    # Cari lokasi logo jika dipanggil dari sub-folder
    if not os.path.exists(logo_path):
        if os.path.exists("../logo_expert_stock_pro.png"):
            logo_path = "../logo_expert_stock_pro.png"

    # a) LOGO dengan Bingkai Emas
    if os.path.exists(logo_path):
        pdf.set_fill_color(218, 165, 32) # Goldenrod color
        pdf.rect(10, 3, 19, 19, 'F')
        pdf.image(logo_path, x=10.5, y=3.5, w=18, h=18)
    
    # b) & c) NAMA APLIKASI & MODUL (Teks Putih)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    pdf.set_xy(35, 8) 
    pdf.cell(0, 10, "Expert Stock Pro - Analisa Teknikal Pro", ln=True)
    
    # Reset posisi Y ke bawah kotak hitam
    pdf.set_y(28)
    
    # --- 2. HYPERLINK SUMBER ---
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(0, 0, 255)  # Warna Biru
    pdf.cell(0, 5, "Sumber: https://lynk.id/hahastoresby", ln=True, align='C', link="https://lynk.id/hahastoresby")
    pdf.ln(2)
    
    # --- 3. NAMA SAHAM & PERUSAHAAN (CENTER) ---
    pdf.set_text_color(0, 0, 0) # Kembali ke Hitam
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 8, f"{data['ticker']} - {data['nama_perusahaan']}", ln=True, align='C')
    
    # --- 4. INFO SEKTOR & SYARIAH (CENTER) ---
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, f"Sektor: {data['sektor']} | Status: {status_syariah_teks}", ln=True, align='C')
    pdf.ln(2)
    
    # --- 5. INFO TANGGAL & HARGA (RATA KANAN) ---
    pdf.set_font("Arial", 'B', 10)
    waktu_analisa = data.get('waktu', datetime.now().strftime("%d-%m-%Y %H:%M"))
    pdf.cell(0, 5, f"Analisa: {waktu_analisa} | Harga: Rp {data['harga']:,.0f}", ln=True, align='R')
    
    # Garis Bawah Header
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y()+2, 200, pdf.get_y()+2)
    pdf.ln(5)
    
    # ---------------------------------
    # MULAI KONTEN UTAMA TEKNIKAL
    # ---------------------------------
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt=f"SKOR TEKNIKAL: {data['score']}/100", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, txt=f"Sinyal: {data['signal']} ({data['confidence']})", ln=True)
    
    pdf.ln(5)
    
    # --- DIMENSI 1: TREND ANALYSIS ---
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 7, txt="1. TREND ANALYSIS", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, txt=f"- Trend Utama (Daily)  : {data['main_trend']}", ln=True)
    pdf.cell(0, 5, txt=f"- Trend Wkly/Monthly : {data['weekly_trend']}", ln=True)
    pdf.cell(0, 5, txt=f"- Support / Resist     : Rp {data['sup_level']:,.0f} / Rp {data['res_level']:,.0f}", ln=True)
    pdf.ln(3)

    # --- DIMENSI 2: INDIKATOR TEKNIKAL ---
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 7, txt="2. INDIKATOR TEKNIKAL", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, txt=f"- Posisi MA   : {data['posisi_ma']}", ln=True)
    pdf.cell(0, 5, txt=f"- RSI         : {data['rsi_text']}", ln=True)
    pdf.cell(0, 5, txt=f"- MACD        : {data['macd_text']}", ln=True)
    pdf.cell(0, 5, txt=f"- Volatilitas : {data['volatilitas']}", ln=True)
    pdf.ln(3)

    # --- DIMENSI 3: PATTERN RECOGNITION ---
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 7, txt="3. PATTERN RECOGNITION", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, txt=f"- Candlestick   : {data['candlestick']}", ln=True)
    pdf.cell(0, 5, txt=f"- Chart Pattern : Potensi Konsolidasi / Channeling", ln=True)
    pdf.cell(0, 5, txt=f"- Divergence    : {data['divergence']}", ln=True)
    pdf.ln(3)

    # --- DIMENSI 4: MOMENTUM & STRENGTH ---
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 7, txt="4. MOMENTUM & STRENGTH", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 5, txt=f"- Momentum : {data['momentum']}", ln=True)
    pdf.cell(0, 5, txt=f"- Pressure : {data['pressure']}", ln=True)
    pdf.ln(3)

    # --- DIMENSI 5: TRADING PLAN ---
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, txt="5. TRADING PLAN", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, txt=f"Harga Saat Ini : Rp {data['harga']:,.0f}", ln=True)
    pdf.cell(0, 6, txt=f"Area Entry     : Rp {data['entry_bawah']:,.0f} - Rp {data['entry_atas']:,.0f}", ln=True)
    pdf.cell(0, 6, txt=f"Stop Loss      : Rp {data['sl_final']:,.0f} (-{data['risk_pct']:.1f}%)", ln=True)
    pdf.cell(0, 6, txt=f"Target         : Rp {data['tp_final']:,.0f} (+{data['tp_pct']:.1f}%)", ln=True)
    
    pdf.ln(5)
    
    # --- DIMENSI 6: SENTIMEN BERITA ---
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, txt="6. ANALISA SENTIMEN BERITA", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, txt=f"Status Sentimen: {data['sentiment']}", ln=True)
    pdf.set_font("Arial", 'I', 10)
    # Gunakan encoding/replace agar karakter aneh dari berita (seperti kutip melengkung) tidak error di fpdf
    aman_headline = data['headline'].encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 6, txt=f"Headline Terakhir: {aman_headline}")
    
    pdf.ln(15)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.set_font("Arial", 'I', 8)
    pdf.multi_cell(0, 4, txt="**DISCLAIMER:** Semua informasi, analisa teknikal, analisa fundamental, ataupun sinyal trading dan analisa-analisa lain yang disediakan di modul ini hanya untuk tujuan edukasi dan informasi. Ini bukan merupakan rekomendasi, ajakan, atau nasihat keuangan untuk membeli atau menjual saham tertentu. Keputusan investasi sepenuhnya berada di tangan Anda. Harap lakukan riset Anda sendiri (*Do Your Own Research*) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.")
    
    return bytes(pdf.output(dest='S').encode('latin1'))

def run_teknikal():
    # --- TAMPILAN WEB & LOGO ---
    logo_file = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_file):
        logo_file = "../logo_expert_stock_pro.png"
        
    # Tampilkan Logo di Web bagian TENGAH dengan ukuran BESAR
    if os.path.exists(logo_file):
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            st.image(logo_file, use_container_width=True)
        st.markdown("<h1 style='text-align: center;'>📈 Analisa Teknikal Pro (6 Dimensi Lengkap)</h1>", unsafe_allow_html=True)
    else:
        st.markdown("<h1 style='text-align: center;'>📈 Analisa Teknikal Pro (6 Dimensi Lengkap)</h1>", unsafe_allow_html=True)
        st.warning("⚠️ File logo belum ditemukan.")
        
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Contoh: BBRI):", value="BBRI").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Jalankan Analisa Lengkap {ticker_input}"):
        with st.spinner("Mengevaluasi tren, indikator, pola, dan sentimen berita..."):
            data = get_full_stock_data(ticker)
            df = data['history']
            info = data.get('info', {})
            
            if df.empty or len(df) < 200:
                st.error("Data tidak mencukupi untuk analisa MA200. Mohon coba saham lain.")
                return

            df = calculate_technical_pro(df)
            last = df.iloc[-1]
            prev_1 = df.iloc[-2] 
            prev_5 = df.iloc[-5] 
            curr_price = last['Close']
            atr = last['ATR']

            # --- AMBIL SENTIMEN BERITA ---
            sentimen_status, sentimen_headline = analyze_news_sentiment(ticker)

            # ==========================================
            # LOGIKA SCORING KOMPREHENSIF (100 POIN)
            # ==========================================
            score = 0
            
            # i) Tren Utama (30 Poin)
            if curr_price > last['MA200']: score += 10
            if curr_price > last['MA50']: score += 10
            if curr_price > last['MA20']: score += 10
            
            # ii) Konfirmasi Volume & Likuiditas (20 Poin)
            curr_vol = last['Volume'] if not pd.isna(last['Volume']) else 0
            avg_vol_20 = last['Vol_MA20'] if not pd.isna(last['Vol_MA20']) else 0
            vwap_val = last['VWAP_20'] if not pd.isna(last['VWAP_20']) else curr_price
            
            if curr_vol > avg_vol_20: score += 10
            if curr_price > vwap_val: score += 10
            
            # iii) Kekuatan Momentum (20 Poin)
            if 50 <= last['RSI'] <= 70: score += 5
            if last['RSI'] > prev_1['RSI']: score += 5 
            if last['MACD'] > last['Signal_Line']: score += 10
                
            # iv) Agresivitas Aksi Harga (20 Poin)
            if last['EMA9'] > last['EMA21']: score += 10
            if curr_price > prev_1['Close']: score += 10
            
            # v) Volatilitas & Risiko (10 Poin)
            if (curr_price > last['MA20']) and (curr_price <= last['BB_Upper']): score += 10

            # Mapping Rekomendasi
            if score >= 80:
                signal = "STRONG BUY"
                confidence = "Sangat Tinggi (Target Operasi Utama)"
            elif score >= 60:
                signal = "BUY / ACCUMULATE"
                confidence = "Tinggi (Menunggu Konfirmasi Penuh)"
            elif score >= 40:
                signal = "HOLD / WAIT"
                confidence = "Menengah (Sideways / Transisi)"
            else:
                signal = "SELL / AVOID"
                confidence = "Rendah (Hancur Lebur Secara Teknikal)"

            # ==========================================
            # TAMPILAN HEADER
            # ==========================================
            clean_ticker = ticker_input.replace(".JK", "")
            nama_perusahaan = info.get('longName', clean_ticker)
            sektor_mentah = info.get('sector', 'Sektor Tidak Diketahui')
            sektor_id = translate_sector(sektor_mentah)
            status_syariah = "✅ Syariah" if is_syariah(clean_ticker) else "✖️ Non-Syariah"

            st.markdown(f"<h2 style='text-align: center; color: #4ade80;'>🏢 {clean_ticker} - {nama_perusahaan}</h2>", unsafe_allow_html=True)
            st.markdown(f"<h5 style='text-align: center; margin-top: -15px; color: #a3a3a3;'>Sektor: {sektor_id} | {status_syariah}</h5>", unsafe_allow_html=True)
            st.write("")
            
            st.header("🏆 SKOR TEKNIKAL")
            st.progress(score / 100.0)
            
            teks_hasil = f"**Skor: {score}/100** — Sinyal: **{signal}** ({confidence})"
            if score >= 80: st.success(teks_hasil)
            elif score >= 60: st.info(teks_hasil)
            elif score >= 40: st.warning(teks_hasil)
            else: st.error(teks_hasil)
            
            st.markdown("---")

            # --- INDIKATOR ---
            main_trend = "UPTREND" if curr_price > last['MA200'] else "DOWNTREND"
            weekly_trend = "Bullish" if last['MA50'] > prev_5['MA50'] else "Bearish"
            res_level = df['High'].tail(20).max()
            sup_level = df['Low'].tail(20).min()
            arah_rsi = "↗️ Naik" if last['RSI'] > prev_1['RSI'] else "↘️ Turun"
            is_div = "Terdeteksi (Bullish)" if (curr_price < prev_5['Close'] and last['RSI'] > prev_5['RSI']) else "Tidak Terdeteksi"
            
            # KOREKSI LOGIKA PRESSURE: Bandingkan Close Hari Ini vs Close Kemarin
            if last['Close'] > prev_1['Close']:
                market_pressure = "Buying Pressure (Naik)"
            elif last['Close'] < prev_1['Close']:
                market_pressure = "Selling Pressure (Turun)"
            else:
                market_pressure = "Neutral (Stagnan)"

            posisi_ma_pdf = "Di atas MA20 (Kuning)" if curr_price > last['MA20'] else "Di bawah MA20 (Kuning)"
            rsi_status = 'Overbought' if last['RSI']>70 else 'Oversold' if last['RSI']<30 else 'Neutral'
            arah_rsi_pdf = "Naik" if last['RSI'] > prev_1['RSI'] else "Turun"
            macd_teks = 'Bullish Cross' if last['MACD'] > last['Signal_Line'] else 'Bearish'
            volatilitas_teks = 'Tinggi' if (last['BB_Upper']-last['BB_Lower']) > (df['BB_Upper']-df['BB_Lower']).mean() else 'Rendah'
            pattern_teks = "Doji" if abs(last['Open']-last['Close']) < (last['High']-last['Low'])*0.1 else "Normal"
            momentum_teks = 'Kuat' if last['RSI'] > 50 else 'Lemah'
            
            # --- PEMBUATAN TRADING PLAN ---
            entry_atas = curr_price
            diskon_4_persen = curr_price * 0.96
            ema9_sekarang = last['EMA9']
            entry_bawah = max(ema9_sekarang, diskon_4_persen)
            
            avg_entry = (entry_atas + entry_bawah) / 2

            sl_atr = avg_entry - (2.5 * atr)
            sl_hard = avg_entry * 0.92 
            sl_final = max(sl_atr, sl_hard) 

            risk_nominal = avg_entry - sl_final
            tp_nominal = avg_entry + (risk_nominal * 2)
            tp_final = tp_nominal

            risk_pct_riil = ((avg_entry - sl_final) / avg_entry) * 100
            tp_pct_riil = ((tp_final - avg_entry) / avg_entry) * 100
            rrr_riil = round(tp_pct_riil / risk_pct_riil, 1) if risk_pct_riil > 0 else 0

            # --- VISUALISASI CHART ---
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
            
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="MA20 (Kuning)"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA200'], line=dict(color='purple', width=2), name="MA200"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], line=dict(color='rgba(173, 216, 230, 0.2)'), name="BB Upper"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], line=dict(color='rgba(173, 216, 230, 0.2)'), fill='tonexty', name="BB Lower"), row=1, col=1)

            fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD Hist"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='white'), name="RSI"), row=3, col=1)
            
            fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- PENYAJIAN DATA ---
            st.markdown("---")
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("1. TREND ANALYSIS")
                st.write(f"• **Trend Utama (Daily):** {main_trend}")
                st.write(f"• **Trend Weekly/Monthly:** {weekly_trend}")
                st.write(f"• **Support/Resist:** Rp {sup_level:,.0f} / Rp {res_level:,.0f}")
                
                st.subheader("2. INDIKATOR TEKNIKAL")
                st.write(f"• **Posisi MA:** Harga {'di atas' if curr_price > last['MA20'] else 'di bawah'} MA20 Kuning")
                st.write(f"• **RSI:** {last['RSI']:.1f} ({arah_rsi} | {'Overbought' if last['RSI']>70 else 'Oversold' if last['RSI']<30 else 'Neutral'})")
                st.write(f"• **MACD:** {'Bullish Cross' if last['MACD'] > last['Signal_Line'] else 'Bearish'}")
                st.write(f"• **Volatilitas:** {'Tinggi' if (last['BB_Upper']-last['BB_Lower']) > (df['BB_Upper']-df['BB_Lower']).mean() else 'Rendah'}")

            with c2:
                st.subheader("3. PATTERN RECOGNITION")
                pattern = "Doji" if abs(last['Open']-last['Close']) < (last['High']-last['Low'])*0.1 else "Normal"
                st.write(f"• **Candlestick:** {pattern}")
                st.write(f"• **Chart Pattern:** Potensi Konsolidasi / Channeling")
                st.write(f"• **Divergence:** {is_div}")

                st.subheader("4. MOMENTUM & STRENGTH")
                st.write(f"• **Momentum:** {'Kuat' if last['RSI'] > 50 else 'Lemah'}")
                st.write(f"• **Pressure:** {market_pressure}")

                st.subheader("6. SENTIMEN BERITA (Dimensi Tambahan)")
                if sentimen_status == "Positif":
                    st.success(f"• **Sentimen:** {sentimen_status}\n\n• **Headline:** {sentimen_headline}")
                elif sentimen_status == "Negatif":
                    st.error(f"• **Sentimen:** {sentimen_status}\n\n• **Headline:** {sentimen_headline}")
                else:
                    st.info(f"• **Sentimen:** {sentimen_status}\n\n• **Headline:** {sentimen_headline}")

            st.markdown("---")
            st.subheader("5. TRADING SIGNAL & PLAN")
            
            # Tambahan Format Header Harga Saat Ini di UI
            st.write(f"#### Harga Saat Ini: Rp {int(curr_price):,.0f}")
            
            s1, s2, s3 = st.columns(3)
            with s1:
                st.metric("AREA ENTRY", f"Rp {int(entry_bawah):,.0f} - {int(entry_atas):,.0f}")
                st.caption("Max Koreksi 4% / EMA9")
            with s2:
                st.error(f"**STOP LOSS**\n\n**Rp {int(sl_final):,.0f} (-{risk_pct_riil:.1f}%)**")
                st.caption("Max Risk 8% / 2.5x ATR")
            with s3:
                st.success(f"**TARGET PROFIT**\n\n**Rp {int(tp_final):,.0f} (+{tp_pct_riil:.1f}%)**")
                st.caption(f"Risk/Reward Ratio 1 : {rrr_riil}")

            st.markdown("---")

            # ==========================================
            # TOMBOL DOWNLOAD PDF MENGGUNAKAN FPDF
            # ==========================================
            pdf_data = {
                'ticker': clean_ticker,
                'nama_perusahaan': nama_perusahaan,
                'sektor': sektor_id,
                'syariah': status_syariah,
                'waktu': datetime.now().strftime("%d-%m-%Y %H:%M"),
                'harga': curr_price,
                'score': score,
                'signal': signal,
                'confidence': confidence,
                'main_trend': main_trend,
                'weekly_trend': weekly_trend,
                'sup_level': sup_level,
                'res_level': res_level,
                'posisi_ma': posisi_ma_pdf,
                'rsi_text': f"{last['RSI']:.1f} ({arah_rsi_pdf} | {rsi_status})",
                'macd_text': macd_teks,
                'volatilitas': volatilitas_teks,
                'candlestick': pattern_teks,
                'divergence': "Terdeteksi (Bullish)" if (curr_price < prev_5['Close'] and last['RSI'] > prev_5['RSI']) else "Tidak Terdeteksi",
                'momentum': momentum_teks,
                'pressure': market_pressure,
                'entry_bawah': entry_bawah,
                'entry_atas': entry_atas,
                'sl_final': sl_final,
                'risk_pct': risk_pct_riil,
                'tp_final': tp_final,
                'tp_pct': tp_pct_riil,
                'sentiment': sentimen_status,
                'headline': sentimen_headline
            }
            
            pdf_bytes = generate_pdf_fpdf(pdf_data)
            
            if pdf_bytes:
                st.download_button(
                    label="📄 Unduh Laporan Analisa (PDF)",
                    data=pdf_bytes,
                    file_name=f"Expert_Stock_Pro_Teknikal_{clean_ticker}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            # --- DISCLAIMER (UI) ---
            st.warning("""
            **DISCLAIMER:** Semua informasi, analisa teknikal, analisa fundamental, ataupun sinyal trading dan analisa-analisa lain yang disediakan di modul ini hanya untuk tujuan edukasi dan informasi. Ini bukan merupakan rekomendasi, ajakan, atau nasihat keuangan untuk membeli atau menjual saham tertentu. Keputusan investasi sepenuhnya berada di tangan Anda. Harap lakukan riset Anda sendiri (*Do Your Own Research*) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.
            """)
