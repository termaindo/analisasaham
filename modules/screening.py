import streamlit as st
import pandas as pd
import numpy as np
import pytz
import os
import base64
import holidays
import io
import plotly.express as px
import concurrent.futures
from datetime import datetime
from fpdf import FPDF 
from modules.data_loader import get_full_stock_data 
from modules.universe import UNIVERSE_SAHAM, is_syariah, get_sector_data 

# --- FUNGSI FORMAT RUPIAH ---
def format_rp(angka):
    """Fungsi untuk memformat angka menjadi format ribuan dengan titik"""
    if isinstance(angka, str):
        return angka
    return f"{int(angka):,}".replace(',', '.')

# --- 1. FUNGSI AUDIO ALERT ---
def play_alert_sound():
    audio_html = """
    <audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>
    """
    st.components.v1.html(audio_html, height=0)

# --- 2. ANALISA ROTASI SEKTOR ---
def analyze_sector_momentum(full_results_df):
    if full_results_df.empty:
        return pd.DataFrame(), []
    sector_summary = full_results_df.groupby('Sektor').agg({
        'Skor': 'mean',
        'Ticker': 'count'
    }).rename(columns={'Ticker': 'Jumlah_Saham', 'Skor': 'Avg_Score'}).sort_values('Avg_Score', ascending=False)
    
    # UPDATE: Standar kekuatan sektor dinaikkan menjadi 70 menyesuaikan kondisi pasar
    leading_sectors = sector_summary[sector_summary['Avg_Score'] >= 70].index.tolist()
    return sector_summary, leading_sectors

# --- 3. FUNGSI GENERATOR PDF (INSTITUTIONAL FORMAT) ---
def export_to_pdf(hasil_lolos, trade_mode, session, sector_report, logo_path="logo_expert_stock_pro.png"):
    pdf = FPDF()
    pdf.add_page()
    
    # Header Box
    pdf.set_fill_color(20, 20, 20)
    pdf.rect(0, 0, 210, 25, 'F')
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=10, y=3, w=18, h=18)
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    pdf.set_xy(35, 8) 
    pdf.cell(0, 10, "Expert Stock Pro - Ultimate Alpha Report", ln=True)
    
    # Hyperlink Sumber 
    pdf.set_y(28)
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(0, 0, 255) 
    pdf.cell(0, 5, "Sumber: https://bit.ly/sahampintar", ln=True, align='C', link="https://bit.ly/sahampintar")
    
    # Info Strategi dan Waktu (WIB)
    pdf.ln(3)
    pdf.set_text_color(0, 0, 0) 
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 8, f"Strategi: {trade_mode} | Sesi: {session}", ln=True, align='C')
    
    tz = pytz.timezone('Asia/Jakarta')
    waktu_cetak = datetime.now(tz).strftime('%d-%m-%Y %H:%M WIB')
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 5, f"Dicetak: {waktu_cetak}", ln=True, align='R')
    pdf.ln(2)

    # --- SEKSI OVERVIEW SEKTOR ---
    if not sector_report.empty:
        pdf.set_fill_color(220, 235, 255)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 7, "  MARKET OVERVIEW (SEKTOR TERKUAT HARI INI)", 0, ln=True, fill=True)
        pdf.set_font("Arial", '', 9)
        top_sectors = ", ".join(sector_report.index[:3].tolist())
        pdf.multi_cell(190, 6, f" Aliran dana (Capital Flow) terbesar saat ini terdeteksi pada sektor: {top_sectors}")
        pdf.ln(3)

    # --- SEKSI A: TOP 3 PRIORITAS ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "A. TOP 3 PRIORITAS TRANSAKSI (HIGH CONVICTION)", 0, ln=True, fill=True)
    pdf.ln(2)

    top_3 = hasil_lolos[:3]
    if top_3:
        for item in top_3:
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(190, 6, f"{item['Ticker']} - {item['Sektor']} | Syariah: {item['Syariah']} | Score: {item['Skor']}/100", ln=True) 
            
            pdf.set_font("Arial", '', 9)
            pdf.cell(60, 5, f"Entry: {item['Entry']}", 0)
            pdf.set_text_color(0, 128, 0)
            pdf.cell(65, 5, f"TP Target: Rp {format_rp(item['TP'])} ({item['Pct_Reward']})", 0)
            pdf.set_text_color(200, 0, 0)
            pdf.cell(65, 5, f"Stop Loss: Rp {format_rp(item['SL'])} ({item['Pct_Risk']})", ln=True)
            pdf.set_text_color(0, 0, 0)
            
            # KOREKSI: Membersihkan emoji dari status agar FPDF tidak error
            status_pdf = item['Status'].replace("🔥", "").replace("🎯", "").strip()
            
            pdf.set_font("Arial", 'B', 8)
            pdf.cell(190, 5, f"Batas Alokasi Maksimal: {item['Lot_Maks']} ({status_pdf})", ln=True)
            
            pdf.set_font("Arial", 'I', 8)
            pdf.multi_cell(190, 4, f"Logic: {item['Logic']}")
            pdf.ln(2)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)
    else:
        pdf.ln(3)
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(190, 6, "Belum ada saham yang memenuhi kriteria ketat institusi saat ini.", ln=True, align='C')
        pdf.ln(3)

    # --- SEKSI B: WATCHLIST 4-10 ---
    watchlist = hasil_lolos[3:10]
    if watchlist:
        pdf.ln(3)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(190, 8, "B. RADAR WATCHLIST (RANK 4-10)", 0, ln=True, fill=True)
        pdf.ln(2)
        
        for w in watchlist:
            pdf.set_font("Arial", 'B', 9)
            pdf.cell(190, 5, f"{w['Ticker']} ({w['Sektor'][:20]}) | Syariah: {w['Syariah']} | Skor: {w['Skor']}", ln=True)
            
            pdf.set_font("Arial", '', 8)
            pdf.cell(40, 5, f"Entry: {w['Entry']}", 0)
            pdf.set_text_color(0, 128, 0)
            pdf.cell(50, 5, f"TP: Rp {format_rp(w['TP'])} ({w['Pct_Reward']})", 0)
            pdf.set_text_color(200, 0, 0)
            pdf.cell(50, 5, f"SL: Rp {format_rp(w['SL'])} ({w['Pct_Risk']})", 0)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(50, 5, f"Maks: {w['Lot_Maks']}", ln=True)

            pdf.set_font("Arial", 'I', 7)
            pdf.multi_cell(190, 4, f"Logic: {w['Logic']}")
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)

    # --- DISCLAIMER FOOTER PDF ---
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, "DISCLAIMER:", ln=True) 
    pdf.set_font("Arial", 'I', 7)
    disclaimer_text = ("Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma indikator teknikal dan fundamental. Seluruh informasi yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi tanggung jawab pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik dan Do Your Own Research (DYOR) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.")
    pdf.multi_cell(190, 4, disclaimer_text)

    return pdf.output(dest='S').encode('latin-1', 'ignore')

# --- 4. INDIKATOR TEKNIKAL ---

def calculate_supertrend(df, period=10, multiplier=2):
    """Menghitung Supertrend. Mengembalikan kolom 'Supertrend' dan 'Supertrend_Dir' (1=bullish, -1=bearish)."""
    hl2 = (df['High'] + df['Low']) / 2
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()

    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)

    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=int)

    for i in range(1, len(df)):
        if df['Close'].iloc[i] > upper_band.iloc[i - 1]:
            direction.iloc[i] = 1
        elif df['Close'].iloc[i] < lower_band.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
            if direction.iloc[i] == 1 and lower_band.iloc[i] < lower_band.iloc[i - 1]:
                lower_band.iloc[i] = lower_band.iloc[i - 1]
            if direction.iloc[i] == -1 and upper_band.iloc[i] > upper_band.iloc[i - 1]:
                upper_band.iloc[i] = upper_band.iloc[i - 1]

        supertrend.iloc[i] = lower_band.iloc[i] if direction.iloc[i] == 1 else upper_band.iloc[i]

    df['Supertrend'] = supertrend
    df['Supertrend_Dir'] = direction
    return df

def calculate_psar(df, af_start=0.02, af_step=0.02, af_max=0.2):
    """Menghitung Parabolic SAR. Mengembalikan kolom 'PSAR'."""
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values
    n = len(df)

    psar = close.copy()
    bull = True
    af = af_start
    ep = low[0]
    hp = high[0]
    lp = low[0]

    for i in range(2, n):
        if bull:
            psar[i] = psar[i - 1] + af * (hp - psar[i - 1])
            psar[i] = min(psar[i], low[i - 1], low[i - 2])
            if low[i] < psar[i]:
                bull = False
                psar[i] = hp
                lp = low[i]
                af = af_start
                ep = lp
            else:
                if high[i] > hp:
                    hp = high[i]
                    af = min(af + af_step, af_max)
                ep = hp
        else:
            psar[i] = psar[i - 1] + af * (lp - psar[i - 1])
            psar[i] = max(psar[i], high[i - 1], high[i - 2])
            if high[i] > psar[i]:
                bull = True
                psar[i] = lp
                hp = high[i]
                af = af_start
                ep = hp
            else:
                if low[i] < lp:
                    lp = low[i]
                    af = min(af + af_step, af_max)
                ep = lp

    df['PSAR'] = psar
    df['PSAR_Bull'] = df['Close'] > df['PSAR']
    return df

def calculate_indicators(df, trade_mode):
    """Menghitung semua indikator teknikal sesuai mode."""
    # --- ATR (dipakai semua mode untuk SL) ---
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()

    if trade_mode == "Day Trading":
        # Supertrend (10, 2)
        df = calculate_supertrend(df, period=10, multiplier=2)

        # VWAP (rolling 5-bar sebagai proxy intraday)
        df['VWAP'] = (df['Close'] * df['Volume']).rolling(window=5).sum() / df['Volume'].rolling(window=5).sum()

        # MACD (12, 26, 9)
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

        # RSI (9)
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(9).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(9).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))

        # PSAR
        df = calculate_psar(df)

    else:  # Swing Trading
        # Supertrend (10, 3)
        df = calculate_supertrend(df, period=10, multiplier=3)

        # MA Structure
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()

        # MACD (12, 26, 9)
        ema12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema26 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        # RSI (14)
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))

        # PSAR
        df = calculate_psar(df)

    return df

# --- 5. MARKET SESSION ---
def get_market_session():
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    if now.weekday() >= 5: return "AKHIR PEKAN", "Tutup."
    if now.date() in holidays.ID(years=now.year): return "LIBUR NASIONAL", "Tutup."
    curr_time = now.hour + now.minute/60
    if curr_time < 9.0: return "PRA-PASAR", "Wait."
    elif 9.0 <= curr_time <= 16.0: return "LIVE MARKET", "Trading."
    else: return "PASCA-PASAR", "Analysis."

# --- FUNGSI PEKERJA UNTUK MULTITHREADING ---
def process_single_stock(ticker, trade_mode, mtf_filter):
    ticker_bersih = ticker.replace(".JK", "")
    try:
        data = get_full_stock_data(ticker)
        df = calculate_indicators(data['history'], trade_mode)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        curr_price = last['Close']
        avg_val_20 = (df['Close'] * df['Volume']).rolling(20).mean().iloc[-1]
        sektor_nama, _ = get_sector_data(ticker_bersih)

        score = 0
        alasan = []

        if trade_mode == "Day Trading":
            # --- SCORING DAY TRADE ---

            # 1. Supertrend (10, 2): 30 Poin
            if last['Supertrend_Dir'] == 1:
                score += 30
                alasan.append("Supertrend Bullish (10,2)")

            # 2. VWAP Alignment: 25 Poin
            if curr_price > last['VWAP']:
                score += 25
                alasan.append("Price > VWAP")

            # 3. MACD Golden Cross (12,26,9): 20 Poin
            if last['MACD'] > last['MACD_Signal'] and prev['MACD'] <= prev['MACD_Signal']:
                score += 20
                alasan.append("MACD Golden Cross")

            # 4. RSI Momentum (9), rentang ideal 45-70: 15 Poin
            if 45 <= last['RSI'] <= 70:
                score += 15
                alasan.append(f"RSI Momentum ({last['RSI']:.1f})")

            # 5. PSAR Acceleration (titik di bawah harga): 10 Poin
            if last['PSAR_Bull']:
                score += 10
                alasan.append("PSAR Bullish (titik di bawah harga)")

            # MTF Filter: untuk day trade, cukup pastikan supertrend bullish
            if mtf_filter and last['Supertrend_Dir'] != 1:
                return None

        else:  # Swing Trading
            # --- SCORING SWING TRADE ---

            # 1. Supertrend (10, 3): 35 Poin
            if last['Supertrend_Dir'] == 1:
                score += 35
                alasan.append("Supertrend Bullish (10,3)")

            # 2. MA Structure: 20 Poin — Price > MA50 AND MA20 > MA50
            if curr_price > last['MA50'] and last['MA20'] > last['MA50']:
                score += 20
                alasan.append("MA Structure (Price>MA50, MA20>MA50)")

            # 3. MACD Histogram mendaki (Growing): 20 Poin
            if last['MACD_Hist'] > prev['MACD_Hist']:
                score += 20
                alasan.append("MACD Histogram Growing")

            # 4. RSI Trend (14), memantul dari level 50: 15 Poin
            if last['RSI'] > 50 and prev['RSI'] <= 50:
                score += 15
                alasan.append(f"RSI Bounce dari 50 ({last['RSI']:.1f})")

            # 5. PSAR Confirm arah tren: 10 Poin
            if last['PSAR_Bull']:
                score += 10
                alasan.append("PSAR Konfirmasi Tren Naik")

            # MTF Filter: pastikan supertrend bullish dan MA structure terpenuhi
            if mtf_filter and not (last['Supertrend_Dir'] == 1 and curr_price > last['MA50']):
                return None

        syariah_status = "Ya" if is_syariah(ticker_bersih) else "Tidak"
        return {
            "Ticker": ticker_bersih, "Sektor": sektor_nama, "Syariah": syariah_status, "Skor": score,
            "Harga": int(curr_price), "ATR": last['ATR'], "Alasan": alasan, "RSI": last['RSI']
        }
    except:
        return None

# --- 6. MODUL UTAMA ---
def run_screening():
    st.set_page_config(page_title="🔍 Screening Saham Harian", layout="wide")
    
    # --- PILIHAN MODE UI ---
    st.markdown("<h4 style='text-align: center;'>Pilih Mode Aplikasi</h4>", unsafe_allow_html=True)
    ui_mode = st.radio(
        "👁️ Tampilan Aplikasi:", 
        ["🌱 Mode Praktis (Untuk Pemula)", "💼 Mode Pro (Indikator Lengkap)"], 
        horizontal=True,
        label_visibility="collapsed"
    )
    st.markdown("---")
    
    if "Praktis" in ui_mode:
        st.markdown("<h1 style='text-align: center;'>🔍 Asisten Saham Pintar</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Mencarikan saham potensial dengan perhitungan aman secara otomatis.</p>", unsafe_allow_html=True)
    else:
        st.markdown("<h1 style='text-align: center;'>🔍 Screening Saham Harian Pro</h1>", unsafe_allow_html=True)

    st.markdown("---")

    # --- FITUR GLOSARIUM (KAMUS TRADER) ---
    with st.expander("📖 Glosarium Istilah (Kamus Trader) - Klik untuk Membaca"):
        st.markdown("""
        **Panduan Singkat Membaca Hasil Analisa:**
        * **Entry:** Rentang harga yang disarankan untuk mulai membeli/mengantri saham. Jangan mengejar harga (*fomo*) jika sudah terlewat jauh di atas area ini.
        * **TP (Take Profit):** Target harga ideal untuk merealisasikan keuntungan (menjual saham).
        * **SL (Stop Loss):** Batas harga toleransi kerugian. Jika harga turun menyentuh level ini, sangat disarankan untuk menjual saham (*cut loss*) demi melindungi sisa modal Anda dari kerugian yang lebih besar.
        * **RRR (Risk-Reward Ratio):** Rasio perbandingan antara potensi keuntungan dengan potensi kerugian. Semakin besar angkanya, semakin bagus transaksinya. (Contoh 1.5x berarti potensi untungnya 1,5 kali lipat dari risiko ruginya).
        * **ATR (Average True Range):** Indikator yang mengukur tingkat volatilitas (gejolak/ayunan) harga saham. Semakin tinggi ATR, rentang gerak saham tersebut semakin liar. Sistem ini otomatis menggunakan ATR untuk menentukan titik Stop Loss yang logis agar tidak mudah 'tersapu' oleh ayunan harian.
        * **Maks Lot (Position Sizing):** Rekomendasi porsi maksimal jumlah Lot yang aman untuk dibeli, dihitung secara otomatis oleh sistem berdasarkan total modal Anda dan batasan kerugian yang Anda izinkan. Ini menjaga portofolio Anda agar tidak 'All-In' atau over-konsentrasi di satu saham saja.
        * **MA (Moving Average):** Harga rata-rata saham dalam rentang waktu tertentu. MA50 untuk rata-rata menengah (50 hari), MA200 untuk rata-rata jangka panjang (200 hari). Saham yang sehat umumnya bergerak di atas garis MA ini.
        * **VWAP (Volume Weighted Average Price):** Rata-rata harga saham intraday yang telah dibobotkan dengan volumenya. Ini adalah indikator patokan utama para trader institusi.
        """)

    # --- INFORMASI JAM OPTIMAL & PEMILIHAN MODE ---
    if "Praktis" in ui_mode:
        st.write("### 1️⃣ Pilih Gaya Beli Anda")
        trade_mode = st.radio("Suka memantau layar setiap hari atau disimpan beberapa hari?", 
                              ["Day Trading (Beli Pagi, Jual Siang/Sore)", "Swing Trading (Beli & Simpan Beberapa Hari)"], horizontal=True)
        trade_mode = "Day Trading" if "Day" in trade_mode else "Swing Trading"
    else:
        st.write("### ⚙️ Pemilihan Strategi & Waktu Analisa")
        st.info("⏰ **Panduan Waktu Analisa Optimal:** \n"
                "- **Day Trading:** 09.30 - 11.00 WIB (Untuk momentum harian tertinggi).\n"
                "- **Swing Trading:** > 16.00 WIB (Untuk konfirmasi harga penutupan yang solid).")
        trade_mode = st.radio("Pilih Strategi Trading (Mode Analisa):", ["Day Trading", "Swing Trading"], horizontal=True)

    # --- PENGATURAN & KALKULATOR RISIKO BERDASARKAN MODE ---
    if "Praktis" in ui_mode:
        st.write("### 2️⃣ Kalkulator Keamanan Dana")
        mtf_filter = True
        sector_boost = True
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            total_modal = st.number_input("Berapa Total Uang Anda untuk Saham? (Rp):", min_value=1000000, value=10000000, step=1000000)
        with col_m2:
            modal_risiko = st.number_input("Batas maksimal uang yang rela hilang per saham? (Rp):", min_value=10000, value=100000, step=50000)
        
        batas_alokasi_rp = total_modal * 0.15
        st.success(f"Sistem akan memastikan Anda tidak membeli saham melebihi batas aman (Maksimal Rp {format_rp(batas_alokasi_rp)} per saham).")
    else:
        with st.expander("🛠️ Pengaturan Filter & Manajemen Risiko (Klik untuk Edit)", expanded=False):
            st.write("**Filter Institusi Tambahan:**")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                mtf_filter = st.checkbox("Hanya saham yang searah dengan tren besar", value=True)
            with col_f2:
                sector_boost = st.checkbox("Hanya saham dari Sektor yang kuat", value=True)
            
            st.markdown("---")
            st.write("**💼 Kalkulator Lot Maksimal (Institutional Position Sizing):**")
            st.caption("Manajemen risiko profesional berdasarkan Modal & Batas Kerugian.")
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                total_modal = st.number_input("Total Modal Portofolio Anda (Rp):", min_value=1000000, value=100000000, step=5000000)
            with col_m2:
                modal_risiko = st.number_input("Nominal Maksimal Siap Rugi (Rp):", min_value=10000, value=1000000, step=50000)
            
            risiko_persen = (modal_risiko / total_modal) * 100 if total_modal > 0 else 0
            batas_alokasi_persen = 15.0
            batas_alokasi_rp = total_modal * (batas_alokasi_persen / 100)
            
            st.markdown(
                f"""
                <div style="background-color:#d4edda; border-left: 5px solid #28a745; padding: 10px; border-radius: 5px;">
                    <p style="margin:0; font-size:12px; color:#155724;">Total Modal: <b>Rp {format_rp(total_modal)}</b></p>
                    <p style="margin:0; font-size:12px; color:#155724;">Nominal Siap Rugi (<b>{risiko_persen:.1f}%</b> dari modal):</p>
                    <h4 style="margin:0; color:#155724;">Rp {format_rp(modal_risiko)}</h4>
                    <p style="margin:0; margin-top:5px; font-size:10px; color:#155724;"><i>*Sistem membatasi maks beli 15% modal (Rp {format_rp(batas_alokasi_rp)}) per saham agar tidak over-konsentrasi.</i></p>
                </div>
                """, unsafe_allow_html=True
            )

    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    curr_time_float = now.hour + now.minute/60
    is_weekend = now.weekday() >= 5
    session, status_desc = get_market_session()

    # --- TAMPILAN STATUS MARKET BERDASARKAN MODE ---
    if "Tutup" in status_desc:
        st.error(f"🛑 **Bursa Saham Sedang Tutup ({session})**" if "Praktis" in ui_mode else f"**Status Market:** {session} ({status_desc})")
    elif "Wait" in status_desc:
        st.warning(f"⏳ **Bursa Saham Belum Buka (Sesi Pra-Pasar)**" if "Praktis" in ui_mode else f"**Status Market:** {session} ({status_desc})")
    elif "Analysis" in status_desc:
        st.info(f"🌙 **Bursa Saham Sudah Tutup (Sesi Pasca-Pasar)**" if "Praktis" in ui_mode else f"**Status Market:** {session} ({status_desc})")
    else:
        st.success(f"🟢 **Bursa Saham Sedang Buka (Live Market)**" if "Praktis" in ui_mode else f"**Status Market:** {session} ({status_desc})")

    st.markdown("---")

    tombol_cari = "🚀 CARIKAN SAHAM UNTUK SAYA" if "Praktis" in ui_mode else f"🚀 JALANKAN ANALISA {trade_mode.upper()}"
    
    if st.button(tombol_cari):
        saham_list = [f"{t}.JK" for tickers in UNIVERSE_SAHAM.values() for t in tickers]
        saham_list = list(set(saham_list))
        
        raw_results = []
        
        loading_header = st.empty()
        loading_header.write("### 🔄 Mesin sedang memilah ratusan saham. Mohon tunggu...")
        
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        total_saham = len(saham_list)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(process_single_stock, ticker, trade_mode, mtf_filter): ticker for ticker in saham_list}
            
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
        
        final_picks = []
        for stock in raw_results:
            f_score = stock['Skor']
            
            if sector_boost and stock['Sektor'] in leading_sectors:
                f_score += 15; stock['Alasan'].append(f"Sector Hot: {stock['Sektor']}")

            # --- PROTEKSI BERLAPIS: SL/TP ---
            # ATR SL
            sl_mult = 1.8 if trade_mode == "Day Trading" else 2.5
            atr_sl = int(stock['Harga'] - (sl_mult * stock['ATR']))

            # Hard Cap SL: maks -3% (Day Trade) atau -8% (Swing)
            max_loss_pct = 0.03 if trade_mode == "Day Trading" else 0.08
            hard_cap_sl = int(stock['Harga'] * (1 - max_loss_pct))

            # Pilih SL yang paling ketat (nilai terbesar/terdekat dengan harga)
            sl = max(atr_sl, hard_cap_sl)

            # TP dengan RR minimal 1.5x (Day) atau 2.0x (Swing)
            rr_min = 1.5 if trade_mode == "Day Trading" else 2.0
            tp = int(stock['Harga'] + (stock['Harga'] - sl) * rr_min)

            rrr = (tp - stock['Harga']) / (stock['Harga'] - sl) if stock['Harga'] > sl else 0

            risiko_per_lembar = stock['Harga'] - sl
            if risiko_per_lembar > 0:
                lembar_maks_risiko = modal_risiko / risiko_per_lembar
                lembar_maks_alokasi = batas_alokasi_rp / stock['Harga']
                
                lembar_final = min(lembar_maks_risiko, lembar_maks_alokasi)
                lot_maksimal = int(lembar_final / 100)
            else:
                lot_maksimal = 0

            pct_risk = ((stock['Harga'] - sl) / stock['Harga']) * 100 if stock['Harga'] > 0 else 0
            pct_reward = ((tp - stock['Harga']) / stock['Harga']) * 100 if stock['Harga'] > 0 else 0

            if f_score >= 70 and rrr >= 1.4:
                final_picks.append({
                    "Ticker": stock['Ticker'], "Sektor": stock['Sektor'], "Skor": f_score,
                    "Harga_Saat_Ini": int(stock['Harga']),
                    "Syariah": stock['Syariah'],
                    "Entry": f"Rp {format_rp(stock['Harga']*0.99)} - {format_rp(stock['Harga'])}",
                    "SL": sl, "TP": tp, "RRR": f"{rrr:.1f}x",
                    "Status": "🔥 FULL SIZING" if f_score >= 85 else "🎯 CICIL SEBAGIAN",
                    "Logic": " | ".join(stock['Alasan']),
                    "Lot_Maks": f"{format_rp(lot_maksimal)} Lot",
                    "Pct_Risk": f"-{pct_risk:.1f}%",
                    "Pct_Reward": f"+{pct_reward:.1f}%"
                })

        final_picks.sort(key=lambda x: x['Skor'], reverse=True)
        st.session_state.final_picks = final_picks[:10] 
        st.session_state.sector_report = sector_report
        st.session_state.pdf_session = session 
        
        st.session_state.analysis_done = True 
        
        if any(p['Skor'] >= 85 for p in st.session_state.final_picks): play_alert_sound()

    # --- DISPLAY UI ---
    if st.session_state.get('analysis_done', False):
        res = st.session_state.get('final_picks', [])
        top_3 = res[:3]
        watchlist = res[3:10]

        st.subheader("🌐 Kondisi Pasar Saat Ini" if "Praktis" in ui_mode else "🌐 Market Overview")
        c1, c2 = st.columns([2, 1])
        with c1:
            if 'sector_report' in st.session_state and not st.session_state.sector_report.empty:
                fig = px.bar(st.session_state.sector_report.reset_index(), x='Sektor', y='Avg_Score', color='Avg_Score', color_continuous_scale='Greens', title="Kekuatan Sektor Saat Ini")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Data sektor tidak tersedia.")
                
        with c2:
            st.write("**Sektor Paling Ramai (Banyak Uang Masuk):**" if "Praktis" in ui_mode else "**Top Leading Sectors:**")
            if 'sector_report' in st.session_state and not st.session_state.sector_report.empty:
                for s in st.session_state.sector_report.index[:3]: st.success(s)

        st.markdown("---")
        
        st.header(f"🏆 Pilihan Terbaik Saat Ini" if "Praktis" in ui_mode else f"🏆 Top 3 Prioritas {trade_mode}")
        if top_3:
            cols = st.columns(len(top_3))
            for idx, item in enumerate(top_3):
                with cols[idx]:
                    st.markdown(f"### {item['Ticker']}")
                    st.write(f"**Sektor:** {item['Sektor']}")
                    st.write(f"**Syariah:** {item['Syariah']}")
                    
                    if "Praktis" in ui_mode:
                        st.info(f"🛒 **Beli di harga:** {item['Entry']}")
                        st.success(f"💰 **Jual Untung di:** Rp {format_rp(item['TP'])} ({item['Pct_Reward']})")
                        st.error(f"🛑 **Jual Rugi (Batas Aman) jika menyentuh:** Rp {format_rp(item['SL'])} ({item['Pct_Risk']})")
                        st.warning(f"📦 **Maksimal Beli:** {item['Lot_Maks']} ({item['Status']})")
                    else:
                        st.metric("Skor Institusi", f"{item['Skor']}/100 Pts", item['Status'])
                        st.write(f"**Target (TP):** Rp {format_rp(item['TP'])} ({item['Pct_Reward']})")
                        st.write(f"**Proteksi (SL):** Rp {format_rp(item['SL'])} ({item['Pct_Risk']})")
                        st.info(f"Area Entry: {item['Entry']}")
                        st.warning(f"🛡️ **Maks. Aman:** {item['Lot_Maks']}")
                        st.caption(f"💡 {item['Logic']}")
        else:
            st.warning("Mesin belum menemukan saham yang benar-benar aman saat ini. Silakan coba beberapa saat lagi.")

        if watchlist:
            st.markdown("---")
            st.subheader(f"📋 Daftar Cadangan (Peringkat 4-10)" if "Praktis" in ui_mode else f"📋 Radar Watchlist (Rank 4-10)")
            df_watch_display = pd.DataFrame(watchlist).copy()
            
            df_watch_display['SL'] = df_watch_display.apply(lambda x: f"Rp {format_rp(x['SL'])} ({x['Pct_Risk']})", axis=1)
            df_watch_display['TP'] = df_watch_display.apply(lambda x: f"Rp {format_rp(x['TP'])} ({x['Pct_Reward']})", axis=1)
            
            if "Praktis" in ui_mode:
                # Mengubah nama kolom agar lebih mudah dipahami
                df_watch_display = df_watch_display.rename(columns={
                    "Sektor": "Industri", "Entry": "Area Beli", "SL": "Jual Rugi (Batas Aman)", "TP": "Jual Untung (Target)"
                })
                kolom_tampil = ["Ticker", "Industri", "Syariah", "Area Beli", "Jual Rugi (Batas Aman)", "Jual Untung (Target)", "Lot_Maks", "Status"]
            else:
                kolom_tampil = ["Ticker", "Sektor", "Syariah", "Skor", "Status", "Entry", "SL", "TP", "RRR", "Lot_Maks"]
                
            st.dataframe(df_watch_display[kolom_tampil], use_container_width=True, hide_index=True)
        
        st.markdown("<br><hr>", unsafe_allow_html=True)
        st.caption("⚠️ **DISCLAIMER:** Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma indikator teknikal dan fundamental. Seluruh informasi yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi tanggung jawab pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik dan *Do Your Own Research* (DYOR) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.")
        st.markdown("<br>", unsafe_allow_html=True)
        
        waktu_cetak_pdf = datetime.now(tz).strftime('%Y%m%d_%H%M')
        pdf_data = export_to_pdf(res, trade_mode, st.session_state.pdf_session, st.session_state.sector_report)
        st.download_button(
            label="📥 UNDUH LAPORAN SCREENING LENGKAP (PDF)", 
            data=pdf_data, 
            file_name=f"ExpertStockPro_{trade_mode}_{waktu_cetak_pdf}.pdf", 
            mime="application/pdf", 
            use_container_width=True
        )

if __name__ == "__main__":
    run_screening()
