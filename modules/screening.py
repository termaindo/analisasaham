import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import pytz

def run_screening():
    st.title("🔍 Screening Saham Harian")
    
    # 1. SINKRONISASI WAKTU
    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(wib)
    jam_sekarang = now.strftime('%H:%M')
    tanggal_sekarang = now.strftime('%d %B %Y')
    sesi_pasar = "LIVE MARKET (Fokus: Intraday)" if now.hour < 16 else "POST MARKET (Fokus: Penutupan)"

    st.info(f"📅 **Waktu Data:** {tanggal_sekarang} - {jam_sekarang} WIB | **Fokus:** {sesi_pasar}")

    if st.button("Mulai Screening (Proses ±60 Detik)"):
        # 2. DAFTAR TOP 50 (Sesuai List Terakhir)
        saham_top50 = [
            "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BBTN.JK", "BRIS.JK", "ARTO.JK", "BFIN.JK", 
            "BREN.JK", "TPIA.JK", "BRPT.JK", "PGEO.JK", "AMMN.JK", "TLKM.JK", "ISAT.JK", "EXCL.JK", 
            "TOWR.JK", "MTEL.JK", "GOTO.JK", "BUKA.JK", "EMTK.JK", "ADRO.JK", "ANTM.JK", "MDKA.JK", 
            "PTBA.JK", "INCO.JK", "PGAS.JK", "MEDC.JK", "AKRA.JK", "HRUM.JK", "ITMG.JK", "TINS.JK", 
            "MBMA.JK", "ICBP.JK", "INDF.JK", "UNVR.JK", "AMRT.JK", "CPIN.JK", "MYOR.JK", "ACES.JK", 
            "MAPI.JK", "CTRA.JK", "SMRA.JK", "BSDE.JK", "PWON.JK", "PANI.JK", "ASII.JK", "UNTR.JK", 
            "KLBF.JK", "JSMR.JK"
        ]

        hasil_lolos = []
        progress_bar = st.progress(0)
        
        for i, ticker in enumerate(saham_top50):
            progress_bar.progress((i + 1) / len(saham_top50))
            try:
                df = yf.Ticker(ticker).history(period="6mo")
                if len(df) < 55: continue

                curr = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2]
                vol = df['Volume'].iloc[-1]
                
                # Kalkulasi Indikator
                df['MA20'] = df['Close'].rolling(20).mean()
                df['MA50'] = df['Close'].rolling(50).mean()
                df['VolMA20'] = df['Volume'].rolling(20).mean()

                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                curr_rsi = (100 - (100 / (1 + (gain/loss)))).iloc[-1]

                exp12 = df['Close'].ewm(span=12, adjust=False).mean()
                exp26 = df['Close'].ewm(span=26, adjust=False).mean()
                macd = exp12 - exp26
                signal = macd.ewm(span=9, adjust=False).mean()

                supp = df['Low'].tail(20).min()
                res = df['High'].tail(20).max()
                risk = ((supp - curr) / curr) * 100
                reward = ((res - curr) / curr) * 100

                # Filter Dasar & Scoring (Sesuai Permintaan)
                if curr > 55 and curr > df['MA20'].iloc[-1] > df['MA50'].iloc[-1] and (curr * vol) > 5e9:
                    score = 40
                    if vol > df['VolMA20'].iloc[-1]: score += 15
                    if macd.iloc[-1] > signal.iloc[-1]: score += 15
                    if 50 <= curr_rsi <= 68: score += 15
                    elif curr_rsi > 75: score -= 10
                    if reward > (abs(risk) * 1.5): score += 15

                    if score >= 70:
                        label = "⭐⭐⭐⭐⭐ (Sangat Kuat)" if score >= 85 else "⭐⭐⭐⭐ (Kuat)"
                        hasil_lolos.append({
                            "Ticker": ticker.replace(".JK", ""), "Harga": int(curr),
                            "Chg (%)": round(((curr-prev)/prev)*100, 2), "RSI": round(curr_rsi, 1),
                            "Confidence": f"{score}%", "Rating": label,
                            "Value (M)": round((curr * vol) / 1e9, 1), "Support": supp, 
                            "Resist": res, "Risk_Pct": round(risk, 2), 
                            "Reward_Pct": round(reward, 2), "Raw_Score": score
                        })
            except: continue

        progress_bar.empty()
        if hasil_lolos:
            hasil_lolos.sort(key=lambda x: x['Raw_Score'], reverse=True)
            df_final = pd.DataFrame(hasil_lolos)
            st.success(f"Ditemukan {len(hasil_lolos)} saham potensial!")
            st.dataframe(df_final[["Ticker", "Rating", "Harga", "Chg (%)", "RSI", "Confidence", "Value (M)"]], use_container_width=True)
            
            st.markdown("---")
            st.subheader("📊 Analisa Detail & Trading Plan")
            
            for item in hasil_lolos:
                with st.expander(f"Detail: {item['Ticker']} | Score: {item['Confidence']}"):
                    st.write(f"**Analisa:** Saham {item['Ticker']} dalam kondisi {item['Rating']}. RSI {item['RSI']} ({'momentum kuat' if item['RSI'] > 50 else 'pemulihan'}).")
                    
                    # --- Tampilan Trading Plan Baru ---
                    c1, c2, c3 = st.columns(3)
                    
                    with c1:
                        # Entry dengan harga lebih kecil sedikit
                        st.markdown(f"""
                            <div style='text-align:center; padding:10px; border:1px solid #ddd; border-radius:5px;'>
                                <small style='color:grey;'>Entry Price</small><br>
                                <b style='font-size:1.1em;'>Rp {item['Harga']:,.0f}</b>
                            </div>
                        """, unsafe_allow_html=True)
                    
                    with c2:
                        # Stop Loss (Risk) Background Merah, Tulisan Putih, Font Besar
                        st.markdown(f"""
                            <div style='background-color:#ff4b4b; color:white; padding:10px; border-radius:5px; text-align:center;'>
                                <small style='font-size:0.8em; opacity:0.9;'>Stop Loss (Price: Rp {item['Support']:,.0f})</small><br>
                                <b style='font-size:1.4em;'>{item['Risk_Pct']}% Risk</b>
                            </div>
                        """, unsafe_allow_html=True)
                        
                    with c3:
                        # Take Profit (Reward) Background Hijau, Tulisan Putih, Font Besar
                        st.markdown(f"""
                            <div style='background-color:#28a745; color:white; padding:10px; border-radius:5px; text-align:center;'>
                                <small style='font-size:0.8em; opacity:0.9;'>Take Profit (Price: Rp {item['Resist']:,.0f})</small><br>
                                <b style='font-size:1.4em;'>+{item['Reward_Pct']}% Reward</b>
                            </div>
                        """, unsafe_allow_html=True)
        else: st.warning("Tidak ada saham terjaring skor > 70 hari ini.")
