import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from modules.data_loader import get_full_stock_data

def calculate_metrics(df):
    # 1. Moving Averages
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA50'] = df['Close'].rolling(50).mean()
    df['MA200'] = df['Close'].rolling(200).mean()
    
    # 2. Bollinger Bands
    df['BB_Mid'] = df['MA20']
    df['BB_Std'] = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + (2 * df['BB_Std'])
    df['BB_Lower'] = df['BB_Mid'] - (2 * df['BB_Std'])
    
    # 3. RSI & MACD
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal']

    # 4. ATR untuk SL/TP Dinamis
    high_low = df['High'] - df['Low']
    df['ATR'] = high_low.rolling(14).mean()
    
    # 5. Support & Resistance (20 Hari)
    df['Sup'] = df['Low'].rolling(20).min()
    df['Res'] = df['High'].rolling(20).max()
    return df

def run_teknikal():
    st.title("📈 Analisa Teknikal Pro")
    st.markdown("---")

    ticker_input = st.text_input("Kode Saham:", value="BBCA").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Jalankan Analisa Lengkap {ticker_input}"):
        with st.spinner("Mengkalkulasi 5 Aspek Analisa..."):
            data = get_full_stock_data(ticker)
            df = data["history"]
            
            if df.empty or len(df) < 200:
                st.error("Data tidak mencukupi untuk analisa MA200.")
                return

            df = calculate_metrics(df)
            last = df.iloc[-1]
            curr_price = last['Close']
            atr = last['ATR']

            # --- VISUALISASI CHART ---
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, 
                               row_heights=[0.6, 0.2, 0.2],
                               subplot_titles=("Price & BB", "MACD", "RSI"))
            
            # Candlestick & MAs (MA20 KUNING)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="MA20 (Kuning)"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], line=dict(color='blue', width=1), name="MA50"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA200'], line=dict(color='purple', width=2), name="MA200"), row=1, col=1)
            
            # Bollinger Bands
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], line=dict(color='gray', dash='dash'), name="BB Upper"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], line=dict(color='gray', dash='dash'), name="BB Lower"), row=1, col=1)
            
            # MACD & RSI
            fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD Hist"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='yellow'), name="RSI"), row=3, col=1)

            fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- ANALISA 5 POIN (FIXED & LENGKAP) ---
            st.markdown("---")
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("1. TREND ANALYSIS")
                st.write(f"• **Trend Utama:** {'UPTREND' if curr_price > last['MA200'] else 'DOWNTREND'}")
                st.write(f"• **Support:** Rp {last['Sup']:,.0f} | **Resistance:** Rp {last['Res']:,.0f}")
                
                st.subheader("2. INDIKATOR TEKNIKAL")
                st.write(f"• **MA20:** {'Diatas' if curr_price > last['MA20'] else 'Dibawah'} Harga")
                st.write(f"• **RSI:** {last['RSI']:.1f} ({'Oversold' if last['RSI']<30 else 'Overbought' if last['RSI']>70 else 'Neutral'})")
                st.write(f"• **MACD:** {'Bullish' if last['MACD'] > last['Signal'] else 'Bearish'}")

            with c2:
                st.subheader("3. PATTERN RECOGNITION")
                pattern = "Doji Terdeteksi" if abs(last['Close']-last['Open']) < (last['High']-last['Low'])*0.1 else "Tidak ada pola candle kuat"
                st.write(f"• **Candle:** {pattern}")
                st.write(f"• **Divergence:** {'Ada indikasi' if (last['Close'] < df['Close'].iloc[-5] and last['RSI'] > df['RSI'].iloc[-5]) else 'Tidak terdeteksi'}")
                
                st.subheader("4. MOMENTUM")
                st.write(f"• **Strength:** {'Kuat' if last['Volume'] > df['Volume'].tail(20).mean() else 'Melemah'}")

            st.markdown("---")
            st.subheader("5. TRADING SIGNAL & PLAN (ATR BASED)")
            # Kalkulasi ATR
            sl = int(curr_price - (2 * atr))
            tp1 = int(curr_price + (2 * atr))
            tp2 = int(curr_price + (4 * atr))
            
            sig = "BUY" if (curr_price > last['MA20'] and last['MACD'] > last['Signal']) else "SELL" if curr_price < last['MA20'] else "HOLD"
            conf = "High" if abs(last['RSI']-50) > 20 else "Medium"
            
            p1, p2, p3 = st.columns(3)
            p1.metric("SIGNAL", sig, f"Confidence: {conf}")
            p2.error(f"**STOP LOSS**\n\n**Rp {sl:,.0f}**")
            p3.success(f"**TAKE PROFIT (TP2)**\n\n**Rp {tp2:,.0f}**")
            
            st.caption(f"Strategi: Swing Trading | TP1: {tp1} | Risk/Reward: 1:2")
