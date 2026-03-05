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
def export_to_pdf(hasil_lolos, trade_mode, session, sector_report, modal_risiko, logo_path="logo_expert_stock_pro.png"):
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
    
    # Info Strategi, Waktu, dan Modal Risiko
    pdf.ln(3)
    pdf.set_text_color(0, 0, 0) 
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 8, f"Strategi: {trade_mode} | Sesi: {session}", ln=True, align='C')
    
    pdf.set_font("Arial", 'B', 9)
    pdf.set_text_color(150, 0, 0) # Warna merah gelap untuk peringatan risiko
    pdf.cell(190, 5, f"Batas Toleransi Risiko per Transaksi (Stop Loss): Rp {modal_risiko:,.0f}".replace(',', '.'), ln=True, align='C')
    
    tz = pytz.timezone('Asia/Jakarta')
    waktu_cetak = datetime.now(tz).strftime('%d-%m-%Y %H:%M WIB')
    pdf.set_text_color(0, 0, 0)
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
        
        # Baris Info Harga
        pdf.set_font("Arial", '', 9)
        pdf.cell(50, 5, f"Entry: {item['Entry']}", 0)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(45, 5, f"Target: Rp {item['TP']}", 0)
        pdf.set_text_color(200, 0, 0)
        pdf.cell(45, 5, f"Stop Loss: Rp {item['SL']}", 0)
        
        # Baris Lot Rekomendasi
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(50, 5, f"Max Beli: {item['Lot_Maks']}", ln=True)
        
        # Baris Logic
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
        
        # Penyesuaian Lebar Kolom untuk Menyisipkan "Lot Maks"
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(15, 6, "Ticker", 1, 0, 'C')
        pdf.cell(45, 6, "Sektor", 1, 0, 'C')
        pdf.cell(10, 6, "Skor", 1, 0, 'C')
        pdf.cell(32, 6, "Entry", 1, 0, 'C')
        pdf.cell(22, 6, "SL", 1, 0, 'C')
        pdf.cell(22, 6, "TP", 1, 0, 'C')
        pdf.cell(20, 6, "RRR", 1, 0, 'C')
        pdf.cell(24, 6, "Max Lot", 1, 1, 'C') # Kolom Baru
        
        pdf.set_font("Arial", '', 8)
        for w in watchlist:
            pdf.cell(15, 6, w['Ticker'], 1, 0, 'C')
            pdf.cell(45, 6, w['Sektor'][:20], 1, 0, 'C') # Potong text sektor sedikit
            pdf.cell(10, 6, str(w['Skor']), 1, 0, 'C')
            pdf.cell(32, 6, w['Entry'].replace("Rp ", ""), 1, 0, 'C') # Hapus "Rp " agar muat
            pdf.cell(22, 6, str(w['SL']), 1, 0, 'C')
            pdf.cell(22, 6, str(w['TP']), 1, 0, 'C')
            pdf.cell(20, 6, w['RRR'], 1, 0, 'C')
            pdf.set_font("Arial", 'B', 8)
            pdf.cell(24, 6, w['Lot_Maks'], 1, 1, 'C') # Isi Kolom Baru
            pdf.set_font("Arial", '', 8)

    # --- DISCLAIMER FOOTER PDF ---
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, "DISCLAIMER:", ln=True) 
    pdf.set_font("Arial", 'I', 7)
    disclaimer_text = ("Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma indikator teknikal dan fundamental. Seluruh informasi yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi tanggung jawab pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik dan Do Your Own Research (DYOR) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.")
    pdf.multi_cell(190, 4, disclaimer_text)

    return pdf.output(dest='S').encode('latin-1', 'ignore')

# --- 4. INDIKATOR TEKNIKAL ---
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

# --- FUNGSI WORKER UNTUK MULTITHREADING ---
def process_single_ticker(ticker, trade_mode, mtf_filter):
    ticker_bersih = ticker.replace(".JK", "")
    try:
        data = get_full_stock_data(ticker)
        df = calculate_indicators(data['history'], trade_mode)
        last = df.iloc[-1]; prev = df.iloc[-2]
        curr_price = last['Close']
        avg_val_20 = (df['Close'] * df['Volume']).rolling(20).mean().iloc[-1]
        sektor_nama, _ = get_sector_data(ticker_bersih)

        is_macro_bullish = curr_price > last['MA200']
        is_medium_bullish = curr_price > last['MA50']
        is_micro_bullish = curr_price > last['VWAP'] if trade_mode == "Day Trading" else curr_price > last['EMA9']

        if mtf_filter and not (is_macro_bullish and is_medium_bullish): 
            return None

        score = 0; alasan = []
        
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

    with st.sidebar:
        st.header("⚙️ Filter Institusi Tambahan")
        mtf_filter = st.checkbox("Strict MTF Alignment", value=True, help="Hanya tampilkan saham yang searah dengan tren besar (Daily & Weekly).")
        sector_boost = st.checkbox("Enable Sector Booster", value=True, help="Berikan poin tambahan pada saham di sektor yang memimpin pasar.")

    st.write("### ⚙️ Pemilihan Strategi & Pengaturan Risiko")
    st.info("⏰ **Panduan Waktu Analisa Optimal:** \n"
            "- **Day Trading:** 09.30 - 11.00 WIB (Untuk momentum harian tertinggi).\n"
            "- **Swing Trading:** > 16.00 WIB (Untuk konfirmasi harga penutupan yang solid).")
    
    st.markdown("**1. Pilih Mode Analisa:**")
    trade_mode = st.radio("Mode:", ["Day Trading", "Swing Trading"], horizontal=True, label_visibility="collapsed")
    
    st.markdown("**2. Position Sizing Calculator (Kalkulator Risiko):**")
    modal_risiko = st.number_input(
        "Maksimal Rupiah yang Rela Dirisikokan per Transaksi:", 
        min_value=10000, 
        value=1000000, 
        step=50000,
        help="Contoh: Jika Anda mengisi 1.000.000, sistem akan menghitung batas aman jumlah lot agar kerugian maksimal Anda berhenti tepat di 1 Juta Rupiah jika harga menyentuh Stop Loss."
    )

    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    curr_time_float = now.hour + now.minute/60
    is_weekend = now.weekday() >= 5
    session, status_desc = get_market_session()

    st.markdown("---")

    if "Tutup" in status_desc:
        st.error(f"**Status Market:** {session} ({status_desc})")
    else:
        st.info(f"**Status Market:** {session} ({status_desc})")

    if trade_mode == "Day Trading":
        is_golden = 9.5 <= curr_time_float <= 11.0 and not is_weekend
        if is_golden: 
            st.success("🌟 **GOLDEN HOURS AKTIF (09.30 - 11.00 WIB):** Waktu paling optimal.")
        else: 
            if not is_weekend: st.warning("⚠️ **NOTIFIKASI WIN RATE:** Disarankan dijalankan pukul 09.30-11.00 WIB.")
            else: st.warning("🚫 **PASAR TUTUP:** Data Day Trading ini menggunakan hasil penutupan terakhir.")
    elif trade_mode == "Swing Trading":
        is_swing = curr_time_float >= 16.0 or is_weekend
        if is_swing: st.success("✅ **WAKTU ANALISA SWING IDEAL:** Data penutupan telah final.")
        else: st.info("ℹ️ **INFO:** Screening Swing Trading paling akurat dilakukan setelah jam 16.00 WIB.")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button(f"🚀 JALANKAN ANALISA {trade_mode.upper()} (TURBO MODE)", use_container_width=True):
        saham_list = [f"{t}.JK" for tickers in UNIVERSE_SAHAM.values() for t in tickers]
        saham_list = list(set(saham_list))
        
        raw_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(process_single_ticker, t, trade_mode, mtf_filter): t for t in saham_list}
            
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                progress_bar.progress((i + 1) / len(saham_list))
                status_text.text(f"Memindai pasar... ({i+1}/{len(saham_list)} saham)")
                try:
                    res = future.result()
                    if res is not None:
                        raw_results.append(res)
                except Exception:
                    continue

        progress_bar.empty()
        status_text.empty()

        df_all = pd.DataFrame(raw_results)
        sector_report, leading_sectors = analyze_sector_momentum(df_all)
        
        final_picks = []
        for stock in raw_results:
            f_score = stock['Skor']
            
            if sector_boost and stock['Sektor'] in leading_sectors:
                f_score += 15; stock['Alasan'].append(f"Sector Hot: {stock['Sektor']}")
            
            sl_mult = 1.8 if trade_mode == "Day Trading" else 2.5
            sl = int(stock['Harga'] - (sl_mult * stock['ATR']))
            tp = int(stock['Harga'] + (stock['Harga'] - sl) * (1.5 if trade_mode == "Day Trading" else 2.0))
            rrr = (tp - stock['Harga']) / (stock['Harga'] - sl) if stock['Harga'] > sl else 0

            risiko_per_lembar = stock['Harga'] - sl
            if risiko_per_lembar > 0:
                lembar_maksimal = modal_risiko / risiko_per_lembar
                lot_maksimal = int(lembar_maksimal / 100) 
            else:
                lot_maksimal = 0

            if f_score >= 65 and r
