import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime

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
            with st.spinner(f"Sedang memproses data {ticker_input}..."):
                # 2. AMBIL DATA (1 Tahun ke belakang)
                stock = yf.Ticker(ticker)
                df = stock.history(period="1y")
                info = stock.info

                if df.empty:
                    st.error("Data saham tidak ditemukan. Pastikan kode benar.")
                    return

                # --- HITUNG INDIKATOR ---
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['MA50'] = df['Close'].rolling(window=50).mean()
                df['VolMA20'] = df['Volume'].rolling(window=20).mean()
                
                # RSI 14
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                df['RSI'] = 100 - (100 / (1 + (gain/loss)))
                
                curr_price = df['Close'].iloc[-1]
                curr_rsi = df['RSI'].iloc[-1]
                vol_now = df['Volume'].iloc[-1]
                vol_ma = df['VolMA20'].iloc[-1]

                # --- 3. BUAT GRAFIK MULTI-PLOT (Price & Volume) ---
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                   vertical_spacing=0.1, 
                                   row_heights=[0.7, 0.3])

                # A. Plot Harga (Row 1)
                fig.add_trace(go.Candlestick(
                    x=df.index, open=df['Open'], high=df['High'],
                    low=df['Low'], close=df['Close'], name='Price'
                ), row=1, col=1)
                
                fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='MA20', line=dict(color='orange', width=1.5)), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], name='MA50', line=dict(color='blue', width=1.5)), row=1, col=1)

                # B. Plot Volume (Row 2)
                # Warna Volume: Hijau jika harga naik, Merah jika harga turun
                colors = ['#26a69a' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#ef5350' for i in range(len(df))]
                
                fig.add_trace(go.Bar(
                    x=df.index, y=df['Volume'], name='Volume', marker_color=colors
                ), row=2, col=1)
                
                fig.add_trace(go.Scatter(
                    x=df.index, y=df['VolMA20'], name='Vol MA20', line=dict(color='purple', width=2)
                ), row=2, col=1)

                # Update Layout
                fig.update_layout(
                    title=f"Chart Interaktif {ticker_input}",
                    xaxis_rangeslider_visible=False,
                    height=600,
                    showlegend=True,
                    template="plotly_white"
                )
                st.plotly_chart(fig, use_container_width=True)

                # --- 4. ANALISA 8 POIN (AI ENGINE) ---
                st.markdown("---")
                st.subheader(f"🤖 Hasil Bedah Tuntas {ticker_input}")

                # Logika Penentuan Otomatis
                f_score = 8 if info.get('marketCap', 0) > 100e12 else 6
                t_score = 8 if curr_price > df['MA20'].iloc[-1] else 4
                sentiment = "Bullish" if curr_price > df['MA20'].iloc[-1] else "Bearish"
                
                supp = df['Low'].tail(30).min()
                res = df['High'].tail(30).max()
                
                # Format Bullet Points Padat
                st.markdown(f"""
                1. **Fundamental Score ({f_score}/10):** Kapitalisasi pasar Rp {info.get('marketCap', 0)/1e12:,.1f}T. Kondisi perusahaan {'sangat dominan' if f_score > 7 else 'menengah'}.
                2. **Technical Score ({t_score}/10):** Harga {'di atas' if t_score > 7 else 'di bawah'} MA20. RSI: {curr_rsi:.1f} ({'Oversold' if curr_rsi < 30 else 'Overbought' if curr_rsi > 70 else 'Netral'}).
                3. **Sentiment:** **{sentiment}** (Volume {'di atas' if vol_now > vol_ma else 'di bawah'} rata-rata 20 hari).
                4. **3 Alasan BUY:** {'Uptrend MA' if sentiment == 'Bullish' else 'Pantulan area Support'}, Volume {'kuat' if vol_now > vol_ma else 'stabil'}, RSI menunjukkan {'ruang kenaikan' if curr_rsi < 60 else 'momentum'}.
                5. **3 Risk:** Sinyal {'jenuh beli' if curr_rsi > 65 else 'lemahnya trend'}, Resiko koreksi global, Penembusan Support Rp {supp:,.0f}.
                6. **Rekomendasi Final:** **{'BUY/HOLD' if sentiment == 'Bullish' else 'WAIT & SEE'}**
                7. **Plan:** Entry: **Rp {curr_price:,.0f}** | Target: **Rp {res:,.0f}** | SL: **Rp {supp:,.0f}**.
                8. **Term:** {'Jangka Panjang (Investasi)' if f_score > 7 else 'Jangka Pendek (Swing)'}.
                """)

        except Exception as e:
            st.error(f"Gagal memuat data. Error: {e}")

    st.caption("Peringatan: Analisa berbasis algoritma data historis. Selalu lakukan riset mandiri.")
