import streamlit as st
import pandas as pd
import numpy as np
import pytz
from datetime import datetime
from modules.data_loader import get_full_stock_data # MENGGUNAKAN METODE ANTI-ERROR

# --- 1. FUNGSI AUDIO ALERT ---
def play_alert_sound():
    audio_html = """
    <audio autoplay>
      <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
    </audio>
    """
    st.components.v1.html(audio_html, height=0)

# --- 2. FUNGSI INDIKATOR PEMBANTU ---
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

# --- 3. PROGRAM UTAMA ---
def run_screening():
    st.title("🔔 High Prob. Breakout Screener")
    st.markdown("---")

    session, desc = get_market_session()
    st.info(f"**Sesi Saat Ini:** {session} | {desc}")

    if st.button("Mulai Screening (Perlu Waktu +/- 2 menit)"):
        # List Top 100 Saham (Shortened for display)
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
                # --- PAKAI DATA_LOADER (ANTI-ERROR) ---
                data = get_full_stock_data(ticker)
                df = data['history']
                
                if df.empty or len(df) < 30: continue 

                # Filter Likuiditas (> 5 Miliar)
                df['Daily_Value'] = df['Close'] * df['Volume']
                if df['Daily_Value'].rolling(20).mean().iloc[-1] < 5e9: continue 

                curr = df['Close'].iloc[-1]
                avg_vol = df['Volume'].tail(20).mean()
                
                # --- KALKULASI ATR (VOLATILITAS) ---
                high_low = df['High'] - df['Low']
                high_close = np.abs(df['High'] - df['Close'].shift())
                low_close = np.abs(df['Low'] - df['Close'].shift())
                ranges = pd.concat([high_low, high_close, low_close], axis=1)
                true_range = np.max(ranges, axis=1)
                df['ATR'] = true_range.rolling(14).mean()
                atr_val = df['ATR'].iloc[-1]

                # --- SCORING MOMENTUM ---
                score = 0
                reasons = []

                if (df['Volume'].iloc[-1] / avg_vol) > 1.5: score += 20; reasons.append("Vol Spike")
                vwap_val = get_vwap(df).iloc[-1]
                if curr > vwap_val: score += 20; reasons.append("Above VWAP")
                rsi_val = calculate_rsi(df['Close']).iloc[-1]
                if 50 < rsi_val < 70: score += 20; reasons.append(f"RSI {rsi_val:.0f}")
                
                prev_close = df['Close'].iloc[-2]
                chg = ((curr - prev_close)/prev_close)*100
                if chg > 1.5: score += 20; reasons.append(f"Naik {chg:.1f}%")

                # --- PENENTUAN SL & TP MENGGUNAKAN ATR ---
                # Stop Loss = Harga - 1.5x ATR (Lebih responsif dibanding persen statis)
                supp = int(curr - (1.5 * atr_val))
                risk_pct = ((curr - supp) / curr) * 100
                
                # Take Profit = Harga + 3.0x ATR (Memberikan RRR 1:2)
                target_price = int(curr + (3.0 * atr_val))
                reward_pct = ((target_price - curr) / curr) * 100
                
                # Hitung Final RRR
                rrr = reward_pct / risk_pct if risk_pct > 0 else 0

                # --- FILTER FINAL: Score & RRR ---
                if score >= 60 and rrr >= 1.3:
                    if score >= 80: 
                        high_score_found = True
                        rating = "⭐⭐⭐⭐⭐"
                    else:
                        rating = "⭐⭐⭐⭐"

                    hasil_lolos.append({
                        "Ticker": ticker.replace(".JK", ""),
                        "Rating": rating,
                        "Harga": int(curr),
                        "RSI": round(rsi_val, 1),
                        "RRR": f"{rrr:.1f}x",
                        "Reasons": ", ".join(reasons),
                        "Support": supp, 
                        "Resist": target_price,
                        "Risk_Pct": round(risk_pct, 1), 
                        "Reward_Pct": round(reward_pct, 1),
                        "Raw_Score": score
                    })

            except: continue

        progress_bar.empty()
        
        if high_score_found:
            st.warning("⚠️ Sinyal Kuat Terdeteksi!")
            play_alert_sound()

        if hasil_lolos:
            hasil_lolos.sort(key=lambda x: x['Raw_Score'], reverse=True)
            df_final = pd.DataFrame(hasil_lolos)
            
            st.success(f"Ditemukan {len(hasil_lolos)} saham potensial (Sinyal ATR)")
            st.dataframe(df_final[["Ticker", "Rating", "Harga", "RSI", "RRR", "Reward_Pct"]], use_container_width=True)

            st.markdown("---")
            for item in hasil_lolos:
                with st.expander(f"Plan: {item['Ticker']} | Score: {item['Raw_Score']} | RRR: {item['RRR']}"):
                    st.write(f"**Indikator:** {item['Reasons']}")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"<div style='text-align:center;'>Entry<br><b>Rp {item['Harga']:,.0f}</b></div>", unsafe_allow_html=True)
                    with c2:
                        st.markdown(f"<div style='background-color:#ffebee; color:#c62828; padding:10px; border-radius:5px; text-align:center;'><b>SL: Rp {item['Support']:,.0f}</b><br><small>Volatility Gap</small></div>", unsafe_allow_html=True)
                    with c3:
                        st.markdown(f"<div style='background-color:#e8f5e9; color:#2e7d32; padding:10px; border-radius:5px; text-align:center;'><b>TP: Rp {item['Resist']:,.0f}</b><br><small>Target +{item['Reward_Pct']}%</small></div>", unsafe_allow_html=True)
        else:
            st.warning("Belum ada saham yang memenuhi kriteria volatilitas ATR saat ini.")
