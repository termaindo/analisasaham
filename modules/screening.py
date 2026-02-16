import streamlit as st
import pandas as pd
import numpy as np
import pytz
from datetime import datetime
from modules.data_loader import get_full_stock_data # STANDAR ANTI-ERROR
from modules.universe import UNIVERSE_SAHAM, is_syariah # Impor universe dan fungsi syariah

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
    
    # ATR untuk SL (14 Hari)
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    
    # MA 200 (Long-term Trend Filter)
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    return df

def get_market_session():
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    curr_time = now.hour + now.minute/60
    
    if now.weekday() >= 5: 
        return "AKHIR PEKAN", "Pasar Tutup. Menggunakan data penutupan terakhir."
    if curr_time < 9.0: 
        return "PRA-PASAR", "Menunggu pembukaan. Memakai data penutupan kemarin."
    elif 9.0 <= curr_time <= 16.0: 
        return "LIVE MARKET", "Sesi perdagangan berjalan. Memakai data real-time."
    else: 
        return "PASCA-PASAR", "Pasar ditutup. Mendata kandidat untuk besok pagi."

# --- 3. MODUL UTAMA ---
def run_screening():
    st.title("🔔 High Prob. Breakout & Day Trading Screener")
    st.markdown("---")

    session, status_desc = get_market_session()
    st.info(f"**Status Sesi:** {session} | {status_desc}")

    if st.button("Mulai Pemindaian Radar (perlu waktu +/- 2 menit)"):
        
        # Ekstrak semua ticker dari UNIVERSE_SAHAM dan tambahkan '.JK'
        saham_list = []
        for sektor, tickers in UNIVERSE_SAHAM.items():
            for ticker in tickers:
                saham_list.append(f"{ticker}.JK")
        
        # Menghapus duplikasi
        saham_list = list(set(saham_list))

        hasil_lolos = []
        high_score_found = False
        progress_bar = st.progress(0)

        for i, ticker in enumerate(saham_list):
            progress_bar.progress((i + 1) / len(saham_list))
            ticker_bersih = ticker.replace(".JK", "")
            
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

                # --- 2. PENILAIAN KONFIDENSI KETAT (SCORING MAX 100 POIN) ---
                score = 0
                alasan = []

                # A. VWAP Alignment (25 Poin)
                if curr_price > last['VWAP']:
                    score += 25; alasan.append("Above VWAP")
                
                # B. Relative Volume (20 Poin)
                if last['Volume'] > (avg_vol_20 * 1.2): 
                    score += 20; alasan.append("Volume Breakout")

                # C. Harga >= MA200 (15 Poin)
                if pd.notna(last['MA200']) and curr_price >= last['MA200']:
                    score += 15; alasan.append("Uptrend (Above MA200)")
                    
                # D. Value MA20 (10 Poin)
                if avg_val_20 > 5e9:
                    score += 10; alasan.append("Liquid (>5M)")

                # E. Price Action/Gap (10 Poin)
                change_pct = ((curr_price - prev['Close']) / prev['Close']) * 100
                if change_pct > 2.0:
                    score += 10; alasan.append(f"Strong Move +{change_pct:.1f}%")

                # F. EMA 9/21 Cross (10 Poin)
                if last['EMA9'] > last['EMA21']:
                    score += 10; alasan.append("EMA Golden Cross")
                
                # G. RSI Momentum & Trend (10 Poin Total)
                curr_rsi = last['RSI']
                prev_rsi = prev['RSI']
                rsi_trend_icon = "↗️" if curr_rsi > prev_rsi else "↘️"
                
                if curr_rsi > 50:
                    score += 5 
                if curr_rsi > prev_rsi:
                    score += 5 
                
                if curr_rsi > 50 or curr_rsi > prev_rsi:
                    alasan.append("RSI Positif")

                if curr_price > prev['High'] and "Breakout Prev High" not in alasan:
                    alasan.append("Breakout Prev High")

                # --- 3. TRADING PLAN (RENTANG ENTRY & LOCK RISK 8%) ---
                
                # Menentukan Rentang Entry (Support Dinamis)
                dynamic_support = max(last['VWAP'], last['EMA9'])
                
                # Kunci batas bawah penawaran maksimal 3% dari harga saat ini
                batas_bawah_aman = curr_price * 0.97
                entry_bawah = max(dynamic_support, batas_bawah_aman)
                entry_bawah = min(entry_bawah, curr_price) # Pastikan tidak lebih dari harga current
                
                # Stop Loss & Take Profit 
                atr_sl = curr_price - (1.5 * last['ATR'])
                sl_final = max(atr_sl, curr_price * 0.92) # KUNCI MAX LOSS 8%
                
                tp_target = curr_price + (curr_price - sl_final) * 2 # RRR 1:2
                rrr = (tp_target - curr_price) / (curr_price - sl_final) if curr_price > sl_final else 0
                
                risk_pct = ((curr_price - sl_final) / curr_price) * 100
                reward_pct = ((tp_target - curr_price) / curr_price) * 100

                # Panggil fungsi Syariah dari universe.py
                status_syariah = "✅ Ya" if is_syariah(ticker_bersih) else "❌ Tidak"

                # Lolos jika Skor mencukupi (>=60) dan Reward sepadan (RRR >= 1.5)
                if score >= 60 and rrr >= 1.5:
                    conf = "High" if score >= 80 else "Medium"
                    if conf == "High": high_score_found = True
                    
                    hasil_lolos.append({
                        "Ticker": ticker_bersih,
                        "Syariah": status_syariah,
                        "Conf": conf,
                        "Skor": score,
                        "Harga_Curr": int(curr_price),
                        "Entry_Bawah": int(entry_bawah),
                        "Rentang_Entry": f"Rp {int(entry_bawah)} - Rp {int(curr_price)}",
                        "RSI": f"{curr_rsi:.1f} {rsi_trend_icon}", 
                        "RRR": f"{rrr:.1f}x",
                        "Signal": ", ".join(alasan),
                        "Stop Loss": int(sl_final),
                        "Take Profit": int(tp_target),
                        "Risk_Pct": round(risk_pct, 1),      
                        "Reward_Pct": round(reward_pct, 1)
                    })
            except Exception as e: 
                continue

        progress_bar.empty()
        
        if high_score_found:
            st.warning("⚠️ Sinyal High Confidence Ditemukan!")
            play_alert_sound()

        if hasil_lolos:
            hasil_lolos.sort(key=lambda x: x['Skor'], reverse=True)
            df_res = pd.DataFrame(hasil_lolos)
            
            st.success(f"Ditemukan {len(hasil_lolos)} kandidat terbaik.")
            
            # Tampilkan dataframe utama yang rapi
            st.dataframe(
                df_res[["Ticker", "Syariah", "Conf", "Skor", "Rentang_Entry", "RSI", "RRR"]], 
                use_container_width=True,
                hide_index=True
            )

            st.markdown("---")
            st.subheader("Detail Trading Plan")
            
            # Tampilkan rincian per saham di dalam expander
            for item in hasil_lolos:
                with st.expander(f"Strategi: {item['Ticker']} (Skor: {item['Skor']} - {item['Conf']} Confidence)"):
                    st.write(f"**Sinyal Aktif:** {item['Signal']}")
                    st.write(f"**Status Syariah:** {item['Syariah']}")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.info(f"Area Entry\n\n**{item['Rentang_Entry']}**")
                    c2.error(f"Stop Loss\n\n**Rp {item['Stop Loss']} (-{item['Risk_Pct']}%)**")
                    c3.success(f"Take Profit\n\n**Rp {item['Take Profit']} (+{item['Reward_Pct']}%)**")
                    
                    st.caption(f"Risk/Reward Ratio: {item['RRR']} | Disarankan pantau Timeframe 5m/15m. Beli di area bawah rentang entry untuk memaksimalkan RRR.")
        else:
            st.info("Tidak ada saham yang memenuhi kriteria ketat saat ini. Pasar mungkin sedang konsolidasi atau koreksi.")

# Untuk testing secara mandiri jika file ini di-run langsung
if __name__ == "__main__":
    run_screening()
