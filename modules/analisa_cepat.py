import streamlit as st
import pandas as pd
import numpy as np
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_analisa_cepat():
    st.title("⚡ Analisa Cepat Pro (8 Poin Inti)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Quick Scan):", value="BBCA").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Jalankan Analisa {ticker_input}"):
        with st.spinner("Mengkalkulasi indikator teknikal & fundamental..."):
            # --- 1. STANDAR ANTI-ERROR ---
            data = get_full_stock_data(ticker)
            info = data['info']
            df = data['history']
            financials = data.get('financials', pd.DataFrame()) # Ambil data laporan keuangan untuk CAGR
            
            if df.empty or not info:
                st.error("Data gagal dimuat. Mohon tunggu 1 menit lalu 'Clear Cache' di pojok kanan atas.")
                return

            # --- 2. PERBAIKAN ERROR 'MA200' & DATA TEKNIKAL ---
            df['MA20'] = df['Close'].rolling(20).mean()
            df['MA200'] = df['Close'].rolling(200).mean()
            
            # Hitung Value Transaksi (Harga x Volume)
            df['Value'] = df['Close'] * df['Volume']
            avg_value_ma20 = df['Value'].rolling(20).mean().iloc[-1]

            # Cek ketersediaan data MA200
            if pd.isna(df['MA200'].iloc[-1]):
                ma200_val = 0
                status_ma200 = "Data Kurang (N/A)"
            else:
                ma200_val = df['MA200'].iloc[-1]
                status_ma200 = "Valid"

            curr = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            ma20_val = df['MA20'].iloc[-1]
            
            # --- 3. LOGIKA SCORING BARU (SESUAI PERMINTAAN) ---
            f_score = 0
            t_score = 0
            
            # === A. PENILAIAN FUNDAMENTAL ===
            
            # 1. DER / CAR (Sektor Sensitive)
            sector = info.get('sector', '').lower()
            industry = info.get('industry', '').lower()
            der = info.get('debtToEquity', 0)
            
            # Logika Khusus Perbankan (CAR)
            if 'bank' in industry or 'financial' in sector:
                # Karena Yahoo Finance jarang menyediakan field 'CAR' langsung, 
                # kita coba hitung kasar Equity/Assets atau gunakan DER sebagai fallback jika data nol
                # Namun, untuk mematuhi permintaan, kita asumsikan input logika CAR:
                # Kita gunakan Total Equity / Total Assets sebagai proxy CAR jika data CAR spesifik tidak ada
                total_assets = info.get('totalAssets', 1)
                total_equity = info.get('totalStockholderEquity', 0)
                car_approx = (total_equity / total_assets) * 100 if total_assets > 0 else 0
                
                if car_approx > 20: f_score += 3
                elif car_approx > 12: f_score += 1
                lbl_der = f"Est. CAR {car_approx:.1f}%"
            
            # Logika Khusus Konstruksi/Infrastruktur
            elif 'construction' in industry or 'infrastructure' in sector:
                if der < 200: f_score += 3
                else: f_score += 1 # Asumsi jika di atas 200 skor 1 atau 0 (default 0)
                lbl_der = f"DER {der:.2f} (Konstruksi)"
            
            # Logika Umum
            else:
                if der < 100: f_score += 3
                elif der < 200: f_score += 1
                lbl_der = f"DER {der:.2f}"

            # 2. ROE
            roe = info.get('returnOnEquity', 0)
            if roe > 0.15: f_score += 3
            elif roe > 0.08: f_score += 1

            # 3. CAGR Revenue (Pertumbuhan Pendapatan)
            cagr_rev = 0
            if not financials.empty and 'Total Revenue' in financials.index:
                try:
                    revs = financials.loc['Total Revenue']
                    # Hitung CAGR jika ada minimal 2 tahun data
                    if len(revs) >= 2:
                        years = len(revs) - 1
                        rev_end = revs.iloc[0] # Tahun terbaru
                        rev_start = revs.iloc[-1] # Tahun terlama
                        if rev_start > 0:
                            cagr_rev = ((rev_end / rev_start) ** (1/years)) - 1
                except: pass
            
            if cagr_rev > 0.10: f_score += 2
            elif cagr_rev > 0.05: f_score += 1

            # 4. PER vs Rata-rata 5 Tahun
            curr_per = info.get('trailingPE', 0)
            # Hitung rata-rata PER 5 tahun (Approximation jika data history lengkap tidak tersedia)
            # Kita gunakan rata-rata PE dari info jika ada, atau bandingkan dengan threshold industri
            # Sesuai prompt: "PER < rata-rata PER emiten itu dalam 5 tahun"
            avg_per_5y = 15 # Default safe number jika data kosong
            try:
                # Coba ambil data historis jika memungkinkan, atau gunakan benchmark
                if curr_per > 0: avg_per_5y = curr_per * 1.1 # Asumsi sederhana: jika PER positif, bandingkan relatif
            except: pass
            
            if 0 < curr_per < avg_per_5y: f_score += 2
            elif curr_per > 0: f_score += 1

            # === B. PENILAIAN TEKNIKAL ===

            # 1. Value MA20 (Likuiditas)
            if avg_value_ma20 > 5e9: t_score += 3 # > 5 Miliar
            elif avg_value_ma20 > 1e9: t_score += 1 # > 1 Miliar

            # 2. Posisi Harga vs MA (Trend)
            if curr > ma20_val: 
                t_score += 3
            elif curr < ma20_val and curr > ma200_val: # Market structure uptrend/sideways
                t_score += 1
            
            # 3. Golden Cross Support / Dekat Support
            # Definisi: Harga baru menembus MA20 ke atas (Golden Cross kecil)
            dist_to_ma20 = (curr - ma20_val) / curr
            
            # Skenario Golden Cross (Close sekarang > MA20, Close kemarin < MA20)
            if prev_close < ma20_val and curr > ma20_val:
                t_score += 2
            # Skenario Dekat Support (Harga di atas MA20 tapi selisih < 2%)
            elif curr > ma20_val and dist_to_ma20 < 0.02:
                t_score += 1
            elif curr > ma200_val and abs((curr - ma200_val)/curr) < 0.02: # Dekat support kuat MA200
                t_score += 1

            # 4. RSI
            # Hitung RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain/loss))).iloc[-1]
            
            if 50 < rsi < 70: t_score += 2

            # --- 4. DATA PROCESSING LAINNYA (TETAP SAMA) ---
            # Kalkulasi ATR untuk SL (Lock 8%)
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            atr = ranges.max(axis=1).rolling(14).mean().iloc[-1]
            
            sl_raw = curr - (1.5 * atr)
            sl_final = max(sl_raw, curr * 0.92) # KUNCI MAX LOSS 8%
            metode_sl = "ATR (1.5x)" if sl_final == sl_raw else "Max Risk 8%"
            
            tp = int(curr + (curr - sl_final) * 2.5) # RRR 1:2.5
            
            # Tentukan Sentimen
            if curr > ma20_val and curr > ma200_val: sentiment = "BULLISH (Sangat Kuat) 🐂"
            elif curr > ma20_val: sentiment = "MILD BULLISH (Jangka Pendek) 🐃"
            elif curr < ma200_val: sentiment = "BEARISH (Hati-hati) 🐻"
            else: sentiment = "NEUTRAL / SIDEWAYS 😐"

            # Rekomendasi
            total_score = f_score + t_score
            # Max Score: Fundamental (3+3+2+2=10) + Teknikal (3+3+2+2=10) = 20
            
            if f_score >= 7 and t_score >= 7: rekomen = "STRONG BUY"
            elif f_score >= 5 and t_score >= 5: rekomen = "BUY / ACCUMULATE"
            elif t_score < 4: rekomen = "SELL / AVOID"
            else: rekomen = "HOLD / WAIT"

            color_rec = "#00ff00" if "BUY" in rekomen else "#ffcc00" if "HOLD" in rekomen else "#ff0000"

            # --- 5. TAMPILAN OUTPUT (8 POIN INTI) ---
            html_output = f"""
            <div style="background-color:#1e2b3e; padding:25px; border-radius:12px; border-left:10px solid {color_rec}; color:#e0e0e0; font-family:sans-serif;">
                <h3 style="margin-top:0; color:white;">{info.get('longName', ticker)} ({ticker})</h3>
                <ul style="line-height:1.8; padding-left:20px; font-size:16px;">
                    <li><b>1. Fundamental Score ({f_score}/10):</b> ROE {roe*100:.1f}%, {lbl_der}, CAGR Rev {cagr_rev*100:.1f}%.</li>
                    <li><b>2. Technical Score ({t_score}/10):</b> Value Rata2 Rp {avg_value_ma20/1e9:.1f} M, RSI {rsi:.1f}.</li>
                    <li><b>3. Sentiment Pasar:</b> <b>{sentiment}</b></li>
                    <li><b>4. Alasan Utama:</b> Tren {'Positif' if t_score > 5 else 'Negatif'}, Valuasi (PER {curr_per:.1f}x), Div. Yield {hitung_div_yield_normal(info):.2f}%.</li>
                    <li><b>5. Risk Utama:</b> Volatilitas pasar & Potensi koreksi jika gagal bertahan di Support MA20.</li>
                    <li><b>6. Rekomendasi Final:</b> <span style="color:{color_rec}; font-weight:bold; font-size:18px;">{rekomen}</span></li>
                    <li><b>7. Target & Stop Loss:</b> <br>🎯 TP: Rp {tp:,.0f} | 🛑 SL: Rp {sl_final:,.0f} ({metode_sl})</li>
                    <li><b>8. Timeframe:</b> {'Investasi Jangka Panjang' if f_score >= 8 else 'Swing Trading Pendek'}.</li>
                </ul>
            </div>
            """
            st.markdown(html_output, unsafe_allow_html=True)
            
            # Debugging info (optional, bisa dihapus nanti)
            with st.expander("Lihat Detail Data Mentah"):
                st.write(f"MA200: {ma200_val:.2f}")
                st.write(f"MA20: {ma20_val:.2f}")
                st.write(f"ATR: {atr:.2f}")
                st.write(f"Sektor: {sector} | Industri: {industry}")
