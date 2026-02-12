import streamlit as st
import pandas as pd
import numpy as np
from modules.data_loader import ambil_data_history, ambil_data_fundamental_lengkap

def run_analisa_cepat():
    st.title("⚡ Analisa Cepat (8 Poin Inti)")
    st.markdown("---")

    col1, _ = st.columns([1, 2])
    with col1:
        ticker_input = st.text_input("Kode Saham:", value="BBCA").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"⚡ Analisa Kilat {ticker_input}"):
        with st.spinner("Menganalisa 8 Poin Penting..."):
            try:
                # 1. AMBIL DATA
                df = ambil_data_history(ticker, period="1y")
                info, financials, _ = ambil_data_fundamental_lengkap(ticker)

                if df.empty:
                    st.error("Data saham tidak ditemukan.")
                    return

                # --- DATA PROCESSING ---
                curr_price = df['Close'].iloc[-1]
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                ma200 = df['Close'].rolling(200).mean().iloc[-1]
                
                # RSI Calculation
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rsi = 100 - (100 / (1 + (gain/loss))).iloc[-1]

                # Fundamental Metrics
                pe = info.get('trailingPE', 0)
                pbv = info.get('priceToBook', 0)
                roe = info.get('returnOnEquity', 0)
                mkt_cap = info.get('marketCap', 0)
                div_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0

                # --- LOGIKA 8 POIN ---

                # 1. Fundamental Score (1-10)
                f_score = 0
                f_reasons = []
                if roe > 0.15: f_score += 3; f_reasons.append("Sangat Profitable (ROE > 15%)")
                elif roe > 0.08: f_score += 2; f_reasons.append("Cukup Profitable")
                
                if 0 < pe < 15: f_score += 2; f_reasons.append("Valuasi Murah (PER < 15)")
                elif pe > 30: f_score -= 1; f_reasons.append("Valuasi Premium")
                
                if mkt_cap > 50e12: f_score += 3; f_reasons.append("Big Cap (Aman)")
                elif mkt_cap < 1e12: f_score -= 1; f_reasons.append("Small Cap (Volatil)")
                else: f_score += 1
                
                if div_yield > 3: f_score += 2; f_reasons.append(f"Dividen {div_yield:.1f}%")
                
                f_score = max(1, min(10, f_score)) # Cap 1-10

                # 2. Technical Score (1-10)
                t_score = 0
                t_reasons = []
                if curr_price > ma20: t_score += 3; t_reasons.append("Uptrend Jangka Pendek")
                if curr_price > ma200: t_score += 3; t_reasons.append("Bullish Jangka Panjang")
                if 30 < rsi < 60: t_score += 2; t_reasons.append("Momentum Stabil")
                elif rsi <= 30: t_score += 3; t_reasons.append("Oversold (Diskon Teknikal)")
                elif rsi >= 70: t_score -= 1; t_reasons.append("Overbought (Rawan Koreksi)")
                
                t_score = max(1, min(10, t_score))

                # 3. Sentiment
                if t_score >= 7: sentiment = "BULLISH 🐂"
                elif t_score >= 5: sentiment = "NEUTRAL 😐"
                else: sentiment = "BEARISH 🐻"

                # 4. Tiga Alasan BUY (Dinamis)
                buy_reasons = []
                if f_score >= 7: buy_reasons.append("Fundamental perusahaan sangat sehat & profitable.")
                if t_score >= 7: buy_reasons.append("Trend harga sedang kuat (Uptrend).")
                if rsi <= 35: buy_reasons.append("Indikator RSI menunjukkan area jenuh jual (Murah).")
                if div_yield > 4: buy_reasons.append(f"Imbal hasil dividen menarik ({div_yield:.1f}%).")
                if curr_price > ma200: buy_reasons.append("Harga di atas MA200 (Fase Akumulasi).")
                if not buy_reasons: buy_reasons.append("Potensi rebound teknikal sesaat.")
                
                # Ambil 3 Teratas
                buy_points = "".join([f"<li>{r}</li>" for r in buy_reasons[:3]])

                # 5. Tiga Risiko Utama (Dinamis)
                risk_reasons = []
                if pe > 25: risk_reasons.append("Valuasi sudah tergolong mahal (PER > 25x).")
                if rsi > 70: risk_reasons.append("Rawan profit taking (RSI Jenuh Beli).")
                if mkt_cap < 5e12: risk_reasons.append("Likuiditas saham lapis kedua/ketiga.")
                if curr_price < ma200: risk_reasons.append("Masih dalam fase Downtrend Besar.")
                if f_score < 5: risk_reasons.append("Kinerja keuangan kurang memuaskan.")
                if not risk_reasons: risk_reasons.append("Volatilitas pasar global.")
                
                risk_points = "".join([f"<li>{r}</li>" for r in risk_reasons[:3]])

                # 6. Rekomendasi
                if f_score >= 7 and t_score >= 6: rec = "STRONG BUY"
                elif t_score >= 7: rec = "TRADING BUY"
                elif f_score >= 7 and t_score < 5: rec = "ACCUMULATE / HOLD"
                elif t_score < 4: rec = "WAIT AND SEE"
                else: rec = "HOLD"

                # 7. Target & SL (ATR Based)
                atr = (df['High'] - df['Low']).tail(14).mean().iloc[-1]
                sl = int(curr_price - (1.5 * atr))
                tp = int(curr_price + (2.5 * atr))

                # 8. Timeframe
                timeframe = "Jangka Panjang (Investasi)" if f_score >=
