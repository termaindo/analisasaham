import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from modules.data_loader import ambil_data_history, ambil_data_fundamental_lengkap

def run_teknikal():
    st.title("📈 Analisa Teknikal Mendalam")
    st.markdown("---")

    col_input1, col_input2 = st.columns([1, 3])
    with col_input1:
        ticker_input = st.text_input("Kode Saham:", value="BBCA").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Analisa {ticker_input} Sekarang"):
        try:
            with st.spinner(f"Sedang memproses chart {ticker_input}..."):
                # 1. AMBIL DATA HARGA SAJA (Lebih stabil)
                df = ambil_data_history(ticker, period="1y")

                if df.empty:
                    st.error(f"❌ Data harga {ticker_input} tidak ditemukan di Yahoo Finance. Cek ejaan kode saham.")
                    return

                # Ambil info terpisah (kalau gagal, chart tetap jalan)
                info, _, _ = ambil_data_fundamental_lengkap(ticker)
                long_name = info.get('longName', ticker_input)

                # --- HITUNG INDIKATOR ---
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['MA50'] = df['Close'].rolling(window=50).mean()
                df['VolMA20'] = df['Volume'].rolling(window=20).mean()
                
                # RSI 14
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                df['RSI'] = 100 - (100 / (1 + (gain/loss)))

                # Data Terakhir
                curr_price = df['Close'].iloc[-1]
                curr_rsi = df['RSI'].iloc[-1]
                
                # --- PLOT CHART ---
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                    vertical_spacing=0.1, row_heights=[0.7, 0.3])

                # Candlestick
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                             low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name='MA20', line=dict(color='orange')), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], name='MA50', line=dict(color='blue')), row=1, col=1)

                # Volume
                colors = ['green' if c >= o else 'red' for c, o in zip(df['Close'], df['Open'])]
                fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color=colors), row=2, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['VolMA20'], name='Vol MA20', line=dict(color='yellow')), row=2, col=1)

                fig.update_layout(title=f"Chart {long_name}", height=600, xaxis_rangeslider_visible=False, template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)

                # --- ANALISA TEKS SINGKAT ---
                st.info(f"💡 **Posisi Harga:** Rp {curr_price:,.0f} | **RSI:** {curr_rsi:.1f} | **Trend:** {'Bullish (Diatas MA20)' if curr_price > df['MA20'].iloc[-1] else 'Bearish'}")

        except Exception as e:
            st.error(f"Terjadi kesalahan teknis: {e}")
