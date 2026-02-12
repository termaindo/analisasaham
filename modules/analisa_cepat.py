import streamlit as st
import pandas as pd
import numpy as np
from modules.data_loader import ambil_data_history, ambil_data_fundamental_lengkap

def run_analisa_cepat():
    st.title("⚡ Analisa Cepat (Quick Check)")
    st.markdown("---")

    col1, _ = st.columns([1, 2])
    with col1:
        ticker_input = st.text_input("Kode Saham:", value="BBCA").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"⚡ Analisa Kilat {ticker_input}"):
        with st.spinner("Mengunyah data..."):
            try:
                # 1. AMBIL DATA (Anti-Error Loader)
                df = ambil_data_history(ticker, period="1y")
                info, financials, _ = ambil_data_fundamental_lengkap(ticker)

                if df.empty:
                    st.error("Data saham tidak ditemukan.")
                    return

                # --- 2. HITUNG METRIK TEKNIKAL ---
                curr_price = df['Close'].iloc[-1]
                
                # MA & Trend
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                ma200 = df['Close'].rolling(200).mean().iloc[-1]
                
                # RSI
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rsi = 100 - (100 / (1 + (gain/loss))).iloc[-1]

                # --- 3. HITUNG METRIK FUNDAMENTAL ---
                pe = info.get('trailingPE', 0)
                pbv = info.get('priceToBook', 0)
                roe = info.get('returnOnEquity', 0)
                mkt_cap = info.get('marketCap', 0)

                # --- 4. LOGIKA SKORING (OTOMATIS) ---
                
                # A. Fundamental Score (Max 10)
                f_score = 0
                f_reasons = []
                if roe > 0.1: f_score += 3; f_reasons.append("Profitable (ROE > 10%)")
                if 0 < pe < 20: f_score += 2; f_reasons.append("Valuasi Wajar (PER < 20)")
                if pbv < 2: f_score += 2; f_reasons.append("Harga Buku Wajar") 
                if mkt_cap > 10e12: f_score += 3; f_reasons.append("Big Cap / Bluechip")
                else: f_score += 1
                
                # B. Technical Score (Max 10)
                t_score = 0
                t_reasons = []
                if curr_price > ma20: t_score += 3; t_reasons.append("Uptrend Jangka Pendek (>MA20)")
                if curr_price > ma200: t_score += 3; t_reasons.append("Uptrend Jangka Panjang (>MA200)")
                if 40 < rsi < 65: t_score += 2; t_reasons.append("Momentum Stabil")
                elif rsi <= 30: t_score += 2; t_reasons.append("Oversold (Murah secara teknikal)")
                
                # C. Tentukan Sentiment & Rekomendasi
                if t_score >= 8: sentiment = "BULLISH 🐂"; rec = "BUY"
                elif t_score >= 5: sentiment = "NEUTRAL 😐"; rec = "HOLD"
                else: sentiment = "BEARISH 🐻"; rec = "WAIT / SELL"
                
                if f_score < 5 and rec == "BUY": rec = "TRADING BUY" (Fundamental lemah)

                # D. Target & SL
                atr = (df['High'] - df['Low']).tail(14).mean().iloc[-1]
                sl = int(curr_price - (1.5 * atr))
                tp = int(curr_price + (2.0 * atr))

                # --- 5. TAMPILKAN HASIL (FORMAT 8 POIN) ---
                st.subheader(f"Hasil Analisa: {info.get('longName', ticker_input)}")
                
                # Warna Card Berdasarkan Rekomendasi
                color = "green" if "BUY" in rec else "orange" if "HOLD" in rec else "red"
                
                output_html = f"""
                <div style="border: 1px solid #ddd; padding: 20px; border-radius: 10px; background-color: #1e2b3e;">
                    <h2 style="color: {color}; margin-top: 0;">{rec}</h2>
                    <ul style="list-style-type: none; padding: 0;">
                        <li><b>1. Fundamental Score:</b> {f_score}/10 ({', '.join(f_reasons) if f_reasons else 'Fundamental Kurang Menarik'})</li>
                        <li><b>2. Technical Score:</b> {t_score}/10 ({', '.join(t_reasons) if t_reasons else 'Trend Lemah'})</li>
                        <li><b>3. Sentiment Pasar:</b> {sentiment}</li>
                        <br>
                        <li><b>4. Alasan BUY (Pros):</b>
                            <ul>
                                <li>{'Fundamental Perusahaan Sehat' if f_score > 6 else 'Potensi Rebound Teknikal'}</li>
                                <li>{'Trend Harga Positif' if t_score > 6 else 'RSI di area Diskon'}</li>
                                <li>Posisi Industri: {'Market Leader' if mkt_cap > 50e12 else 'Challenger/Grower'}</li>
                            </ul>
                        </li>
                        <br>
                        <li><b>5. Risiko Utama (Cons):</b>
                            <ul>
                                <li>{'Valuasi Premium' if pe > 25 else 'Volatilitas Pasar'}</li>
                                <li>{'Rawan Profit Taking' if rsi > 70 else 'Trend belum konfirmasi kuat' if t_score < 6 else 'Likuiditas harian'}</li>
                                <li>Stop Loss wajib disiplin.</li>
                            </ul>
                        </li>
                        <br>
                        <li><b>6. Rekomendasi Final:</b> <b>{rec}</b></li>
                        <li><b>7. Plan:</b> Target Rp {tp:,.0f} | Stop Loss Rp {sl:,.0f}</li>
                        <li><b>8. Timeframe:</b> {'Jangka Panjang (Investasi)' if f_score >= 8 else 'Jangka Pendek (Trading)'}</li>
                    </ul>
                </div>
                """
                st.markdown(output_html, unsafe_allow_html=True)
                
                st.caption("*Analisa dihasilkan otomatis oleh algoritma berdasarkan data historis & laporan keuangan terakhir.*")

            except Exception as e:
                st.error(f"Gagal menganalisa: {e}")
