import streamlit as st
import pandas as pd
import numpy as np
import pytz
from datetime import datetime
from modules.data_loader import get_full_stock_data # STANDAR ANTI-ERROR

# --- 1. FUNGSI AUDIO ALERT ---
def play_alert_sound():
    """Bunyikan lonceng untuk High Confidence Signal"""
    audio_html = """
    <audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>
    """
    st.components.v1.html(audio_html, height=0)

# --- 2. INDIKATOR DAY TRADING ---
def calculate_day_indicators(df):
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    # EMA 9 & 21 (Momentum Crossover)
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    
    # VWAP (Volume Weighted Average Price)
    df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    
    # ATR untuk SL
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    
    return df

def get_market_session():
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    curr_time = now.hour + now.minute/60
    if now.weekday() >= 5: return "AKHIR PEKAN", "Pasar Tutup. Menggunakan data penutupan terakhir."
    if curr_time < 9.0: return "PRA-PASAR", "Menunggu pembukaan. Memakai data penutupan kemarin."
    elif 9.0 <= curr_time <= 16.0: return "LIVE MARKET", "Sesi perdagangan berjalan. Memakai data real-time."
    else: return "PASCA-PASAR", "Pasar ditutup. Mendata kandidat untuk besok pagi."

# --- 3. MODUL UTAMA ---
def run_screening():
    st.title("🔔 High Prob. Breakout & Day Trading Screener")
    st.markdown("---")

    session, status_desc = get_market_session()
    st.info(f"**Status Sesi:** {session} | {status_desc}")

    if st.button("Mulai Pemindaian Radar (perlu waktu +/- 2 menit)"):
        # List Top 100 Saham Teraktif (Bisa disesuaikan)
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
                data = get_full_stock_data(ticker)
                df = data['history']
                if df.empty or len(df) < 30: continue

                df = calculate_day_indicators(df)
                last = df.iloc[-1]
                prev = df.iloc[-2]
                
                curr_price = last['Close']
                avg_val_20 = (df['Close'] * df['Volume']).rolling(20).mean().iloc[-1]
                avg_vol_20 = df['Volume'].rolling(20).mean().iloc[-1]

                # --- 1. FILTER LIKUIDITAS UTAMA (Min Rp 1 Miliar) ---
                if avg_val_20 < 1e9: continue

                # --- 2. PENILAIAN KONFIDENSI (SCORING MAX 100 POIN) ---
                score = 0
                alasan = []

                # A. Relative Volume (20 Poin): Volume meningkat
                if last['Volume'] > (avg_vol_20 * 1.2): # Filter volume naik >20%
                    score += 20; alasan.append("Volume Breakout")
                
                # B. VWAP Alignment (20 Poin): Harga di atas VWAP
                if curr_price > last['VWAP']:
                    score += 20; alasan.append("Above VWAP")
                
                # C. RSI Momentum (20 Poin): Rentang 50 - 70
                if 50 <= last['RSI'] <= 70:
                    score += 20; alasan.append(f"RSI Ideal ({last['RSI']:.0f})")
                    
                # D. EMA 9/21 Cross (20 Poin): Tren jangka pendek bullish
                if last['EMA9'] > last['EMA21']:
                    score += 20; alasan.append("EMA Golden Cross")
                    
                # E. Price Action/Gap (10 Poin): Kenaikan > 2%
                change_pct = ((curr_price - prev['Close']) / prev['Close']) * 100
                if change_pct > 2.0:
                    score += 10; alasan.append(f"Strong Move +{change_pct:.1f}%")
                    
                # F. Value MA20 (10 Poin): Transaksi > Rp 5 Miliar
                if avg_val_20 > 5e9:
                    score += 10; alasan.append("High Liquidity (>5M)")

                # Filter tambahan: Breakout Yesterday's High (Syarat Opsional masuk Watchlist)
                if curr_price > prev['High'] and "Breakout High" not in alasan:
                    alasan.append("Breakout Prev High")

                # --- 3. TRADING PLAN & LOCK RISK 8% ---
                atr_sl = curr_price - (1.5 * last['ATR'])
                sl_final = max(atr_sl, curr_price * 0.92) # KUNCI MAX LOSS 8%
                
                tp_target = curr_price + (curr_price - sl_final) * 2 # RRR 1:2
                rrr = (tp_target - curr_price) / (curr_price - sl_final) if curr_price > sl_final else 0
                
                # --- HITUNG % RISK DAN REWARD ---
                risk_pct = ((curr_price - sl_final) / curr_price) * 100
                reward_pct = ((tp_target - curr_price) / curr_price) * 100

                # Lolos jika Skor mencukupi dan Reward sepadan
                if score >= 60 and rrr >= 1.5:
                    conf = "High" if score >= 80 else "Medium"
                    if conf == "High": high_score_found = True
                    
                    hasil_lolos.append({
                        "Ticker": ticker.replace(".JK", ""),
                        "Conf": conf,
                        "Harga": int(curr_price),
                        "RSI": round(last['RSI'], 1),
                        "RRR": f"{rrr:.1f}x",
                        "Signal": ", ".join(alasan),
                        "Stop Loss": int(sl_final),
                        "Take Profit": int(tp_target),
                        "Risk_Pct": round(risk_pct, 1),      
                        "Reward_Pct": round(reward_pct, 1), 
                        "Skor": score
                    })
            except: continue

        progress_bar.empty()
        if high_score_found:
            st.warning("⚠️ Sinyal High Confidence Ditemukan!")
            play_alert_sound()

        if hasil_lolos:
            hasil_lolos.sort(key=lambda x: x['Skor'], reverse=True)
            df_res = pd.DataFrame(hasil_lolos)
            
            st.success(f"Ditemukan {len(hasil_lolos)} kandidat terbaik.")
            st.dataframe(df_res[["Ticker", "Conf", "Harga", "RSI", "RRR", "Signal"]], use_container_width=True)

            st.markdown("---")
            for item in hasil_lolos:
                with st.expander(f"Strategi: {item['Ticker']} (Skor: {item['Skor']})"):
                    st.write(f"**Indikator:** {item['Signal']}")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Entry", f"Rp {item['Harga']}")
                    c2.error(f"Stop Loss\n\nRp {item['Stop Loss']} (-{item['Risk_Pct']}%)")
                    c3.success(f"Take Profit\n\nRp {item['Take Profit']} (+{item['Reward_Pct']}%)")
                    st.caption(f"Risk/Reward: {item['RRR']} | Disarankan pantau Timeframe 5m/15m")
