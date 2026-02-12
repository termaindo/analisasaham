import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from modules.data_loader import ambil_data_saham  # Import Gudang Data

def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_teknikal():
    st.title("📈 Analisa Teknikal Mendalam")
    st.markdown("---")

    col_input, _ = st.columns([1, 2])
    with col_input:
        ticker_input = st.text_input("Masukkan Kode Saham:", value="BBTN").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Analisa {ticker_input} Sekarang"):
        try:
            with st.spinner(f"Mengambil data {ticker_input} dari server..."):
                # --- PENGGUNAAN CACHE DI SINI ---
                df, info = ambil_data_saham(ticker, period="1y")

                if df.empty:
                    st.error("Data saham tidak ditemukan atau koneksi terputus.")
                    return

                # Indikator
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['MA50'] = df['Close'].rolling(window=50).mean()
                df['RSI'] = calculate_rsi(df)

                curr_price = df['Close'].iloc[-1]
                
                # Header Harga
                st.subheader(f"{info.get('longName', ticker_input)}")
                st.metric("Harga Terakhir", f"Rp {curr_price:,.0f}", 
                          f"{((curr_price - df['Close'].iloc[-2])/df['Close'].iloc[-2])*100:.2f}%")

                # Chart Candlestick
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                             low=df['Low'], close=df['Close'], name='Price'))
                fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1), name='MA 20'))
                fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], line=dict(color='blue', width=1), name='MA 50'))
                
                fig.update_layout(title=f"Chart {ticker_input}", xaxis_rangeslider_visible=False, height=500)
                st.plotly_chart(fig, use_container_width=True)

                # Analisa Singkat
                rsi_now = df['RSI'].iloc[-1]
                st.info(f"**RSI Indicator:** {rsi_now:.2f} ({'Jenuh Beli' if rsi_now > 70 else 'Jenuh Jual' if rsi_now < 30 else 'Netral'})")

        except Exception as e:
            st.error(f"Terjadi kesalahan: {e}. Coba tunggu 1 menit lalu tekan tombol lagi.")
