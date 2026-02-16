import sys
import os

# --- PENGATURAN PATH ROOT ---
# Memastikan Python selalu mengenali folder utama project
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Sekarang pemanggilan 'modules.' dijamin tidak akan error
from modules.data_loader import get_full_stock_data
from modules.universe import is_syariah

# --- FUNGSI ANALISA TEKNIKAL MENDALAM ---
def calculate_technical_pro(df):
    # 1. Moving Averages
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA50'] = df['Close'].rolling(50).mean()
    df['MA200'] = df['Close'].rolling(200).mean()
    
    # 2. RSI (Relative Strength Index)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    # 3. MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal_Line']
    
    # 4. Bollinger Bands
    df['BB_Mid'] = df['MA20']
    df['BB_Std'] = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + (2 * df['BB_Std'])
    df['BB_Lower'] = df['BB_Mid'] - (2 * df['BB_Std'])

    # 5. ATR (Average True Range)
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    
    # --- TAMBAHAN INDIKATOR UNTUK SCORING 100 POIN ---
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP_20'] = (df['Typical_Price'] * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['Value'] = df['Close'] * df['Volume']
    
    return df

def run_teknikal():
    st.title("📈 Analisa Teknikal Pro (5 Dimensi Lengkap)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="BBRI").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Jalankan Analisa Lengkap {ticker_input}"):
        with st.spinner("Mengevaluasi tren, indikator, dan pola..."):
            # --- STANDAR ANTI-ERROR ---
            data = get_full_stock_data(ticker)
            df = data['history']
            
            if df.empty or len(df) < 200:
                st.error("Data tidak mencukupi untuk analisa MA200. Mohon coba saham lain.")
                return

            # --- CEK STATUS SYARIAH ---
            clean_ticker = ticker_input.replace(".JK", "")
            status_syariah = "[Syariah]" if is_syariah(clean_ticker) else "[Non-Syariah]"
            
            # Menampilkan header hasil analisa beserta status syariah
            st.subheader(f"Hasil Analisa: {clean_ticker} {status_syariah}")

            df = calculate_technical_pro(df)
            last = df.iloc[-1]
            prev = df.iloc[-5] # Untuk cek momentum 1 minggu lalu
            curr_price = last['Close']
            atr = last['ATR']

            # --- 1. TREND ANALYSIS (Timeframe Check) ---
            main_trend = "UPTREND" if curr_price > last['MA200'] else "DOWNTREND"
            # Simulasi Weekly/Monthly berdasarkan kemiringan MA
            weekly_trend = "Bullish" if last['MA50'] > prev['MA50'] else "Bearish"
            res_level = df['High'].tail(20).max()
            sup_level = df['Low'].tail(20).min()

            # --- 2. INDIKATOR TEKNIKAL & 3. PATTERN ---
            # Deteksi Divergence Sederhana
            is_div = "Terdeteksi (Bullish)" if (curr_price < prev['Close'] and last['RSI'] > prev['RSI']) else "Tidak Terdeteksi"
            
            # --- 5. TRADING SIGNAL & ATR SL (LOCK 8%) ---
            sl_raw = curr_price - (1.5 * atr)
            # LOGIKA KUNCI 8%
            sl_final = max(sl_raw, curr_price * 0.92)
            metode_sl = "ATR (1.5x)" if sl_final == sl_raw else "Hard Cap (8%)"
            
            risk_amount = curr_price - sl_final
            tp1 = int(curr_price + (risk_amount * 1.5))
            tp2 = int(curr_price + (risk_amount * 2.5))
            tp3 = int(curr_price + (risk_amount * 3.5))
            rrr = round((tp2 - curr_price) / (curr_price - sl_final), 1)

            # ==========================================
            # KONFIRMASI SINYAL (LOGIKA SCORING 100 POIN)
            # ==========================================
            curr_vol = last['Volume'] if not pd.isna(last['Volume']) else 0
            avg_vol_20 = last['Vol_MA20'] if not pd.isna(last['Vol_MA20']) else 0
            vwap_val = last['VWAP_20'] if not pd.isna(last['VWAP_20']) else curr_price
            ema9_val = last['EMA9']
            ema21_val = last['EMA21']
            avg_value_ma20 = df['Value'].rolling(20).mean().iloc[-1]
            prev_close_1 = df['Close'].iloc[-2]

            score = 0
            # 1. Relative Volume (20 Poin)
            if curr_vol > avg_vol_20: score += 20
            # 2. VWAP Alignment (20 Poin)
            if curr_price > vwap_val: score += 20
            # 3. RSI Momentum (20 Poin)
            if 50 < last['RSI'] < 70: score += 20
            # 4. EMA 9/21 Cross (20 Poin)
            if ema9_val > ema21_val: score += 20
            # 5. Price Action/Gap (10 Poin)
            if (curr_price - prev_close_1) / prev_close_1 > 0.02: score += 10
            # 6. Value MA20 (10 Poin)
            if avg_value_ma20 > 5e9: score += 10

            # Mapping Rekomendasi
            if score >= 70:
                signal = "STRONG BUY"
                confidence = "High"
            elif score >= 50:
                signal = "BUY"
                confidence = "Medium"
            elif score >= 40:
                signal = "HOLD"
                confidence = "Medium"
            else:
                signal = "SELL"
                confidence = "Low"

            # --- LOGIKA RENTANG ENTRY (SUPPORT DINAMIS) ---
            entry_atas = curr_price
            support_dinamis = max(vwap_val, last['MA20'])
            batas_diskon_2pct = curr_price * 0.98
            
            if support_dinamis < curr_price:
                entry_bawah = max(support_dinamis, batas_diskon_2pct)
            else:
                entry_bawah = batas_diskon_2pct
            # ==========================================

            # --- VISUALISASI CHART ---
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
            
            # Chart Utama (MA20 KUNING)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="MA20 (Kuning)"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA200'], line=dict(color='purple', width=2), name="MA200"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], line=dict(color='rgba(173, 216, 230, 0.2)'), name="BB Upper"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], line=dict(color='rgba(173, 216, 230, 0.2)'), fill='tonexty', name="BB Lower"), row=1, col=1)

            # MACD & RSI
            fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD Hist"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='white'), name="RSI"), row=3, col=1)
            
            fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- PENYAJIAN DATA 5 POIN ---
            st.markdown("---")
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("1. TREND ANALYSIS")
                st.write(f"• **Trend Utama (Daily):** {main_trend}")
                st.write(f"• **Trend Weekly/Monthly:** {weekly_trend}")
                st.write(f"• **Support/Resist:** Rp {sup_level:,.0f} / Rp {res_level:,.0f}")
                
                st.subheader("2. INDIKATOR TEKNIKAL")
                st.write(f"• **Posisi MA:** Harga {'di atas' if curr_price > last['MA20'] else 'di bawah'} MA20 Kuning")
                st.write(f"• **RSI:** {last['RSI']:.1f} ({'Overbought' if last['RSI']>70 else 'Oversold' if last['RSI']<30 else 'Neutral'})")
                st.write(f"• **MACD:** {'Bullish Cross' if last['MACD'] > last['Signal_Line'] else 'Bearish'}")
                st.write(f"• **Volatilitas:** {'Tinggi' if (last['BB_Upper']-last['BB_Lower']) > (df['BB_Upper']-df['BB_Lower']).mean() else 'Rendah'}")

            with c2:
                st.subheader("3. PATTERN RECOGNITION")
                pattern = "Doji" if abs(last['Open']-last['Close']) < (last['High']-last['Low'])*0.1 else "Normal"
                st.write(f"• **Candlestick:** {pattern}")
                st.write(f"• **Chart Pattern:** Potensi Konsolidasi / Channeling")
                st.write(f"• **Divergence:** {is_div}")

                st.subheader("4. MOMENTUM & STRENGTH")
                st.write(f"• **Momentum:** {'Kuat' if last['RSI'] > 50 else 'Lemah'}")
                st.write(f"• **Pressure:** {'Buying Pressure' if last['Close'] > last['Open'] else 'Selling Pressure'}")

            st.markdown("---")
            st.subheader("5. TRADING SIGNAL & PLAN")
            s1, s2, s3 = st.columns(3)
            with s1:
                st.metric("SINYAL", signal, f"Score: {score}/100 | Conf: {confidence}")
                st.write(f"**Entry Zone:** Rp {int(entry_bawah):,.0f} - Rp {int(entry_atas):,.0f}")
            with s2:
                st.error(f"**STOP LOSS**\n\n**Rp {sl_final:,.0f}**\n(Metode: {metode_sl})")
            with s3:
                st.success(f"**TAKE PROFIT**\n\nTP1: {tp1}\nTP2: {tp2}\nTP3: {tp3}")
            
            st.caption(f"Risk/Reward: 1 : {rrr} | Style: Swing Trading | Max Risk Locked: 8.0%")

            # --- DISCLAIMER ---
            st.markdown("---")
            st.warning("""
            **DISCLAIMER:** Semua informasi, analisa teknikal, dan sinyal trading yang disediakan di modul ini hanya untuk tujuan edukasi dan informasi. Ini bukan merupakan rekomendasi, ajakan, atau nasihat keuangan untuk membeli atau menjual saham tertentu. Keputusan investasi sepenuhnya berada di tangan Anda. Harap lakukan riset Anda sendiri (*Do Your Own Research*) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.
            """)
