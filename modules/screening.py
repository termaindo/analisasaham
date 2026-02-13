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

    if st.button("Mulai Pemindaian Radar (perlu waktu +/- 2 menit)"):
        # List Top 100 Saham Teraktif
        saham_list = [
            "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BBTN.JK", "BRIS.JK", "ARTO.JK", "BFIN.JK", 
            "BREN.JK", "TPIA.JK", "BRPT.JK", "PGEO.JK", "AMMN.JK", "TLKM.JK", "ISAT.JK", "EXCL.JK", 
            "TOWR.JK", "MTEL.JK", "GOTO.JK", "BUKA.JK", "EMTK.JK", "ADRO.JK",
