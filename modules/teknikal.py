import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from modules.data_loader import ambil_data_saham  # Import Gudang Data Anti-Error

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
            with st.spinner(f"Sedang memproses data {ticker_input} dari server..."):
                # --- 2. AMBIL DATA LEWAT CACHE (Supaya tidak Error Too Many Requests) ---
                df, info = ambil_data_saham(ticker, period="1y")

                if df.empty:
                    st.error("Data saham tidak ditemukan atau koneksi terputus.")
                    return

                # --- HITUNG INDIKATOR ---
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['MA50'] = df['Close'].rolling(window=50).mean()
                df['VolMA20'] = df['Volume'].rolling(window=20).mean()
                
                # RSI 14 (Rumus Manual sesuai request)
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                df['RSI'] = 100 - (100 / (1 + (gain/loss)))
                
                curr_price = df['Close'].iloc[-1]
                curr_rsi = df['RSI'].iloc[-1]
                vol_now = df['Volume'].iloc[-1]
                vol_ma = df['VolMA20'].iloc[-1]

                # --- 3. BUAT GRAFIK MULTI-PLOT (Price & Volume) ---
                fig = make_subplots(
                    rows=2, cols=1, 
                    shared_xaxes=True, 
                    vertical_spacing=0.1, 
                    row_heights=[0.7, 0.3]
                )

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
                
                # Warna Vol MA20 menjadi Kuning (Yellow)
                fig.add_trace(go.Scatter(
                    x=df.index, y=df['VolMA20'], name='Vol MA20', line=dict(color='yellow', width=2)
                ), row=2, col=1)

                # Update Layout
                fig.update_layout(
                    title=f"Chart Interaktif {info.get('longName', ticker_input)}",
                    xaxis_rangeslider_visible=False,
                    height=600,
                    showlegend=True,
                    template="plotly_dark", # Tema Gelap
                    margin=dict(l=20, r=20, t=60, b=20)
                )
                st.plotly_chart(fig, use_container_width=True)

                # --- 4. ANALISA 8 POIN (Sesuai Prompt Pak Musa) ---
                st.markdown("---")
                st.subheader(f"🤖 Analisa Expert: {ticker_input}")

                # Logika Penilaian Sederhana
                # F-Score: Anggap bagus jika Big Cap (>100T)
                market_cap = info.get('marketCap', 0)
                f_score = 8 if market_cap > 100e12 else 6 if market_cap > 10e12 else 5
                
                # T-Score: Bagus jika di atas MA20
                ma20_last = df['MA20'].iloc[-1]
                t_score = 8 if curr_price > ma20_last else 4
                sentiment = "Bullish" if curr_price > ma20_last else "Bearish"
                
                # Support & Resistance (Low/High 30 Hari)
                supp = df['Low'].tail(30).min()
                res = df['High'].tail(30).max()
                
                # Menampilkan Teks Analisa
                st.markdown(f"""
                * **Fundamental score (1-10):** {f_score}/10 - Kapitalisasi pasar Rp {market_cap/1e12:,.1f}T.
                * **Technical score (1-10):** {t_score}/10 - Harga {'di atas' if t_score > 7 else 'di bawah'} MA20. RSI: {curr_rsi:.1f}.
                * **Sentiment pasar saat ini:** **{sentiment}**
                * **3 Alasan utama untuk BUY:** {'Uptrend MA' if sentiment == 'Bullish' else 'Pantulan Support'}, Volume {'kuat' if vol_now > vol_ma else 'stabil'}, RSI {'mendukung' if curr_rsi < 65 else 'momentum'}.
                * **3 Risk utama yang harus diwaspadai:** Sinyal {'jenuh beli' if curr_rsi > 68 else 'tren lemah'}, Koreksi pasar, Penembusan Support Rp {supp:,.0f}.
                * **Rekomendasi final:** **{'BUY/HOLD' if sentiment == 'Bullish' else 'WAIT & SEE'}**
                * **Entry buy, target price & stop loss:** Entry: **Rp {curr_price:,.0f}** | Target: **Rp {res:,.0f}** | SL: **Rp {supp:,.0f}**.
                * **Investasi jangka pendek atau panjang?** {'Jangka Panjang (Investasi)' if f_score > 7 else 'Jangka Pendek (Swing)'}.
                """)

        except Exception as e:
            st.error(f"Terjadi kesalahan saat analisa. Coba refresh halaman. Detail: {e}")

    st.caption("DISCLAIMER: Analisa data otomatis, keputusan investasi tetap di tangan Anda.")
