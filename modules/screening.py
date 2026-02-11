import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import pytz

def run_screening():
    st.title("🔍 Screening Saham Harian")
    st.markdown("---")

    # 1. SINKRONISASI WAKTU
    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(wib)
    jam_sekarang = now.strftime('%H:%M')
    tanggal_sekarang = now.strftime('%d %B %Y')

    if now.hour < 16:
        sesi_pasar = "LIVE MARKET (Fokus: Volatilitas Intraday)"
    else:
        sesi_pasar = "POST MARKET (Fokus: Analisa Penutupan)"

    st.info(f"""
    **📅 Waktu Data:** {tanggal_sekarang} - {jam_sekarang} WIB
    **🛒 Fokus:** {sesi_pasar}
    """)

    # 2. DAFTAR TOP 50 SAHAM
    saham_top50 = [
        "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BBTN.JK", "BRIS.JK", "ARTO.JK", "BFIN.JK", 
        "BREN.JK", "TPIA.JK", "BRPT.JK", "PGEO.JK", "AMMN.JK", "TLKM.JK", "ISAT.JK", "EXCL.JK", 
        "TOWR.JK", "MTEL.JK", "GOTO.JK", "BUKA.JK", "EMTK.JK", "ADRO.JK", "ANTM.JK", "MDKA.JK", 
        "PTBA.JK", "INCO.JK", "PGAS.JK", "MEDC.JK", "AKRA.JK", "HRUM.JK", "ITMG.JK", "TINS.JK", 
        "MBMA.JK", "ICBP.JK", "INDF.JK", "UNVR.JK", "AMRT.JK", "CPIN.JK", "MYOR.JK", "ACES.JK", 
        "MAPI.JK", "CTRA.JK", "SMRA.JK", "BSDE.JK", "PWON.JK", "PANI.JK", "ASII.JK", "UNTR.JK", 
        "KLBF.JK", "JSMR.JK"
    ]

    if st.button("Mulai Screening (Proses ±60 Detik)"):
        hasil_lolos = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_saham = len(saham_top50)

        for i, ticker in enumerate(saham_top50):
            progress_bar.progress((i + 1) / total_saham)
            status_text.text(f"Menganalisa ({i+1}/{total_saham}): {ticker}...")

            try:
                # Ambil data 6 bulan untuk perhitungan MACD & RSI yang aman
                df = yf.Ticker(ticker).history(period="6mo")
                if len(df) < 55: continue

                # Identifikasi Data Terkini
                curr = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2]
                vol = df['Volume'].iloc[-1]
                
                # --- KALKULASI INDIKATOR ---
                # 1. Moving Average
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['MA50'] = df['Close'].rolling(window=50).mean()
                df['VolMA20'] = df['Volume'].rolling(window=20).mean()

                # 2. RSI (14)
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                curr_rsi = (100 - (100 / (1 + rs))).iloc[-1]

                # 3. MACD
                exp12 = df['Close'].ewm(span=12, adjust=False).mean()
                exp26 = df['Close'].ewm(span=26, adjust=False).mean()
                macd_line = exp12 - exp26
                signal_line = macd_line.ewm(span=9, adjust=False).mean()

                # 4. Risk / Reward (20 Days Support/Resist)
                supp = df['Low'].tail(20).min()
                res = df['High'].tail(20).max()
                risk = ((supp - curr) / curr) * 100
                reward = ((res - curr) / curr) * 100

                # --- KRITERIA SCREENER DASAR ---
                cond1 = curr > 55
                cond2 = (curr > df['MA20'].iloc[-1]) and (df['MA20'].iloc[-1] > df['MA50'].iloc[-1])
                cond3 = (curr * vol) > 5_000_000_000 # Value > 5 Miliar
                cond4 = vol > df['VolMA20'].iloc[-1] # Volume Spike

                if cond1 and cond2 and cond3 and cond4:
                    # --- SISTEM SCORING ---
                    score = 40 # Base score lolos filter trend
                    
                    if vol > df['VolMA20'].iloc[-1]: score += 15
                    if macd_line.iloc[-1] > signal_line.iloc[-1]: score += 15
                    
                    if 50 <= curr_rsi <= 68: score += 15
                    elif curr_rsi > 75: score -= 10 # Penalti Overbought
                    
                    if reward > (abs(risk) * 1.5): score += 15

                    # --- FILTER MINIMAL SKOR 70 ---
                    if score >= 70:
                        if score >= 85: 
                            label = "⭐⭐⭐⭐⭐ (Sangat Kuat)"
                        else: 
                            label = "⭐⭐⭐⭐ (Kuat)"

                        hasil_lolos.append({
                            "Ticker": ticker.replace(".JK", ""),
                            "Harga": int(curr),
                            "Chg (%)": round(((curr-prev)/prev)*100, 2),
                            "RSI": round(curr_rsi, 1),
                            "Confidence": f"{score}%",
                            "Rating": label,
                            "Value (M)": round((curr * vol) / 1e9, 1),
                            "Support": supp,
                            "Resist": res,
                            "Risk_Pct": round(risk, 2),
                            "Reward_Pct": round(reward, 2),
                            "Raw_Score": score
                        })
            except Exception:
                continue

        progress_bar.empty()
        status_text.empty()

        # 3. TAMPILKAN LAPORAN
        if hasil_lolos:
            # Urutkan berdasarkan Skor tertinggi
            hasil_lolos.sort(key=lambda x: x['Raw_Score'], reverse=True)
            df_hasil = pd.DataFrame(hasil_lolos)

            st.success(f"Ditemukan {len(hasil_lolos)} saham potensial dengan rating Kuat ke atas!")
            
            # Tabel Utama (Menjawab keluhan Bapak sebelumnya agar RSI muncul)
            st.dataframe(
                df_hasil[["Ticker", "Rating", "Harga", "Chg (%)", "RSI", "Confidence", "Value (M)"]], 
                use_container_width=True
            )

            st.markdown("---")
            st.subheader("📊 Analisa Detail & Trading Plan")

            for item in hasil_lolos:
                with st.expander(f"Detail: {item['Ticker']} | {item['Rating']} | Score: {item['Confidence']}"):
                    # Analisa Teks
                    rsi_status = "momentum kuat" if item['RSI'] > 50 else "pemulihan trend"
                    st.write(f"**Analisa:** Saham {item['Ticker']} dalam kondisi {item['Rating']}. RSI berada di angka {item['RSI']} yang menunjukkan {rsi_status}.")
                    
                    # Trading Plan
                    c1, c2, c3 = st.
