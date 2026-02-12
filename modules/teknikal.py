import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from modules.data_loader import get_full_stock_data

def calculate_metrics(df):
    # Indikator Dasar
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA50'] = df['Close'].rolling(50).mean()
    df['MA200'] = df['Close'].rolling(200).mean()
    
    # RSI & MACD
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # --- KALKULASI ATR (Average True Range) ---
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    return df

def run_teknikal():
    st.title("📈 Analisa Teknikal (ATR Dynamic Plan)")
    st.markdown("---")

    ticker_input = st.text_input("Kode Saham:", value="BBRI").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Analisa Sinyal {ticker_input}"):
        with st.spinner("Mengkalkulasi volatilitas ATR..."):
            data = get_full_stock_data(ticker)
            df = data["history"]
            
            if df.empty:
                st.error("Data tidak ditemukan.")
                return

            df = calculate_metrics(df)
            last = df.iloc[-1]
            curr_price = last['Close']
            atr = last['ATR']

            # --- TRADING PLAN BERBASIS ATR ---
            # Stop Loss (SL) = Harga - 2x ATR (Standar Konservatif)
            sl = int(curr_price - (2 * atr))
            
            # Take Profit (TP) Berjenjang
            tp1 = int(curr_price + (2 * atr)) # RR 1:1
            tp2 = int(curr_price + (4 * atr)) # RR 1:2
            tp3 = int(curr_price + (6 * atr)) # RR 1:3
            
            # --- VISUALISASI ---
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA200'], line=dict(color='purple', width=2), name='MA200'), row=1, col=1)
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- OUTPUT TRADING PLAN ---
            st.subheader("🎯 Trading Plan (Volatility Based)")
            st.write(f"**Nilai ATR Saat Ini:** Rp {atr:.2f}")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.error(f"🛑 **STOP LOSS**\n\n**Rp {sl:,.0f}**\n(2x ATR)")
            with c2:
                st.success(f"💰 **TAKE PROFIT**\n\nTP1: {tp1:,.0f}\nTP2: {tp2:,.0f}\nTP3: {tp3:,.0f}")
            with c3:
                st.info(f"📊 **RISK/REWARD**\n\nTarget RR: 1:2\nStatus: {'Uptrend' if curr_price > last['MA200'] else 'Downtrend'}")
