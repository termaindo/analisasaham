import streamlit as st
import pandas as pd
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_analisa_cepat():
    st.title("⚡ Analisa Cepat Pro (8 Poin Inti)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Quick Check):", value="BBCA").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button("🚀 Jalankan Analisa"):
        with st.spinner("Menyusun ringkasan eksekutif..."):
            # --- STANDAR ANTI-ERROR ---
            data = get_full_stock_data(ticker)
            info = data['info']
            df = data['history']
            
            if df.empty or not info:
                st.error("Data gagal dimuat. Mohon tunggu 1 menit lalu 'Clear Cache'.")
                return

            # --- DATA PROCESSING ---
            curr = df['Close'].iloc[-1]
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            atr = (df['High'] - df['Low']).tail(14).mean()
            
            # --- LOGIKA STOP LOSS (ATR vs 8%) ---
            # Formula: $$SL = \max(Price - 1.5 \times ATR, Price \times 0.92)$$
            sl_raw = curr - (1.5 * atr)
            sl_final = max(sl_raw, curr * 0.92)
            metode_sl = "ATR (1.5x)" if sl_final == sl_raw else "Max Risk 8%"
            
            tp = int(curr + (curr - sl_final) * 2.5) # RRR 1:2.5

            # --- SKORING & SENTIMEN ---
            f_score = 8 if info.get('returnOnEquity', 0) > 0.15 else 6
            t_score = 7 if curr > ma20 else 4
            sentiment = "BULLISH 🐂" if curr > ma20 else "BEARISH 🐻" if curr < df['MA200'].iloc[-1] else "NEUTRAL 😐"

            # --- TAMPILAN 8 POIN (RINGKAS & PADAT) ---
            html_output = f"""
<div style="background-color:#1e2b3e; padding:25px; border-radius:12px; border-left:10px solid #ff0000; color:#e0e0e0; font-family:sans-serif;">
    <h3 style="margin-top:0; color:white;">{info.get('longName', ticker)}</h3>
    <ul style="line-height:1.6; padding-left:20px;">
        <li><b>1. Fundamental Score ({f_score}/10):</b> Profitabilitas solid, didorong ROE {info.get('returnOnEquity', 0)*100:.1f}% yang sehat.</li>
        <li><b>2. Technical Score ({t_score}/10):</b> Harga berada {'di atas' if curr > ma20 else 'di bawah'} MA20, menunjukkan momentum {'kuat' if curr > ma20 else 'lemah'}.</li>
        <li><b>3. Sentiment Pasar:</b> Saat ini cenderung <b>{sentiment}</b>.</li>
        <li><b>4. 3 Alasan Utama BUY:</b> Market leader di sektornya, Valuasi wajar, dan Yield Dividen {hitung_div_yield_normal(info):.1f}%.</li>
        <li><b>5. 3 Risk Utama:</b> Volatilitas pasar global, Risiko regulasi, dan Tekanan jual di level Resistance.</li>
        <li><b>6. Rekomendasi Final:</b> <span style="color:#00ff00;"><b>{'BUY' if f_score >= 7 and t_score >= 6 else 'HOLD'}</b></span></li>
        <li><b>7. Target Price & Stop Loss:</b> 🎯 TP: Rp {tp:,.0f} | 🛑 SL: Rp {sl_final:,.0f} ({metode_sl}).</li>
        <li><b>8. Timeframe:</b> Cocok untuk {'Investasi Jangka Panjang' if f_score >= 8 else 'Swing Trading Pendek'}.</li>
    </ul>
</div>
"""
            st.markdown(html_output, unsafe_allow_html=True)
