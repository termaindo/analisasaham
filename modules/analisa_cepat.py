import streamlit as st
import pandas as pd
import numpy as np
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_analisa_cepat():
    st.title("⚡ Analisa Cepat Pro (8 Poin Inti)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Quick Check):", value="BBCA").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button("🚀 Jalankan Analisa"):
        with st.spinner("Mengkalkulasi indikator teknikal & fundamental..."):
            # --- 1. STANDAR ANTI-ERROR ---
            data = get_full_stock_data(ticker)
            info = data['info']
            df = data['history']
            
            if df.empty or not info:
                st.error("Data gagal dimuat. Mohon tunggu 1 menit lalu 'Clear Cache' di pojok kanan atas.")
                return

            # --- 2. PERBAIKAN ERROR 'MA200' ---
            # Kita harus menghitung indikator ini SECARA MANUAL di sini
            df['MA20'] = df['Close'].rolling(20).mean()
            df['MA200'] = df['Close'].rolling(200).mean() # <--- INI PERBAIKANNYA
            
            # Cek ketersediaan data MA200
            if pd.isna(df['MA200'].iloc[-1]):
                ma200_val = 0
                status_ma200 = "Data Kurang (N/A)"
            else:
                ma200_val = df['MA200'].iloc[-1]
                status_ma200 = "Valid"

            curr = df['Close'].iloc[-1]
            ma20_val = df['MA20'].iloc[-1]
            
            # --- 3. LOGIKA SCORING YANG DIPERKUAT ---
            
            # A. Skor Fundamental (0-10)
            roe = info.get('returnOnEquity', 0)
            der = info.get('debtToEquity', 0)
            per = info.get('trailingPE', 0)
            
            f_score = 0
            if roe > 0.15: f_score += 4      # ROE Bagus (>15%)
            elif roe > 0.08: f_score += 2
            
            if der < 100: f_score += 3       # Utang Aman (DER < 1x)
            elif der < 200: f_score += 1
            
            if 0 < per < 25: f_score += 3    # Valuasi Wajar
            elif per > 0: f_score += 1

            # B. Skor Teknikal (0-10)
            t_score = 0
            if curr > ma20_val: t_score += 4 # Short Term Uptrend
            if curr > ma200_val and ma200_val > 0: t_score += 4 # Long Term Uptrend
            
            # Cek RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain/loss))).iloc[-1]
            
            if 50 < rsi < 70: t_score += 2   # Momentum Kuat tapi belum Overbought

            # --- 4. DATA PROCESSING LAINNYA ---
            # Kalkulasi ATR untuk SL (Lock 8%)
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            atr = ranges.max(axis=1).rolling(14).mean().iloc[-1]
            
            sl_raw = curr - (1.5 * atr)
            sl_final = max(sl_raw, curr * 0.92) # KUNCI MAX LOSS 8%
            metode_sl = "ATR (1.5x)" if sl_final == sl_raw else "Max Risk 8%"
            
            tp = int(curr + (curr - sl_final) * 2.5) # RRR 1:2.5
            
            # Tentukan Sentimen
            if curr > ma20_val and curr > ma200_val: sentiment = "BULLISH (Sangat Kuat) 🐂"
            elif curr > ma20_val: sentiment = "MILD BULLISH (Jangka Pendek) 🐃"
            elif curr < ma200_val: sentiment = "BEARISH (Hati-hati) 🐻"
            else: sentiment = "NEUTRAL / SIDEWAYS 😐"

            # Rekomendasi
            if f_score >= 7 and t_score >= 6: rekomen = "STRONG BUY"
            elif f_score >= 5 and t_score >= 5: rekomen = "BUY / ACCUMULATE"
            elif t_score < 4: rekomen = "SELL / AVOID"
            else: rekomen = "HOLD / WAIT"

            color_rec = "#00ff00" if "BUY" in rekomen else "#ffcc00" if "HOLD" in rekomen else "#ff0000"

            # --- 5. TAMPILAN OUTPUT (8 POIN INTI) ---
            html_output = f"""
            <div style="background-color:#1e2b3e; padding:25px; border-radius:12px; border-left:10px solid {color_rec}; color:#e0e0e0; font-family:sans-serif;">
                <h3 style="margin-top:0; color:white;">{info.get('longName', ticker)} ({ticker})</h3>
                <ul style="line-height:1.8; padding-left:20px; font-size:16px;">
                    <li><b>1. Fundamental Score ({f_score}/10):</b> Didukung oleh ROE {roe*100:.1f}% dan DER {der/100:.2f}x.</li>
                    <li><b>2. Technical Score ({t_score}/10):</b> Harga {'di atas' if curr > ma20_val else 'di bawah'} MA20 & {'di atas' if curr > ma200_val else 'di bawah'} MA200.</li>
                    <li><b>3. Sentiment Pasar:</b> <b>{sentiment}</b></li>
                    <li><b>4. Alasan Utama:</b> Tren {'Positif' if t_score > 5 else 'Negatif'}, Valuasi (PER {per:.1f}x), Div. Yield {hitung_div_yield_normal(info):.2f}%.</li>
                    <li><b>5. Risk Utama:</b> Volatilitas pasar & Potensi koreksi jika gagal bertahan di Support MA20.</li>
                    <li><b>6. Rekomendasi Final:</b> <span style="color:{color_rec}; font-weight:bold; font-size:18px;">{rekomen}</span></li>
                    <li><b>7. Target & Stop Loss:</b> <br>🎯 TP: Rp {tp:,.0f} | 🛑 SL: Rp {sl_final:,.0f} ({metode_sl})</li>
                    <li><b>8. Timeframe:</b> {'Investasi Jangka Panjang' if f_score >= 8 else 'Swing Trading Pendek'}.</li>
                </ul>
            </div>
            """
            st.markdown(html_output, unsafe_allow_html=True)
            
            # Debugging info (optional, bisa dihapus nanti)
            with st.expander("Lihat Detail Data Mentah"):
                st.write(f"MA200: {ma200_val:.2f}")
                st.write(f"MA20: {ma20_val:.2f}")
                st.write(f"ATR: {atr:.2f}")
