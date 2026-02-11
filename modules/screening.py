import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import pytz

def run_screening():
    st.title("🔍 Screening Saham: Top 100 (Safe Strategy)")
    
    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(wib)
    st.info(f"📅 **Waktu Data:** {now.strftime('%d %B %Y - %H:%M')} WIB")
    st.markdown("> **Update:** Kolam diperluas ke 100 saham teraktif dengan strategi *Risk:Reward* ketat.")

    if st.button("Mulai Screening (Proses ±2 Menit)"):
        # 1. DAFTAR TOP 100 (Daftar ini mencakup Bluechip + Second Liner Teraktif)
        saham_top100 = [
            "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BBTN.JK", "BRIS.JK", "ARTO.JK", "BFIN.JK", 
            "BREN.JK", "TPIA.JK", "BRPT.JK", "PGEO.JK", "AMMN.JK", "TLKM.JK", "ISAT.JK", "EXCL.JK", 
            "TOWR.JK", "MTEL.JK", "GOTO.JK", "BUKA.JK", "EMTK.JK", "ADRO.JK", "ANTM.JK", "MDKA.JK", 
            "PTBA.JK", "INCO.JK", "PGAS.JK", "MEDC.JK", "AKRA.JK", "HRUM.JK", "ITMG.JK", "TINS.JK", 
            "MBMA.JK", "ICBP.JK", "INDF.JK", "UNVR.JK", "AMRT.JK", "CPIN.JK", "MYOR.JK", "ACES.JK", 
            "MAPI.JK", "CTRA.JK", "SMRA.JK", "BSDE.JK", "PWON.JK", "PANI.JK", "ASII.JK", "UNTR.JK", 
            "KLBF.JK", "JSMR.JK", "ASSA.JK", "AUTO.JK", "AVIA.JK", "BBYB.JK", "BCIC.JK", "BDMN.JK",
            "BEBS.JK", "BIRD.JK", "BKSL.JK", "BMTR.JK", "BNGA.JK", "BNLI.JK", "BSIM.JK", "BUMI.JK",
            "CPRO.JK", "DMMX.JK", "DOID.JK", "ENRG.JK", "ERAA.JK", "ESSA.JK", "FORU.JK", "HEAL.JK",
            "IMAS.JK", "INKP.JK", "INTP.JK", "JPFA.JK", "KIAS.JK", "LPKR.JK", "LPPF.JK", "LSIP.JK",
            "MAIN.JK", "MAPA.JK", "MIKA.JK", "MLPL.JK", "MNCN.JK", "MPPA.JK", "NATO.JK", "RAJA.JK",
            "SAME.JK", "SCMA.JK", "SIDO.JK", "SILO.JK", "SMGR.JK", "SSMS.JK", "TAPG.JK", "TKIM.JK",
            "TOSL.JK", "TYRE.JK", "WIKA.JK", "WOOD.JK"
        ]

        hasil_lolos = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, ticker in enumerate(saham_top100):
            progress_bar.progress((i + 1) / len(saham_top100))
            status_text.text(f"Menganalisa ({i+1}/100): {ticker}")
            try:
                df = yf.Ticker(ticker).history(period="6mo")
                if len(df) < 55: continue

                curr = df['Close'].iloc[-1]
                vol = df['Volume'].iloc[-1]
                
                # Kalkulasi Indikator
                df['MA20'] = df['Close'].rolling(20).mean()
                df['MA50'] = df['Close'].rolling(50).mean()
                df['VolMA20'] = df['Volume'].rolling(20).mean()

                # Strategi: Titik Entry adalah MA20 + 1% (Sedikit di atas garis agar mudah kena)
                entry_bow = df['MA20'].iloc[-1] * 1.01 
                supp = df['Low'].tail(20).min()
                res = df['High'].tail(20).max()
                
                risk_bow = ((supp - entry_bow) / entry_bow) * 100
                reward_bow = ((res - entry_bow) / entry_bow) * 100
                rr_ratio = reward_bow / abs(risk_bow) if risk_bow != 0 else 0

                # Filter: Uptrend & Transaksi > 5 Miliar
                if curr > 55 and curr > df['MA20'].iloc[-1] > df['MA50'].iloc[-1] and (curr * vol) > 5e9:
                    # Syarat R:R tetap 1.3x demi keamanan Pak Musa
                    if rr_ratio >= 1.3:
                        # Scoring sederhana untuk sorting
                        score = 70 if rr_ratio >= 1.5 else 60
                        
                        hasil_lolos.append({
                            "Ticker": ticker.replace(".JK", ""), 
                            "Harga_Sekarang": int(curr),
                            "Entry_Area": int(entry_bow), 
                            "RR_Ratio": round(rr_ratio, 2),
                            "Confidence": f"{score}%",
                            "Stop_Loss": int(supp), 
                            "Target_Resist": int(res), 
                            "Risk": round(risk_bow, 1), 
                            "Reward": round(reward_bow, 1),
                            "Raw_Score": score
                        })
            except: continue

        progress_bar.empty()
        status_text.empty()

        if hasil_lolos:
            hasil_lolos.sort(key=lambda x: x['Raw_Score'], reverse=True)
            df_final = pd.DataFrame(hasil_lolos)
            st.success(f"Ditemukan {len(hasil_lolos)} saham potensial dari Top 100!")
            st.dataframe(df_final[["Ticker", "Entry_Area", "Harga_Sekarang", "RR_Ratio", "Confidence"]], use_container_width=True)
            
            st.markdown("---")
            for item in hasil_lolos:
                with st.expander(f"Plan: {item['Ticker']} | R:R Ratio: {item['RR_Ratio']}x"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"<div style='text-align:center; padding:10px; border:1px solid #ddd; border-radius:5px;'><small>Antri Beli di</small><br><b style='font-size:1.3em;'>Rp {item['Entry_Area']:,.0f}</b></div>", unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"<div style='background-color:#FF0000; color:white; padding:10px; border-radius:5px; text-align:center;'><b style='font-size:1.3em;'>Rp {item['Stop_Loss']:,.0f}</b><br><small>{item['Risk']}% Risk</small></div>", unsafe_allow_html=True)
                    with c3:
                        st.markdown(f"<div style='background-color:#008000; color:white; padding:10px; border-radius:5px; text-align:center;'><b style='font-size:1.3em;'>Rp {item['Target_Resist']:,.0f}</b><br><small>+{item['Reward']}% Reward</small></div>", unsafe_allow_html=True)
        else: 
            st.warning("Pasar sedang sangat berisiko. Tidak ada dari 100 saham yang memenuhi syarat keamanan Risk:Reward.")
