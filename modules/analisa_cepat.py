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
                rsi_series = 100 - (100 / (1 + (gain/loss)))
                rsi = rsi_series.iloc[-1]

                # Fundamental Metrics
                pe = info.get('trailingPE', 0)
                pbv = info.get('priceToBook', 0)
                roe = info.get('returnOnEquity', 0)
                mkt_cap = info.get('marketCap', 0)
                div_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0

                # --- LOGIKA 8 POIN ---

                # 1. Fundamental Score
                f_score = 0
                f_reasons = []
                if roe > 0.15: f_score += 3; f_reasons.append("Sangat Profitable")
                elif roe > 0.08: f_score += 2; f_reasons.append("Cukup Profitable")
                
                if 0 < pe < 15: f_score += 2; f_reasons.append("Valuasi Murah")
                elif pe > 30: f_score -= 1; f_reasons.append("Valuasi Premium")
                
                if mkt_cap > 50e12: f_score += 3; f_reasons.append("Big Cap")
                elif mkt_cap < 1e12: f_score -= 1; f_reasons.append("Small Cap")
                else: f_score += 1
                
                if div_yield > 3: f_score += 2; f_reasons.append(f"Dividen {div_yield:.1f}%")
                f_score = max(1, min(10, f_score))

                # 2. Technical Score
                t_score = 0
                t_reasons = []
                if curr_price > ma20: t_score += 3; t_reasons.append("Uptrend Pendek")
                if curr_price > ma200: t_score += 3; t_reasons.append("Bullish Panjang")
                if 30 < rsi < 60: t_score += 2; t_reasons.append("Momentum Stabil")
                elif rsi <= 30: t_score += 3; t_reasons.append("Oversold")
                elif rsi >= 70: t_score -= 1; t_reasons.append("Overbought")
                t_score = max(1, min(10, t_score))

                # 3. Sentiment
                if t_score >= 7: sentiment = "BULLISH 🐂"
                elif t_score >= 5: sentiment = "NEUTRAL 😐"
                else: sentiment = "BEARISH 🐻"

                # 4. Alasan BUY (Generated)
                buy_reasons = []
                if f_score >= 7: buy_reasons.append("Fundamental perusahaan sangat sehat.")
                if t_score >= 7: buy_reasons.append("Trend harga sedang kuat (Uptrend).")
                if rsi <= 35: buy_reasons.append("RSI di area jenuh jual (Diskon).")
                if div_yield > 4: buy_reasons.append(f"Yield dividen menarik ({div_yield:.1f}%).")
                if curr_price > ma200: buy_reasons.append("Harga di atas MA200 (Akumulasi).")
                if not buy_reasons: buy_reasons.append("Potensi pantulan teknikal sesaat.")
                
                # HTML String Preparation
                buy_str = "".join([f"<li>{r}</li>" for r in buy_reasons[:3]])

                # 5. Risiko (Generated)
                risk_reasons = []
                if pe > 25: risk_reasons.append("Valuasi mahal (PER > 25x).")
                if rsi > 70: risk_reasons.append("Rawan profit taking (RSI Tinggi).")
                if mkt_cap < 5e12: risk_reasons.append("Likuiditas saham kecil.")
                if curr_price < ma200: risk_reasons.append("Trend Utama masih Turun (Downtrend).")
                if f_score < 5: risk_reasons.append("Kinerja keuangan melemah.")
                if not risk_reasons: risk_reasons.append("Volatilitas pasar global.")
                
                # HTML String Preparation
                risk_str = "".join([f"<li>{r}</li>" for r in risk_reasons[:3]])

                # 6. Rekomendasi
                if f_score >= 7 and t_score >= 6: rec = "STRONG BUY"
                elif t_score >= 7: rec = "TRADING BUY"
                elif f_score >= 7 and t_score < 5: rec = "ACCUMULATE / HOLD"
                elif t_score < 4: rec = "WAIT AND SEE"
                else: rec = "HOLD"

                # 7. Target & SL (ATR FIX)
                # PERBAIKAN: .mean() sudah menghasilkan angka, tidak perlu .iloc[-1]
                atr = (df['High'] - df['Low']).tail(14).mean()
                
                sl = int(curr_price - (1.5 * atr))
                tp = int(curr_price + (2.5 * atr))

                # 8. Timeframe & Variabel Penjelas
                timeframe = "Jangka Panjang (Investasi)" if f_score >= 7 else "Jangka Pendek (Trading)"
                
                reason_f = ', '.join(f_reasons[:2]) if f_reasons else 'Kurang Menarik'
                reason_t = ', '.join(t_reasons[:2]) if t_reasons else 'Trend Lemah'

                # --- TAMPILAN OUTPUT FINAL ---
                st.subheader(f"Analisa Singkat: {info.get('longName', ticker_input)}")
                
                color_map = {"STRONG BUY": "green", "TRADING BUY": "blue", "ACCUMULATE / HOLD": "orange", "WAIT AND SEE": "red", "HOLD": "gray"}
                color = color_map.get(rec, "blue")

                html_content = f"""
                <div style="background-color: #1e2b3e; padding: 25px; border-radius: 12px; border-left: 8px solid {color};">
                    <h2 style="color: {color}; margin-top: 0; border-bottom: 1px solid #444; padding-bottom: 10px;">{rec}</h2>
                    
                    <ul style="line-height: 1.8; padding-left: 20px;">
                        <li><b>1. Fundamental Score:</b> {f_score}/10 <span style='color:gray'>({reason_f})</span></li>
                        <li><b>2. Technical Score:</b> {t_score}/10 <span style='color:gray'>({reason_t})</span></li>
                        <li><b>3. Sentiment Pasar:</b> {sentiment}</li>
                        <br>
                        <li><b>4. Alasan Utama BUY:</b>
                            <ul>{buy_str}</ul>
                        </li>
                        <br>
                        <li><b>5. Risiko Wajib Waspada:</b>
                            <ul>{risk_str}</ul>
                        </li>
                        <br>
                        <li><b>6. Rekomendasi Final:</b> <b>{rec}</b></li>
                        <li><b>7. Trading Plan:</b>
                            <br>🎯 Target Price: <b>Rp {tp:,.0f}</b>
                            <br>🛑 Stop Loss: <b>Rp {sl:,.0f}</b>
                        </li>
                        <li><b>8. Timeframe:</b> {timeframe}</li>
                    </ul>
                </div>
                """
                st.markdown(html_content, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Gagal melakukan analisa cepat: {e}")
