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

def get_market_session():
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    curr_time = now.hour + now.minute/60
    if now.weekday() >= 5: return "WEEKEND", "Data penutupan Jumat terakhir."
    if curr_time < 9.0: return "PRE_MARKET", "Pasar belum buka."
    elif 9.0 <= curr_time <= 16.0: return "LIVE_MARKET", "Pasar sedang berjalan."
    else: return "POST_MARKET", "Pasar tutup."

def run_screening():
    st.title("🔍 High Prob. Breakout Screener (Min RRR 1.3x)")
    st.markdown("---")

    session, desc = get_market_session()
    st.info(f"**Sesi Saat Ini:** {session} | {desc}")

    if st.button("Cari Saham Potensial"):
        # List Top 100
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
        progress_bar = st.progress(0)

        for i, ticker in enumerate(saham_list):
            progress_bar.progress((i + 1) / len(saham_list))
            try:
                df = yf.Ticker(ticker).history(period="6mo")
                if len(df) < 60: continue # Butuh data lebih panjang untuk resistance

                # Filter Value > 5 Miliar
                df['Daily_Value'] = df['Close'] * df['Volume']
                if df['Daily_Value'].rolling(20).mean().iloc[-1] < 5e9: continue 

                curr = df['Close'].iloc[-1]
                avg_vol = df['Volume'].tail(20).mean()
                
                # --- SCORING MOMENTUM ---
                score = 0
                reasons = []

                if (df['Volume'].iloc[-1] / avg_vol) > 1.5: score += 20; reasons.append("Vol Naik")
                vwap_val = get_vwap(df).iloc[-1]
                if curr > vwap_val: score += 20; reasons.append("Above VWAP")
                
                rsi_val = calculate_rsi(df['Close']).iloc[-1]
                if 50 < rsi_val < 70: score += 20; reasons.append(f"RSI {rsi_val:.0f}")

                # --- PENENTUAN STOP LOSS (RISK) ---
                # Gunakan Swing Low terdekat (3-5 candle terakhir)
                low_5 = df['Low'].tail(5).min()
                raw_risk_pct = ((curr - low_5) / curr) * 100
                
                # Jaga agar Stop Loss Masuk Akal (Min 3%, Max 8%)
                if raw_risk_pct < 2.0: # Jika terlalu dekat, longgarkan sedikit
                    supp = int(curr * 0.97) # Paksa SL -3%
                    risk_pct = 3.0
                elif raw_risk_pct > 8.0: # Jika terlalu jauh, perketat
                    supp = int(curr * 0.92) # Paksa SL -8%
                    risk_pct = 8.0
                    reasons.append("SL Diperketat")
                else:
                    supp = int(low_5)
                    risk_pct = raw_risk_pct

                # --- PENENTUAN TAKE PROFIT (STRATEGI BARU) ---
                # Target Minimal agar RRR >= 1.5
                min_reward_pct = risk_pct * 1.5 
                
                # Cek Resistance Historis (Highest 60 Hari)
                res_hist = df['High'].tail(60).max()
                res_dist_pct = ((res_hist - curr) / curr) * 100

                # LOGIKA CERDAS:
                # Jika resistance historis terlalu dekat (< target minimal),
                # Kita tembak TARGET BREAKOUT (Proyeksi)
                if res_dist_pct < min_reward_pct:
                    target_price = int(curr * (1 + (min_reward_pct / 100)))
                    target_type = "🎯 Breakout Proj."
                    reasons.append("Target Breakout")
                else:
                    target_price = int(res_hist)
                    target_type = "🚧 Swing High"

                # Hitung Final Reward %
                final_reward_pct = ((target_price - curr) / curr) * 100
                rrr = final_reward_pct / risk_pct

                # FILTER FINAL: Score lumayan & RRR harus > 1.3
                if score >= 50 and rrr >= 1.3:
                    hasil_lolos.append({
                        "Ticker": ticker.replace(".JK", ""),
                        "Harga": int(curr),
                        "RSI": round(rsi_val, 1),
                        "RRR": f"{rrr:.1f}x",
                        "Reasons": ", ".join(reasons),
                        "Support": supp, 
                        "Resist": target_price,
                        "Target_Type": target_type,
                        "Risk_Pct": round(risk_pct, 1), 
                        "Reward_Pct": round(final_reward_pct, 1),
                        "Raw_Score": score
                    })

            except: continue

        progress_bar.empty()
        
        if hasil_lolos:
            hasil_lolos.sort(key=lambda x: x['Raw_Score'], reverse=True)
            df_final = pd.DataFrame(hasil_lolos)
            
            # Tampilan Tabel Diperkaya
            st.success(f"Ditemukan {len(hasil_lolos)} saham dengan potensi Risk:Reward > 1.3x")
            st.dataframe(df_final[["Ticker", "Harga", "RSI", "RRR", "Target_Type", "Reward_Pct"]], use_container_width=True)

            st.markdown("---")
            for item in hasil_lolos:
                with st.expander(f"Plan: {item['Ticker']} | RRR: {item['RRR']} | Target: {item['Target_Type']}"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"""<div style='text-align:center; padding:10px; border:1px solid #ddd; border-radius:5px;'>
                            <small>Entry</small><br><b>Rp {item['Harga']:,.0f}</b></div>""", unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"""<div style='background-color:#ffebee; color:#c62828; padding:10px; border-radius:5px; text-align:center;'>
                            <b>SL: Rp {item['Support']:,.0f}</b><br><small>-{item['Risk_Pct']}%</small></div>""", unsafe_allow_html=True)
                    with c3:
                        st.markdown(f"""<div style='background-color:#e8f5e9; color:#2e7d32; padding:10px; border-radius:5px; text-align:center;'>
                            <b>TP: Rp {item['Resist']:,.0f}</b><br><small>+{item['Reward_Pct']}%</small></div>""", unsafe_allow_html=True)
                    st.caption(f"Strategi: {item['Reasons']}")
        else:
            st.warning("Pasar sedang sulit. Tidak ada saham yang memenuhi kriteria RRR > 1.3x saat ini.")
