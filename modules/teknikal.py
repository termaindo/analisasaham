import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from modules.data_loader import ambil_data_history, ambil_data_fundamental_lengkap

# --- 1. FUNGSI KALKULASI INDIKATOR ---
def calculate_indicators(df):
    # Moving Averages
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    # Bollinger Bands
    df['BB_Mid'] = df['MA20']
    df['BB_Std'] = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Mid'] + (2 * df['BB_Std'])
    df['BB_Lower'] = df['BB_Mid'] - (2 * df['BB_Std'])
    
    # RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    # MACD (12, 26, 9)
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal_Line']
    
    # ATR (Average True Range) untuk Stop Loss Dinamis
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    return df

def identify_patterns(df):
    # Pola Sederhana: Hammer & Doji
    # Hammer: Buntut bawah panjang, body kecil di atas
    df['Body'] = np.abs(df['Close'] - df['Open'])
    df['Lower_Shadow'] = np.minimum(df['Close'], df['Open']) - df['Low']
    df['Upper_Shadow'] = df['High'] - np.maximum(df['Close'], df['Open'])
    
    # Logic Hammer: Buntut bawah > 2x Body & Buntut atas kecil
    df['Hammer'] = (df['Lower_Shadow'] > 2 * df['Body']) & (df['Upper_Shadow'] < 0.5 * df['Body'])
    
    # Logic Doji: Body sangat kecil
    df['Doji'] = df['Body'] <= (df['Close'] * 0.001) # Body < 0.1% harga
    
    return df

# --- 2. PROGRAM UTAMA ---
def run_teknikal():
    st.title("📈 Analisa Teknikal Pro (5 Aspek)")
    st.markdown("---")

    col1, _ = st.columns([1, 2])
    with col1:
        ticker_input = st.text_input("Kode Saham:", value="BBRI").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Analisa Lengkap {ticker_input}"):
        try:
            with st.spinner("Mengkalkulasi indikator & pattern..."):
                # Ambil Data (2 Tahun agar MA200 valid)
                df = ambil_data_history(ticker, period="2y")
                
                if df.empty:
                    st.error("Data saham tidak ditemukan.")
                    return

                # Hitung Indikator
                df = calculate_indicators(df)
                df = identify_patterns(df)
                
                # Data Terakhir
                last = df.iloc[-1]
                prev = df.iloc[-2]
                curr_price = last['Close']
                
                # --- A. TREND ANALYSIS ---
                # Tentukan Trend Utama berdasarkan MA200 & MA50
                if curr_price > last['MA200'] and last['MA50'] > last['MA200']:
                    trend = "UPTREND (Bullish Utama)"
                    trend_color = "green"
                elif curr_price < last['MA200'] and last['MA50'] < last['MA200']:
                    trend = "DOWNTREND (Bearish Utama)"
                    trend_color = "red"
                else:
                    trend = "SIDEWAYS / KONSOLIDASI"
                    trend_color = "orange"
                    
                # Support & Resistance (Donchian 20 Hari)
                res_level = df['High'].tail(20).max()
                sup_level = df['Low'].tail(20).min()

                # --- B. SIGNAL SCORING (LOGIKA CONFIDENCE) ---
                score = 0
                reasons = []
                
                # 1. MA Score
                if curr_price > last['MA20']: score += 20; reasons.append("Harga > MA20 (Short Term Bull)")
                if curr_price > last['MA200']: score += 20; reasons.append("Harga > MA200 (Long Term Bull)")
                
                # 2. MACD Score
                if last['MACD'] > last['Signal_Line']: 
                    score += 20
                    reasons.append("MACD Golden Cross")
                elif last['MACD_Hist'] > prev['MACD_Hist']: # Histogram menanjak
                    score += 10
                    reasons.append("Momentum MACD Menguat")
                    
                # 3. RSI Score
                if 40 < last['RSI'] < 60: score += 10 # Zona aman
                elif 60 <= last['RSI'] < 70: score += 20; reasons.append("RSI Bullish Momentum")
                elif last['RSI'] <= 30: score += 15; reasons.append("RSI Oversold (Potensi Rebound)")
                
                # 4. Volume Score
                vol_ma = df['Volume'].rolling(20).mean().iloc[-1]
                if last['Volume'] > vol_ma: score += 10; reasons.append("Volume di atas rata-rata")

                # Tentukan Confidence Level
                if score >= 70: confidence = "HIGH"; signal = "STRONG BUY"
                elif score >= 50: confidence = "MEDIUM"; signal = "BUY / ACCUMULATE"
                elif score >= 30: confidence = "LOW"; signal = "NEUTRAL / HOLD"
                else: confidence = "HIGH"; signal = "STRONG SELL"

                # --- C. TRADING PLAN (ENTRY, TP, SL) ---
                atr = last['ATR']
                stop_loss = int(curr_price - (1.5 * atr)) # SL konservatif
                tp1 = int(curr_price + (1.5 * atr))       # RR 1:1
                tp2 = int(curr_price + (3.0 * atr))       # RR 1:2
                tp3 = int(curr_price + (4.5 * atr))       # RR 1:3
                rr_ratio = (tp2 - curr_price) / (curr_price - stop_loss)

                # --- VISUALISASI CHART (4 ROW) ---
                fig = make_subplots(rows=4, cols=1, shared_xaxes=True, 
                                    vertical_spacing=0.05, 
                                    row_heights=[0.5, 0.15, 0.15, 0.2],
                                    subplot_titles=(f"Price & MA ({trend})", "Volume", "MACD", "RSI"))

                # Row 1: Candlestick, MA, BB
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], line=dict(color='blue', width=1), name='MA50'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['MA200'], line=dict(color='purple', width=2), name='MA200'), row=1, col=1)
                # Bollinger Bands (Area)
                fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], line=dict(color='gray', width=0), showlegend=False), row=1, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], line=dict(color='gray', width=0), fill='tonexty', fillcolor='rgba(128,128,128,0.1)', name='BB'), row=1, col=1)

                # Row 2: Volume
                colors = ['green' if c >= o else 'red' for c, o in zip(df['Close'], df['Open'])]
                fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)

                # Row 3: MACD
                fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='blue', width=1), name='MACD'), row=3, col=1)
                fig.add_trace(go.Scatter(x=df.index, y=df['Signal_Line'], line=dict(color='orange', width=1), name='Signal'), row=3, col=1)
                fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color='gray', name='Hist'), row=3, col=1)

                # Row 4: RSI
                fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='white', width=1), name='RSI'), row=
