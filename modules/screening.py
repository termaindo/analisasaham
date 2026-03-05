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
    leading_sectors = sector_summary[sector_summary['Avg_Score'] >= 60].index.tolist()
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
    pdf.cell(0, 10, "Expert Stock Pro - Screening Saham Harian Pro", ln=True)
    
    # Hyperlink Sumber 
    pdf.set_y(28)
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(0, 0, 255) 
    pdf.cell(0, 5, "Sumber: https://lynk.id/hahastoresby", ln=True, align='C', link="https://lynk.id/hahastoresby")
    
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

    # --- SEKSI A: TOP 3 PRIORITAS ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "A. TOP 3 PRIORITAS TRANSAKSI (HIGH CONVICTION)", 0, ln=True, fill=True)
    pdf.ln(2)

    top_3 = hasil_lolos[:3]
    for item in top_3:
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 6, f"{item['Ticker']} - {item['Sektor']} | Score: {item['Skor']}/100", ln=True) 
        
        pdf.set_font("Arial", '', 9)
        pdf.cell(60, 5, f"Entry: {item['Entry']}", 0)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(60, 5, f"TP Target: Rp {format_rp(item['TP'])}", 0)
        pdf.set_text_color(200, 0, 0)
        pdf.cell(60, 5, f"Stop Loss: Rp {format_rp(item['SL'])}", ln=True)
        pdf.set_text_color(0, 0, 0)
        
        pdf.set_font("Arial", 'I', 8)
        pdf.multi_cell(190, 4, f"Logic: {item['Logic']}")
        pdf.ln(2)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(2)

    # --- SEKSI B: WATCHLIST 4-10 ---
    watchlist = hasil_lolos[3:10]
    if watchlist:
        pdf.ln(3)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(190, 8, "B. RADAR WATCHLIST (RANK 4-10)", 0, ln=True, fill=True)
        pdf.ln(2)
        
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(20, 6, "Ticker", 1, 0, 'C')
        pdf.cell(45, 6, "Sektor", 1, 0, 'C')
        pdf.cell(15, 6, "Skor", 1, 0, 'C')
        pdf.cell(35, 6, "Entry", 1, 0, 'C')
        pdf.cell(25, 6, "SL", 1, 0, 'C')
        pdf.cell(25, 6, "TP", 1, 0, 'C')
        pdf.cell(25, 6, "Maks Lot", 1, 1, 'C')
        
        pdf.set_font("Arial", '', 8)
        for w in watchlist:
            pdf.cell(20, 6, w['Ticker'], 1, 0, 'C')
            pdf.cell(45, 6, w['Sektor'][:20], 1, 0, 'C')
            pdf.cell(15, 6, str(w['Skor']), 1, 0, 'C')
            pdf.cell(35, 6, w['Entry'], 1, 0, 'C')
            pdf.cell(25, 6, format_rp(w['SL']), 1, 0, 'C')
            pdf.cell(25, 6, format_rp(w['TP']), 1, 0, 'C')
            pdf.cell(25, 6, w['Lot_Maks'], 1, 1, 'C')

    # --- DISCLAIMER FOOTER PDF ---
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, "DISCLAIMER:", ln=True) 
    pdf.set_font("Arial", 'I', 7)
    disclaimer_text = ("Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma indikator teknikal dan fundamental. Seluruh informasi yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi tanggung jawab pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik dan Do Your Own Research (DYOR) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.")
    pdf.multi_cell(190, 4, disclaimer_text)

    return pdf.output(dest='S').encode('latin-1', 'ignore')

# --- 4. INDIKATOR TEKNIKAL (MTF ENGINE) ---
def calculate_indicators(df, trade_mode):
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['VWAP'] = (df['Close'] * df['Volume']).rolling(window=5).sum() / df['Volume'].rolling(window=5).sum()
    
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

        is_macro_bullish = curr_price > last['MA200']
        is_medium_bullish = curr_price > last['MA50']
        is_micro_bullish = curr_price > last['VWAP'] if trade_mode == "Day Trading" else curr_price > last['EMA9']

        if mtf_filter and not (is_macro_bullish and is_medium_bullish): 
            return None

        score = 0
        alasan = []
        
        if is_macro_bullish: score += 20; alasan.append("Macro UP (MA200)")
        if is_medium_bullish: score += 15; alasan.append("Medium UP (MA50)")
        if is_micro_bullish: 
            score += 15
            alasan.append("Micro Momentum (VWAP)" if trade_mode == "Day Trading" else "Micro Momentum (EMA9)")
        
        if trade_mode == "Day Trading":
            if curr_price > prev['High']:
                score += 5; alasan.append("Breakout Prev. High")
        else: 
            if last['EMA9'] > last['EMA21']:
                score += 5; alasan.append("Momentum Cross (EMA9>21)")
        
        if last['Volume'] > df['Vol_SMA20'].iloc[-1]: score += 20; alasan.append("Volume Spike")
        if avg_val_20 > (1e10 if trade_mode == "Day Trading" else 5e9): 
            score += 10; alasan.append("Inst. Liquidity")

        return {
            "Ticker": ticker_bersih, "Sektor": sektor_nama, "Skor": score, 
            "Harga": int(curr_price), "ATR": last['ATR'], "Alasan": alasan, "RSI": last['RSI']
        }
    except: 
        return None

# --- 6. MODUL UTAMA ---
def run_screening():
    st.set_page_config(page_title="🔍 Screening Saham Harian Pro", layout="wide")
    st.markdown("<h1 style='text-align: center;'>🔍 Screening Saham Harian Pro</h1>", unsafe_allow_html=True)
    st.markdown("---")

    # --- INFORMASI JAM OPTIMAL & PEMILIHAN MODE ---
    st.write("### ⚙️ Pemilihan Strategi & Waktu Analisa")
    
    st.info("⏰ **Panduan Waktu Analisa Optimal:** \n"
            "- **Day Trading:** 09.30 - 11.00 WIB (Untuk momentum harian tertinggi).\n"
            "- **Swing Trading:** > 16.00 WIB (Untuk konfirmasi harga penutupan yang solid).")
    
    trade_mode = st.radio("Pilih Strategi Trading (Mode Analisa):", ["Day Trading", "Swing Trading"], horizontal=True)

    # --- PENGATURAN & KALKULATOR DI HALAMAN UTAMA (DALAM EXPANDER) ---
    with st.expander("🛠️ Pengaturan Filter & Manajemen Risiko (Klik untuk Edit)", expanded=False):
        st.write("**Filter Institusi Tambahan:**")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            # BUG FIX: Tanda kutip berlebih dihapus
            mtf_filter = st.checkbox("Hanya saham yang searah dengan tren besar", value=True)
        with col_f2:
            # BUG FIX: Tanda kutip berlebih dihapus
            sector_boost = st.checkbox("Hanya saham dari Sektor yang kuat", value=True)
        
        st.markdown("---")
        st.write("**💼 Kalkulator Lot Maksimal (Institutional Position Sizing):**")
        st.caption("Manajemen risiko profesional berdasarkan Modal & Batas Kerugian.")
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            total_modal = st.number_input("Total Modal Portofolio Anda (Rp):", min_value=1000000, value=100000000, step=5000000)
        with col_m2:
            modal_risiko = st.number_input("Nominal Maksimal Siap Rugi (Rp):", min_value=10000, value=1000000, step=50000, help="Ketik angka murni tanpa titik.")
        
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

    if "Tutup" in status_desc:
        st.error(f"**Status Market:** {session} ({status_desc})")
    else:
        st.info(f"**Status Market:** {session} ({status_desc})")

    if trade_mode == "Day Trading":
        is_golden = 9.5 <= curr_time_float <= 11.0 and not is_weekend
        if is_golden: 
            st.success("🌟 **GOLDEN HOURS AKTIF (09.30 - 11.00 WIB):** Waktu paling optimal untuk mencari saham potensial dan eksekusi Day Trading. Volatilitas dan volume sedang berada di puncaknya.")
        else: 
            if not is_weekend:
                st.warning("⚠️ **NOTIFIKASI WIN RATE:** Screening & Eksekusi Day Trading disarankan dijalankan pada pukul 09.30-11.00 WIB. Saat ini bukan jam optimal, sinyal mungkin rentan terjebak *sideways*.")
            else:
                st.warning("🚫 **PASAR TUTUP:** Data Day Trading yang dihasilkan adalah hasil penutupan terakhir. Gunakan hanya untuk evaluasi.")
    elif trade_mode == "Swing Trading":
        is
