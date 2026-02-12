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
    if now.weekday() >= 5: return "AKHIR PEKAN", "Pasar Tutup."
    if curr_time < 9.0: return "PRA-PASAR", "Menunggu pembukaan (Jam 09:00)."
    elif 9.0 <= curr_time <= 16.0: return "LIVE MARKET", "Sesi perdagangan berjalan."
    else: return "PASCA-PASAR", "Pasar sudah ditutup."

# --- 3. MODUL UTAMA ---
def run_screening():
    st.title("🔔 High Prob. Breakout & Day Trading Screener")
    st.markdown("---")

    session, status_desc = get_market_session()
    st.info(f"**Status Sesi:** {session} | {status_desc}")

    if st.button("Mulai Pemindaian Radar (VWAP & Breakout Focus)"):
        # List Top 60-80 Saham Teraktif
        saham_list = [
            "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "ASII.JK", "TLKM.JK", "UNTR.JK", "ADRO.JK", 
            "ITMG.JK", "PTBA.JK", "ANTM.JK", "MDKA.JK", "INCO.JK", "GOTO.JK", "BRIS.JK", "BREN.JK",
            "TPIA.JK", "AMMN.JK", "PGAS.JK", "MEDC.JK", "AKRA.JK", "HRUM.JK", "CPIN.JK", "ICBP.JK"
        ] # Daftar dapat diperluas

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

                # --- 1. FILTER LIKUIDITAS (Min Rp 5 Miliar) ---
                if avg_val_20 < 5e9: continue

                # --- 2. PENILAIAN KONFIDENSI (SCORING) ---
                score = 0
                alasan = []

                # Volume Spike
                if last['Volume'] > (avg_vol_20 * 1.5):
                    score += 20; alasan.append("Volume Tinggi (1.5x Avg)")
                
                # Gap Up Detection
                gap_pct = ((last['Open'] - prev['Close']) / prev['Close']) * 100
                if gap_pct > 0.5:
                    score += 20; alasan.append(f"Gap Up {gap_pct:.1f}%")

                # VWAP & EMA Analysis
                if curr_price > last['VWAP']:
                    score += 15; alasan.append("Above VWAP")
                if last['EMA9'] > last['EMA21']:
                    score += 15; alasan.append("EMA 9/21 Golden Cross")
                if last['RSI'] > 50:
                    score += 10; alasan.append("RSI Momentum > 50")
                
                # Breakout Yesterday's High
                if curr_price > prev['High']:
                    score += 20; alasan.append("Breakout High Kemarin")

                # --- 3. TRADING PLAN & LOCK RISK 8% ---
                atr_sl = curr_price - (1.5 * last['ATR'])
                sl_final = max(atr_sl, curr_price * 0.92) # KUNCI MAX LOSS 8%
                
                tp_target = curr_price + (curr_price - sl_final) * 2 # RRR 1:2
                rrr = (tp_target - curr_price) / (curr_price - sl_final) if curr_price > sl_final else 0

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
                    c2.error(f"Stop Loss\n\nRp {item['Stop Loss']}")
                    c3.success(f"Take Profit\n\nRp {item['Take Profit']}")
                    st.caption(f"Risk/Reward: {item['RRR']} | Timeframe: 15m/60m Swing")
