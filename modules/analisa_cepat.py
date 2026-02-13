import streamlit as st
import pandas as pd
import numpy as np
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_analisa_cepat():
    st.title("⚡ Analisa Cepat Pro (Scoring System V2)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Quick Check):", value="BBCA").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button("🚀 Jalankan Analisa"):
        with st.spinner("Menghitung Skor Fundamental & Teknikal..."):
            # --- STANDAR ANTI-ERROR ---
            data = get_full_stock_data(ticker)
            info = data['info']
            df = data['history']
            
            if df.empty or not info:
                st.error("Data gagal dimuat. Mohon tunggu 1 menit lalu 'Clear Cache'.")
                return

            # --- DATA PROCESSING (INDIKATOR UTAMA) ---
            curr = df['Close'].iloc[-1]
            
            # Moving Averages
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            ma200 = df['MA200'].iloc[-1] if 'MA200' in df.columns else df['Close'].rolling(200).mean().iloc[-1]
            
            # ATR untuk Stop Loss
            atr = (df['High'] - df['Low']).tail(14).mean()
            
            # RSI (Relative Strength Index) untuk Momentum
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]

            # Rata-rata Transaksi Harian (Value) - Cek Likuiditas
            avg_val_5d = (df['Close'] * df['Volume']).rolling(5).mean().iloc[-1]

            # --- LOGIKA STOP LOSS (Tetap Mempertahankan Standar Lama) ---
            sl_raw = curr - (1.5 * atr)
            sl_final = max(sl_raw, curr * 0.92)
            metode_sl = "ATR (1.5x)" if sl_final == sl_raw else "Max Risk 8%"
            tp = int(curr + (curr - sl_final) * 2.5) # RRR 1:2.5

            # ==============================================================================
            # 1. SISTEM SCORING FUNDAMENTAL (Weighted)
            # ==============================================================================
            # Data Fetching dengan Safety Default
            roe = info.get('returnOnEquity', 0) if info.get('returnOnEquity') else 0
            der = info.get('debtToEquity', 0) if info.get('debtToEquity') else 100 # Default moderate
            per = info.get('trailingPE', 0) if info.get('trailingPE') else 0
            pbv = info.get('priceToBook', 0) if info.get('priceToBook') else 0
            rev_growth = info.get('revenueGrowth', 0) if info.get('revenueGrowth') else 0
            
            f_points = 0
            f_reasons = []

            # A. Solvabilitas (Fatalitas Tinggi) - Bobot 25%
            # Note: Yahoo Finance biasanya return DER dalam persen (misal 150 = 1.5x)
            if der < 100: 
                f_points += 25
                f_reasons.append("Hutang Aman (DER < 1x)")
            elif der < 200:
                f_points += 10
            else:
                f_reasons.append("Hutang Tinggi (DER > 2x)")

            # B. Profitabilitas (Mesin Uang) - Bobot 35%
            if roe > 0.15:
                f_points += 35
                f_reasons.append(f"Profitabilitas Super (ROE {roe*100:.1f}%)")
            elif roe > 0.08:
                f_points += 15
                f_reasons.append("Profitabilitas Moderat")
            else:
                f_reasons.append("Profitabilitas Rendah")

            # C. Valuasi (Mahal/Murah) - Bobot 20%
            if per > 0 and per < 15:
                f_points += 20
                f_reasons.append("Valuasi Wajar/Murah")
            elif per > 30:
                f_points += 0
                f_reasons.append("Valuasi Mahal")
            else:
                f_points += 10

            # D. Pertumbuhan (Growth) - Bobot 20%
            if rev_growth > 0:
                f_points += 20
            else:
                f_reasons.append("Revenue Negatif/Stagnan")

            f_score = int(f_points / 10) # Skala 1-10
            f_score_color = "#00ff00" if f_score >= 7 else "#ffcc00" if f_score >= 5 else "#ff0000"

            # ==============================================================================
            # 2. SISTEM SCORING TEKNIKAL (Weighted)
            # ==============================================================================
            t_points = 0
            t_reasons = []

            # A. Likuiditas (Fatalitas Utama) - Bobot 20%
            # Ambang batas likuiditas: 2 Miliar per hari
            is_liquid = avg_val_5d > 2_000_000_000 
            if is_liquid:
                t_points += 20
            else:
                t_reasons.append("❗ Saham Kurang Likuid (<2M)")

            # B. Tren Utama (Market Structure) - Bobot 40%
            if curr > ma200:
                t_points += 40
                t_reasons.append("Major Uptrend (Diatas MA200)")
            else:
                t_reasons.append("Major Downtrend (Dibawah MA200)")

            # C. Momentum Jangka Pendek - Bobot 20%
            if curr > ma20:
                t_points += 20
                t_reasons.append("Momentum Kuat (Diatas MA20)")
            else:
                t_reasons.append("Koreksi Jangka Pendek")

            # D. Indikator Osilator (RSI) - Bobot 20%
            if 40 <= rsi <= 70:
                t_points += 20 # Zona ideal
            elif rsi < 30:
                t_points += 15
                t_reasons.append("Oversold (Potensi Rebound)")
            elif rsi > 70:
                t_points += 5
                t_reasons.append("Overbought (Hati-hati)")

            t_score = int(t_points / 10)
            t_score_color = "#00ff00" if t_score >= 7 else "#ffcc00" if t_score >= 5 else "#ff0000"

            # --- SENTIMEN GABUNGAN ---
            sentiment = "STRONG BULLISH 🐂" if f_score >= 7 and t_score >= 7 else \
                        "BULLISH 🐂" if t_score >= 6 else \
                        "BEARISH 🐻" if t_score < 4 else "NEUTRAL 😐"
            
            recommendation = "BUY" if f_score >= 6 and t_score >= 6 and is_liquid else \
                             "WAIT/HOLD" if t_score >= 5 else "SELL/AVOID"
            rec_color = "#00ff00" if recommendation == "BUY" else "#ffffff"

            # String gabungan alasan untuk display ringkas
            f_reason_str = ", ".join(f_reasons[:2]) if f_reasons else "Data Fundamental Standar"
            t_reason_str = ", ".join(t_reasons[:2]) if t_reasons else "Teknikal Netral"

            # --- TAMPILAN 8 POIN (RINGKAS & PADAT) ---
            html_output = f"""
<div style="background-color:#1e2b3e; padding:25px; border-radius:12px; border-left:10px solid {rec_color}; color:#e0e0e0; font-family:sans-serif;">
    <h3 style="margin-top:0; color:
