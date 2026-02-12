import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from modules.data_loader import get_full_stock_data

# --- FUNGSI MESIN INDIKATOR & PATTERN ---
def calculate_advanced_metrics(df):
    # 1. Moving Averages
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA50'] = df['Close'].rolling(50).mean()
    df['MA200'] = df['Close'].rolling(200).mean()
    
    # 2. Bollinger Bands
    df['BB_Mid'] = df['MA20']
    df['BB_Std'] = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + (2 * df['BB_Std'])
    df['BB_Lower'] = df['BB_Mid'] - (2 * df['BB_Std'])
    
    # 3. RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    # 4. MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal']
    
    # 5. ATR (Average True Range)
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    df['ATR'] = np.max(ranges, axis=1).rolling(14).mean()

    # 6. Support & Resistance (Pivot 20 hari)
    df['Support'] = df['Low'].rolling(window=20).min()
    df['Resistance'] = df['High'].rolling(window=20).max()
    
    return df

def detect_patterns(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    patterns = []
    
    body = abs(last['Close'] - last['Open'])
    range_day = last['High'] - last['Low']
    if body <= (range_day * 0.1): patterns.append("Doji (Indikasi Reversal/Konsolidasi)")
    
    lower_shadow = min(last['Open'], last['Close']) - last['Low']
    if lower_shadow > (2 * body) and body > 0: patterns.append("Hammer (Potensi Bullish Reversal)")
    
    if last['Close'] < prev['Close'] and last['RSI'] > prev['RSI']:
        patterns.append("Bullish Divergence (Momentum Menguat)")
    elif last['Close'] > prev['Close'] and last['RSI'] < prev['RSI']:
        patterns.append("Bearish Divergence (Momentum Melemah)")
        
    return patterns if patterns else ["Tidak ada pola spesifik terdeteksi"]

# --- MODUL UTAMA ---
def run_teknikal():
    st.title("📈 Analisa Teknikal Pro")
    st.markdown("---")

    ticker_input = st.text_input("Masukkan Kode Saham:", value="BBRI").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Jalankan Analisa Lengkap {ticker_input}"):
        with st.spinner("Mengkalkulasi ribuan titik data teknikal..."):
            data = get_full_stock_data(ticker)
            df = data["history"]
            
            if df.empty or len(df) < 200:
                st.error("Data historis tidak mencukupi untuk analisa MA200. Coba saham lain.")
                return

            df = calculate_advanced_metrics(df)
            last = df.iloc[-1]
            curr_price = last['Close']
            atr = last['ATR']
            
            # Trend Analysis
            ma200_trend = "UPTREND" if curr_price > last['MA200'] else "DOWNTREND"
            
            # Sinyal & Confidence
            score = 0
            reasons = []
            if curr_price > last['MA20']: score += 1; reasons.append("Harga di atas MA20 (Kuning)")
            if last['MACD'] > last['Signal']: score += 1; reasons.append("MACD Bullish Cross")
            if last['RSI'] < 30: score += 1; reasons.append("RSI Oversold")
            
            confidence = "High" if abs(score) >= 3 else "Medium" if abs(score) >= 2 else "Low"
            final_signal = "BUY" if score >= 1 else "SELL" if score <= -1 else "HOLD"

            # Trading Plan (ATR BASED)
            sl = int(curr_price - (2 * atr))
            tp1 = int(curr_price + (2 * atr))
            tp2 = int(curr_price + (4 * atr))
            tp3 = int(curr_price + (6 * atr))

            # --- VISUALISASI CHART (ADD MA20 KUNING) ---
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, 
                               row_heights=[0.6, 0.2, 0.2],
                               subplot_titles=("Price, MA (MA20 Kuning), & BB", "MACD", "RSI"))
            
            # Row 1: Candlestick & MAs
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
            
            # MA20 KUNING (Permintaan Khusus)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="MA20 (Kuning)"), row=1, col=1)
            
            # MA Lainnya
            fig.add_trace(go.Scatter(x=df.index, y=df['MA200'], line=dict(color='purple', width=2), name="MA200"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], line=dict(color='blue', width=1), name="MA50"), row=1, col=1)
            
            # Bollinger Bands
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], line=dict(color='gray', dash='dash'), name="BB Upper"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], line=dict(color='gray', dash='dash'), name="BB Lower"), row=1, col=1)
            
            # Row 2 & 3: MACD & RSI
            fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD Hist"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='yellow'), name="RSI"), row=3, col=1)
            fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1)
            fig.add_hline(y=30, line_dash="dot", line_color="green", row=3, col=1)

            fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- OUTPUT ANALISA (Tetap 5 Poin) ---
            st.markdown("---")
            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("1. TREND ANALYSIS")
                st.write(f"• Trend Utama: **{ma200_trend}**")
                st.write(f"• Resistance: Rp {last['Resistance']:,.0f}")
                st
