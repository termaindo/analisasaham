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
    pdf.cell(190, 8, f"Strategi: {trade_mode} | Multi-Timeframe Confirmed", ln=True, align='C')
    pdf.ln(5)
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# --- 4. INDIKATOR TEKNIKAL (MTF ENGINE) ---
def calculate_indicators(df, trade_mode):
    # Core Indicators
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    # ATR for Risk
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    
    # Micro Momentum
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

    # Sidebar Options
    with st.sidebar:
        st.header("⚙️ Strategy Settings")
        trade_mode = st.radio("Trading Mode:", ["Day Trading", "Swing Trading"])
        mtf_filter = st.checkbox("Strict MTF Alignment", value=True, help="Hanya tampilkan saham yang searah dengan tren besar (Daily & Weekly).")
        sector_boost = st.checkbox("Enable Sector Booster", value=True)

    # Time Logic
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    curr_time_float = now.hour + now.minute/60
    session, _ = get_market_session()

    # Dynamic Notifications
    if trade_mode == "Day Trading":
        if 9.5 <= curr_time_float <= 11.0: st.success("🌟 **GOLDEN HOURS AKTIF**")
        else: st.warning("⚠️ **WIN RATE REDUCED:** Jalankan pukul 09.30-11.00.")
    else:
        if curr_time_float >= 16.0: st.success("✅ **IDEAL SWING ANALYSIS**")

    if st.button(f"🚀 JALANKAN ANALISA MULTI-TIMEFRAME"):
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

                # --- MTF ALIGNMENT LOGIC ---
                is_macro_bullish = curr_price > last['MA200']
                is_medium_bullish = curr_price > last['MA50']
                is_micro_bullish = curr_price > last['VWAP'] if trade_mode == "Day Trading" else curr_price > last['EMA9']

                if mtf_filter and not (is_macro_bullish and is_medium_bullish):
                    continue # Buang saham yang melawan tren besar

                score = 0; alasan = []
                # Scoring Base
                if is_macro_bullish: score += 20; alasan.append("Macro UP (MA200)")
                if is_medium_bullish: score += 15; alasan.append("Medium UP (MA50)")
                if is_micro_bullish: score += 15; alasan.append("Micro Momentum")
                
                # Volume & Liquidity
                if last['Volume'] > df['Vol_SMA20'].iloc[-1]: score += 20; alasan.append("Volume Spike")
                if avg_val_20 > (1e10 if trade_mode == "Day Trading" else 5e9): score += 10; alasan.append("Institutional Liquidity")

                raw_results.append({
                    "Ticker": ticker_bersih, "Sektor": sektor_nama, "Skor": score, 
                    "Harga": int(curr_price), "ATR": last['ATR'], "Alasan": alasan, "RSI": last['RSI']
                })
            except: continue

        # --- SECTOR MOMENTUM ---
        df_all = pd.DataFrame(raw_results)
        sector_report, leading_sectors = analyze_sector_momentum(df_all)
        
        final_picks = []
        for stock in raw_results:
            f_score = stock['Skor']
            if sector_boost and stock['Sektor'] in leading_sectors:
                f_score += 15; stock['Alasan'].append(f"Sector Hot: {stock['Sektor']}")
            
            # Risk Management
            sl_mult = 1.8 if trade_mode == "Day Trading" else 2.5
            sl = int(stock['Harga'] - (sl_mult * stock['ATR']))
            tp = int(stock['Harga'] + (stock['Harga'] - sl) * (1.5 if trade_mode == "Day Trading" else 2.0))
            rrr = (tp - stock['Harga']) / (stock['Harga'] - sl) if stock['Harga'] > sl else 0

            if f_score >= 65 and rrr >= 1.4:
                final_picks.append({
                    "Ticker": stock['Ticker'], "Sektor": stock['Sektor'], "Skor": f_score,
                    "Entry": f"{int(stock['Harga']*0.99)}-{stock['Harga']}",
                    "SL": sl, "TP": tp, "RRR": f"{rrr:.1f}x",
                    "Status": "🔥 HIGH CONVICTION" if f_score >= 85 else "🎯 READY",
                    "Logic": " | ".join(stock['Alasan'])
                })

        final_picks.sort(key=lambda x: x['Skor'], reverse=True)
        st.session_state.final_picks = final_picks
        st.session_state.sector_report = sector_report
        progress_bar.empty()
        if any(p['Skor'] >= 85 for p in final_picks): play_alert_sound()

    # --- DISPLAY UI ---
    if 'final_picks' in st.session_state:
        st.subheader("🌐 Market Overview")
        c1, c2 = st.columns([2, 1])
        with c1:
            fig = px.bar(st.session_state.sector_report.reset_index(), x='Sektor', y='Avg_Score', color='Avg_Score', color_continuous_scale='Greens')
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.write("**Top Leading Sectors:**")
            for s in st.session_state.sector_report.index[:3]: st.success(s)

        st.subheader(f"🏆 Top Picks: {trade_mode}")
        st.dataframe(pd.DataFrame(st.session_state.final_picks), use_container_width=True)

if __name__ == "__main__":
    run_screening()
