import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from modules.data_loader import get_full_stock_data

def calculate_metrics(df):
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA50'] = df['Close'].rolling(50).mean()
    df['MA200'] = df['Close'].rolling(200).mean()
    df['BB_Mid'] = df['MA20']
    df['BB_Std'] = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + (2 * df['BB_Std'])
    df['BB_Lower'] = df['BB_Mid'] - (2 * df['BB_Std'])
    
    # RSI & MACD
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal']

    # ATR (Average True Range)
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    
    return df

def run_teknikal():
    st.title("📈 Analisa Teknikal Pro")
    st.markdown("---")

    ticker_input = st.text_input("Kode Saham:", value="ASII").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Analisa {ticker_input}"):
        data = get_full_stock_data(ticker)
        df = data["history"]
        if df.empty or len(df) < 200:
            st.error("Data tidak cukup untuk analisa mendalam.")
            return

        df = calculate_metrics(df)
        last = df.iloc[-1]
        curr_price = last['Close']
        atr = last['ATR']

        # --- LOGIKA TRADING PLAN (MAX LOSS 8%) ---
        sl_atr = curr_price - (1.5 * atr)
        risk_pct = (curr_price - sl_atr) / curr_price
        
        # Cek apakah resiko > 8%
        if risk_pct > 0.08:
            # Gunakan batasan 8% atau Swing Low 10 hari (mana yang lebih ketat)
            swing_low = df['Low'].tail(10).min()
            sl_final = max(swing_low, curr_price * 0.92)
            metode_sl = "Hard Cap 8% / Swing Low"
        else:
            sl_final = sl_atr
            metode_sl = "ATR Dinamis (1.5x)"

        tp1 = int(curr_price + (curr_price - sl_final) * 1.5)
        tp2 = int(curr_price + (curr_price - sl_final) * 2.5)

        # --- VISUALISASI ---
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="MA20 Kuning"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA200'], line=dict(color='purple', width=2), name="MA200"), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD"), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='white'), name="RSI"), row=3, col=1)
        fig.update_layout(height=850, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- OUTPUT 5 POIN ---
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("1. TREND ANALYSIS")
            st.write(f"• **Trend Utama:** {'UPTREND' if curr_price > last['MA200'] else 'DOWNTREND'}")
            st.write(f"• **Support Terdekat:** Rp {df['Low'].tail(20).min():,.0f}")
            
            st.subheader("2. INDIKATOR TEKNIKAL")
            st.write(f"• **RSI:** {last['RSI']:.1f} ({'Oversold' if last['RSI']<30 else 'Overbought' if last['RSI']>70 else 'Netral'})")
            st.write(f"• **MACD:** {'Bullish' if last['MACD'] > last['Signal'] else 'Bearish'}")

        with c2:
            st.subheader("3. PATTERN & MOMENTUM")
            st.write(f"• **Pola:** {'Doji' if abs(last['Open']-last['Close']) < (last['High']-last['Low'])*0.1 else 'Normal'}")
            st.write(f"• **Tekanan:** {'Buying Pressure Kuat' if last['Volume'] > df['Volume'].tail(20).mean() else 'Melemah'}")

            st.subheader("4. TRADING SIGNAL")
            signal = "BUY" if (curr_price > last['MA20'] and last['MACD'] > last['Signal']) else "HOLD/SELL"
            st.markdown(f"### Sinyal: **{signal}**")

        st.subheader("5. TRADING PLAN (Max Loss 8%)")
        p1, p2, p3 = st.columns(3)
        p1.error(f"**STOP LOSS**\n\n**Rp {sl_final:,.0f}**\n({metode_sl})")
        p2.success(f"**TAKE PROFIT (TP1)**\n\n**Rp {tp1:,.0f}**")
        p3.info(f"**RISK/REWARD**\n\nRRR: 1:1.5\nRisk: {((curr_price-sl_final)/curr_price)*100:.1f}%")
