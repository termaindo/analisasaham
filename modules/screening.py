import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import pytz

def run_screening():
    st.title("🔍 Screening Saham: Safe Strategy (R:R 1.3x)")
    
    # 1. SINKRONISASI WAKTU
    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(wib)
    jam_sekarang = now.strftime('%H:%M')
    tanggal_sekarang = now.strftime('%d %B %Y')
    sesi_pasar = "LIVE MARKET" if now.hour < 16 else "POST MARKET"

    st.info(f"📅 **Waktu Data:** {tanggal_sekarang} - {jam_sekarang} WIB | **Fokus:** {sesi_pasar}")
    st.markdown("> **Strategi:** Hanya menampilkan saham dengan *Reward* minimal **1.3x** dari *Risk* menggunakan titik *Entry* di MA20 (Buy on Weakness).")

    if st.button("Mulai Screening (Proses ±60 Detik)"):
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

                # LOGIKA BUY ON WEAKNESS (ENTRY DI MA20)
                entry_bow = df['MA20'].iloc[-1]
                supp = df['Low'].tail(20).min()
                res = df['High'].tail(20).max()
                
                # Hitung Risk/Reward berdasarkan harga BoW (bukan harga sekarang)
                risk_bow = ((supp - entry_bow) / entry_bow) * 100
                reward_bow = ((res - entry_bow) / entry_bow) * 100
                rr_ratio = reward_bow / abs(risk_bow) if risk_bow != 0 else 0

                # Filter Dasar & Syarat Ketat R:R >= 1.3
                if curr > 55 and curr > df['MA20'].iloc[-1] > df['MA50'].iloc[-1] and (curr * vol) > 5e9:
                    if rr_ratio >= 1.3:
                        # Scoring System
                        score = 40
                        if vol > df['VolMA20'].iloc[-1]: score += 15
                        if macd.iloc[-1] > signal.iloc[-1]: score += 15
                        if 50 <= curr_rsi <= 68: score += 15
                        elif curr_rsi > 75: score -= 10
                        if rr_ratio >= 2.0: score += 15

                        label = "⭐⭐⭐⭐⭐ (Sangat Layak)" if score >= 85 else "⭐⭐⭐⭐ (Layak)"
                        
                        hasil_lolos.append({
                            "Ticker": ticker.replace(".JK", ""), "Harga_Now": int(curr),
                            "Entry_BoW": int(entry_bow), "RSI": round(curr_rsi, 1),
                            "Confidence": f"{score}%", "Rating": label,
                            "Value (M)": round((curr * vol) / 1e9, 1), "Stop_Loss": supp, 
                            "Target": res, "Risk_Pct": round(risk_bow, 2), 
                            "Reward_Pct": round(reward_bow, 2), "RR_Ratio": round(rr_ratio, 2),
                            "Raw_Score": score
                        })
            except: continue

        progress_bar.empty()
        if hasil_lolos:
            hasil_lolos.sort(key=lambda x: x['Raw_Score'], reverse=True)
            df_final = pd.DataFrame(hasil_lolos)
            st.success(f"Ditemukan {len(hasil_lolos)} saham dengan Rasio Risk:Reward sehat (min 1.3x)!")
            st.dataframe(df_final[["Ticker", "Rating", "Entry_BoW", "Harga_Now", "RR_Ratio", "Confidence"]], use_container_width=True)
            
            st.markdown("---")
            st.subheader("📊 Strategi Buy on Weakness (BoW)")
            for item in hasil_lolos:
                with st.expander(f"Plan: {item['Ticker']} | R:R Ratio: {item['RR_Ratio']}x"):
                    st.write(f"**Analisa:** Saham {item['Ticker']} sedang uptrend. Jangan kejar harga atas (**Rp {item['Harga_Now']:,.0f}**). Tunggu harga melemah ke area **Entry BoW** agar risiko terjaga.")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"""
                        <div style='text-align: center; padding: 10px; border: 1px solid #ddd; border-radius: 5px;'>
                            <span style='font-size: 0.8em; color: gray;'>Antri Beli di (BoW)</span><br>
                            <span style='font-size: 1.3em; font-weight: bold;'>Rp {item['Entry_BoW']:,.0f}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with c2:
                        st.markdown(f"""
                        <div style='background-color: #FF0000; color: white; padding: 10px; border-radius: 5px; text-align: center;'>
                            <span style='font-size: 1.5em; font-weight: bold;'>Rp {item['Stop_Loss']:,.0f}</span><br>
                            <span style='font-size: 0.9em; opacity: 0.9;'>Stop Loss ({item['Risk_Pct']}% Risk)</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with c3:
                        st.markdown(f"""
                        <div style='background-color: #008000; color: white; padding: 10px; border-radius: 5px; text-align: center;'>
                            <span style='font-size: 1.5em; font-weight: bold;'>Rp {item['Target']:,.0f}</span><br>
                            <span style='font-size: 0.9em; opacity: 0.9;'>Take Profit (+{item['Reward_Pct']}% Reward)</span>
                        </div>
                        """, unsafe_allow_html=True)
        else: 
            st.warning("Tidak ada saham dengan rasio R:R sehat (1.3x) hari ini. Lebih baik 'Wait and See' atau tunggu harga terkoreksi ke MA20.")
