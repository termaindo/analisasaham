import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import pytz

# 1. FUNGSI INDIKATOR
def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_vwap(df):
    return (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()

def play_alert_sound():
    audio_html = """
    <audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>
    """
    st.components.v1.html(audio_html, height=0)

def get_market_session():
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    curr_time = now.hour + now.minute/60
    if now.weekday() >= 5: return "WEEKEND", "Data penutupan Jumat terakhir."
    if curr_time < 9.0: return "PRE_MARKET", "Pasar belum buka."
    elif 9.0 <= curr_time <= 16.0: return "LIVE_MARKET", "Pasar sedang berjalan."
    else: return "POST_MARKET", "Pasar tutup."

def run_screening():
    st.title("🔍 Daily Momentum Screener Pro")
    st.markdown("---")

    session, desc = get_market_session()
    st.info(f"**Sesi Saat Ini:** {session} | {desc}")

    if st.button("Mulai Screening Momentum (Top 100)"):
        # List saham tetap sama (Top 100)
        saham_list = [
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
        high_score_found = False
        progress_bar = st.progress(0)

        for i, ticker in enumerate(saham_list):
            progress_bar.progress((i + 1) / len(saham_list))
            try:
                df = yf.Ticker(ticker).history(period="6mo")
                if len(df) < 30: continue

                # --- HITUNG VALUE MA20 (USULAN PAK MUSA) ---
                df['Daily_Value'] = df['Close'] * df['Volume']
                value_ma20 = df['Daily_Value'].rolling(window=20).mean().iloc[-1]
                
                # FILTER UTAMA: Hanya proses jika rata-rata transaksi > 5 Miliar
                if value_ma20 < 5e9: continue 

                curr = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2]
                avg_vol = df['Volume'].tail(20).mean()
                
                # --- SISTEM SCORING ---
                score = 0
                reasons = []

                if (df['Volume'].iloc[-1] / avg_vol) > 2.0: score += 30; reasons.append("Vol Spike")
                elif (df['Volume'].iloc[-1] / avg_vol) > 1.2: score += 15; reasons.append("High Vol")

                vwap_val = get_vwap(df).iloc[-1]
                if curr > vwap_val: score += 20; reasons.append("Above VWAP")

                rsi_val = calculate_rsi(df['Close']).iloc[-1]
                if 50 < rsi_val < 70: score += 20; reasons.append(f"RSI {rsi_val:.0f}")

                df['EMA9'] = df['Close'].ewm(span=9).mean()
                df['EMA21'] = df['Close'].ewm(span=21).mean()
                if df['EMA9'].iloc[-1] > df['EMA21'].iloc[-1]: score += 20; reasons.append("EMA Cross")

                chg = ((curr - prev) / prev) * 100
                if chg > 2: score += 10; reasons.append(f"+{chg:.1f}%")

                # --- PERHITUNGAN RRR ---
                supp = df['Low'].tail(20).min()
                res = df['High'].tail(20).max()
                risk_pct = ((supp - curr) / curr) * 100
                reward_pct = ((res - curr) / curr) * 100
                rrr = abs(reward_pct / risk_pct) if risk_pct != 0 else 0

                if score >= 60:
                    if score >= 90: high_score_found = True
                    hasil_lolos.append({
                        "Ticker": ticker.replace(".JK", ""),
                        "Rating": "⭐⭐⭐⭐⭐" if score >= 85 else "⭐⭐⭐⭐",
                        "Harga": int(curr),
                        "RSI": round(rsi_val, 1),
                        "Confidence": f"{score}%",
                        "RRR": f"{rrr:.1f}x",
                        "Value_Avg": round(value_ma20 / 1e9, 1),
                        "Reasons": ", ".join(reasons),
                        "Support": int(supp), "Resist": int(res),
                        "Risk_Pct": round(risk_pct, 1), "Reward_Pct": round(reward_pct, 1),
                        "Raw_Score": score
                    })
            except: continue

        progress_bar.empty()
        
        if high_score_found:
            st.warning("⚠️ Sinyal Momentum Sangat Kuat Terdeteksi (Score > 90%)!")
            play_alert_sound()

        if hasil_lolos:
            hasil_lolos.sort(key=lambda x: x['Raw_Score'], reverse=True)
            df_final = pd.DataFrame(hasil_lolos)
            
            # Tampilkan Rata-rata Value di tabel agar Bapak bisa memantau likuiditasnya
            st.dataframe(df_final[["Ticker", "Rating", "Harga", "RSI", "Confidence", "RRR", "Value_Avg"]], use_container_width=True)

            st.markdown("---")
            for item in hasil_lolos:
                with st.expander(f"Plan: {item['Ticker']} | RRR: {item['RRR']} | Avg Value: {item['Value_Avg']}M"):
                    st.write(f"**Analisa:** {item['Reasons']}")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"""<div style='text-align:center; padding:10px; border:1px solid #ddd; border-radius:5px;'>
                            <small style='color:gray;'>Entry Price</small><br><b style='font-size:1.3em;'>Rp {item['Harga']:,.0f}</b></div>""", unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"""<div style='background-color:#FF0000; color:white; padding:10px; border-radius:5px; text-align:center;'>
                            <span style='font-size:1.5em; font-weight:bold;'>Rp {item['Support']:,.0f}</span><br><small>{item['Risk_Pct']}% Risk</small></div>""", unsafe_allow_html=True)
                    with c3:
                        st.markdown(f"""<div style='background-color:#008000; color:white; padding:10px; border-radius:5px; text-align:center;'>
                            <span style='font-size:1.5em; font-weight:bold;'>Rp {item['Resist']:,.0f}</span><br><small>+{item['Reward_Pct']}% Reward</small></div>""", unsafe_allow_html=True)
        else:
            st.warning("Tidak ada saham likuid (Avg > 5M) dengan momentum kuat saat ini.")
