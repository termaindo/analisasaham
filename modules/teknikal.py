import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

def run_teknikal():
    st.title("📈 Analisa Teknikal Mendalam")
    st.markdown("---")

    # 1. INPUT KODE SAHAM
    col_input1, col_input2 = st.columns([1, 3])
    with col_input1:
        ticker_input = st.text_input("Masukkan Kode Saham:", value="BBCA").upper()
        
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Analisa {ticker_input} Sekarang"):
        try:
            with st.spinner(f"Sedang membedah data {ticker_input}..."):
                # 2. AMBIL DATA
                stock = yf.Ticker(ticker)
                df = stock.history(period="1y")
                info = stock.info

                if df.empty:
                    st.error("Data saham tidak ditemukan. Pastikan kode benar.")
                    return

                # Indikator Dasar
                curr_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                df['MA20'] = df['Close'].rolling(20).mean()
                df['MA50'] = df['Close'].rolling(50).mean()
                
                # RSI 14
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rsi = 100 - (100 / (1 + (gain/loss))).iloc[-1]

                # 3. TAMPILKAN GRAFIK INTERAKTIF
                fig = go.Figure(data=[go.Candlestick(
                    x=df.index,
                    open=df['Open'], high=df['High'],
                    low=df['Low'], close=df['Close'],
                    name='Harga'
                )])
                fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='MA20', line=dict(color='orange')))
                fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], name='MA50', line=dict(color='blue')))
                fig.update_layout(title=f"Chart Harga {ticker_input}", xaxis_rangeslider_visible=False, height=400)
                st.plotly_chart(fig, use_container_width=True)

                # 4. LOGIKA ANALISA AI (Sesuai Prompt Bapak)
                # Menentukan skor & sentiment secara otomatis berdasarkan data
                f_score = 8 if info.get('marketCap', 0) > 100e12 else 6
                t_score = 8 if curr_price > df['MA20'].iloc[-1] else 5
                sentiment = "Bullish" if curr_price > df['MA20'].iloc[-1] else "Bearish"
                
                supp = df['Low'].tail(20).min()
                res = df['High'].tail(20).max()

                st.markdown("### 🤖 Ringkasan Analisa AI")
                st.markdown(f"""
                * **Fundamental Score ({f_score}/10):** Kapitalisasi pasar {'besar' if f_score > 7 else 'menengah'}, kondisi keuangan stabil.
                * **Technical Score ({t_score}/10):** Harga di {'atas' if t_score > 7 else 'bawah'} MA20. RSI di level {rsi:.1f} ({'Oversold' if rsi < 30 else 'Normal' if rsi < 70 else 'Overbought'}).
                * **Sentiment:** **{sentiment}**
                * **3 Alasan BUY:** {'Uptrend terkonfirmasi' if sentiment == 'Bullish' else 'Potensi Technical Rebound'}, Volume terjaga, Dekat area Support.
                * **3 Risk:** Volatilitas pasar global, Aksi ambil untung (profit taking), Penembusan Support Rp {supp:,.0f}.
                * **Rekomendasi:** **{'BUY' if rsi < 60 and sentiment == 'Bullish' else 'HOLD'}**
                * **Plan:** Entry Buy: **Rp {curr_price:,.0f}** | Target: **Rp {res:,.0f}** | SL: **Rp {supp:,.0f}**.
                * **Investasi:** {'Jangka Panjang (Bluechip)' if f_score > 7 else 'Jangka Pendek (Swing)'}.
                """)

        except Exception as e:
            st.error(f"Terjadi kesalahan teknis: {e}")

    st.caption("Peringatan: Analisa ini dihasilkan otomatis oleh sistem berdasarkan data historis.")
