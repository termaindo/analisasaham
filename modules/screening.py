import streamlit as st
import pandas as pd
import numpy as np
import pytz
import os
import base64
import holidays
import io
import plotly.express as px
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
    
    pdf.set_y(28)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 8, f"Strategi: {trade_mode} | Sesi: {session}", ln=True, align='C')
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 5, f"Dicetak: {datetime.now().strftime('%d-%m-%Y %H:%M')}", ln=True, align='R')
    pdf.ln(2)

    # --- SEKSI A: TOP 3 PRIORITAS ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "A. TOP 3 PRIORITAS TRANSAKSI (HIGH CONVICTION)", 0, ln=True, fill=True)
    pdf.ln(2)

    top_3 = hasil_lolos[:3]
    for item in top_3:
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 6, f"{item['Ticker']} - {item['Sektor']} | Score: {item['Skor']}", ln=True)
        
        pdf.set_font("Arial", '', 9)
        pdf.cell(60, 5, f"Entry: {item['Entry']}", 0)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(60, 5, f"TP Target: Rp {item['TP']}", 0)
        pdf.set_text_color(200, 0, 0)
        pdf.cell(60, 5, f"Stop Loss: Rp {item['SL']}", ln=True)
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
        
        # Header Tabel
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(20, 6, "Ticker", 1, 0, 'C')
        pdf.cell(50, 6, "Sektor", 1, 0, 'C')
        pdf.cell(15, 6, "Skor", 1, 0, 'C')
        pdf.cell(35, 6, "Entry", 1, 0, 'C')
        pdf.cell(25, 6, "SL", 1, 0, 'C')
        pdf.cell(25, 6, "TP", 1, 0, 'C')
        pdf.cell(20, 6, "RRR", 1, 1, 'C')
        
        # Isi Tabel
        pdf.set_font("Arial", '', 8)
        for w in watchlist:
            pdf.cell(20, 6, w['Ticker'], 1, 0, 'C')
            pdf.cell(50, 6, w['Sektor'][:22], 1, 0, 'C')
            pdf.cell(15, 6, str(w['Skor']), 1, 0, 'C')
            pdf.cell(35, 6, w['Entry'], 1, 0, 'C')
            pdf.cell(25, 6, str(w['SL']), 1, 0, 'C')
            pdf.cell(25, 6, str(w['TP']), 1, 0, 'C')
            pdf.cell(20, 6, w['RRR'], 1, 1, 'C')

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

# --- 6. MODUL UTAMA ---
def run_screening():
    st.set_page_config(page_title="🔍 Screening Saham Harian Pro", layout="wide")
    st.markdown("<h1 style='text-align: center;'>🔍 Screening Saham Harian Pro</h1>", unsafe_allow_html=True)
    st.markdown("---")

    # --- PILIHAN MODE DI LAYAR UTAMA ---
    st.write("### ⚙️ Pemilihan Strategi & Waktu Analisa")
    trade_mode = st.radio("Pilih Strategi Trading (Mode Analisa):", ["Day Trading", "Swing Trading"], horizontal=True)

    # Sidebar Options
    with st.sidebar:
        st.header("⚙️ Filter Institusi Tambahan")
        mtf_filter = st.checkbox("Strict MTF Alignment", value=True, help="Hanya tampilkan saham yang searah dengan tren besar (Daily & Weekly).")
        sector_boost = st.checkbox("Enable Sector Booster", value=True, help="Berikan poin tambahan pada saham di sektor yang memimpin pasar.")

    # Time Logic & Market Session
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    curr_time_float = now.hour + now.minute/60
    is_weekend = now.weekday() >= 5
    session, status_desc = get_market_session()

    if "Tutup" in status_desc:
        st.error(f"**Status Market:** {session} ({status_desc})")
    else:
        st.info(f"**Status Market:** {session} ({status_desc})")

    # --- DYNAMIC NOTIFICATIONS ---
    if trade_mode == "Day Trading":
        is_golden = 9.5 <= curr_time_float <= 11.0 and not is_weekend
        if is_golden: 
            st.success("🌟 **GOLDEN HOURS AKTIF (09.30 - 11.00 WIB):** Waktu paling optimal untuk mencari saham potensial dan eksekusi Day Trading. Volatilitas dan volume sedang berada di puncaknya.")
        else: 
            if not is_weekend:
                st.warning("⚠️ **NOTIFIKASI WIN RATE:** Day Trading disarankan dijalankan pada pukul 09.30-11.00 WIB. Saat ini bukan jam optimal, sinyal mungkin rentan terjebak *sideways*.")
            else:
                st.warning("🚫 **PASAR TUTUP:** Data Day Trading yang dihasilkan adalah hasil penutupan terakhir. Gunakan hanya untuk evaluasi.")
    
    elif trade_mode == "Swing Trading":
        is_swing = curr_time_float >= 16.0 or is_weekend
        if is_swing: 
            st.success("✅ **WAKTU ANALISA SWING IDEAL:** Data penutupan telah final. Ini adalah waktu terbaik untuk menyusun *Watchlist* dan *Trading Plan* untuk esok hari.")
        else: 
            st.info("ℹ️ **INFO:** Screening Swing Trading paling akurat dilakukan setelah jam 16.00 WIB untuk memastikan struktur harga penutupan harian tidak berubah.")

    st.markdown("---")

    # --- TOMBOL EKSEKUSI ---
    if st.button(f"🚀 JALANKAN ANALISA {trade_mode.upper()}"):
        saham_list = [f"{t}.JK" for tickers in UNIVERSE_SAHAM.values() for t in tickers]
        saham_list = list(set(saham_list))
        
        raw_results = []
        progress_bar = st.progress(0)

        for i, ticker in enumerate(saham_list):
            progress_bar.progress((i + 1) / len(saham_list))
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

                if mtf_filter and not (is_macro_bullish and is_medium_bullish): continue

                score = 0; alasan = []
                if is_macro_bullish: score += 20; alasan.append("Macro UP (MA200)")
                if is_medium_bullish: score += 15; alasan.append("Medium UP (MA50)")
                if is_micro_bullish: score += 15; alasan.append("Micro Momentum")
                
                if last['Volume'] > df['Vol_SMA20'].iloc[-1]: score += 20; alasan.append("Volume Spike")
                if avg_val_20 > (1e10 if trade_mode == "Day Trading" else 5e9): score += 10; alasan.append("Inst. Liquidity")

                raw_results.append({
                    "Ticker": ticker_bersih, "Sektor": sektor_nama, "Skor": score, 
                    "Harga": int(curr_price), "ATR": last['ATR'], "Alasan": alasan, "RSI": last['RSI']
                })
            except: continue

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

            if f_score >= 65 and rrr >= 1.4:
                final_picks.append({
                    "Ticker": stock['Ticker'], "Sektor": stock['Sektor'], "Skor": f_score,
                    "Entry": f"Rp {int(stock['Harga']*0.99)} - {stock['Harga']}",
                    "SL": sl, "TP": tp, "RRR": f"{rrr:.1f}x",
                    "Status": "🔥 HIGH CONVICTION" if f_score >= 85 else "🎯 READY",
                    "Logic": " | ".join(stock['Alasan'])
                })

        final_picks.sort(key=lambda x: x['Skor'], reverse=True)
        # Batasi hanya 10 saham teratas untuk mencegah analysis paralysis
        st.session_state.final_picks = final_picks[:10] 
        st.session_state.sector_report = sector_report
        st.session_state.pdf_session = session # Simpan sesi untuk PDF
        progress_bar.empty()
        if any(p['Skor'] >= 85 for p in st.session_state.final_picks): play_alert_sound()

    # --- DISPLAY UI (TOP 10 LOGIC) ---
    if 'final_picks' in st.session_state and st.session_state.final_picks:
        res = st.session_state.final_picks
        top_3 = res[:3]
        watchlist = res[3:10]

        st.subheader("🌐 Market Overview")
        c1, c2 = st.columns([2, 1])
        with c1:
            fig = px.bar(st.session_state.sector_report.reset_index(), x='Sektor', y='Avg_Score', color='Avg_Score', color_continuous_scale='Greens', title="Kekuatan Sektor Saat Ini")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.write("**Top Leading Sectors:**")
            for s in st.session_state.sector_report.index[:3]: st.success(s)

        st.markdown("---")
        
        # --- UI: TOP 3 CARDS ---
        st.header(f"🏆 Top 3 Prioritas {trade_mode}")
        if top_3:
            cols = st.columns(len(top_3))
            for idx, item in enumerate(top_3):
                with cols[idx]:
                    st.markdown(f"### {item['Ticker']}")
                    st.write(f"**Sektor:** {item['Sektor']}")
                    st.metric("Skor Institusi", f"{item['Skor']} Pts", item['Status'])
                    st.write(f"**Target (TP):** Rp {item['TP']}")
                    st.write(f"**Proteksi (SL):** Rp {item['SL']}")
                    st.info(f"Area Entry: {item['Entry']}")
                    st.caption(f"💡 {item['Logic']}")
        else:
            st.warning("Belum ada saham yang memenuhi kriteria ketat institusi saat ini.")

        # --- UI: WATCHLIST 4-10 TABLE ---
        if watchlist:
            st.markdown("---")
            st.subheader(f"📋 Radar Watchlist (Rank 4-10)")
            df_watch = pd.DataFrame(watchlist)
            # Reorder columns untuk tampilan web yang lebih bersih
            kolom_tampil = ["Ticker", "Sektor", "Skor", "Status", "Entry", "SL", "TP", "RRR"]
            st.dataframe(df_watch[kolom_tampil], use_container_width=True, hide_index=True)
        
        # --- PDF DOWNLOAD BUTTON ---
        st.markdown("<br>", unsafe_allow_html=True)
        pdf_data = export_to_pdf(res, trade_mode, st.session_state.pdf_session, st.session_state.sector_report)
        st.download_button("📥 UNDUH LAPORAN SCREENING LENGKAP (PDF)", data=pdf_data, file_name=f"Alpha_Report_{trade_mode}.pdf", mime="application/pdf", use_container_width=True)

if __name__ == "__main__":
    run_screening()
