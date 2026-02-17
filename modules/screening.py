import streamlit as st
import pandas as pd
import numpy as np
import pytz
from datetime import datetime
from modules.data_loader import get_full_stock_data 
from modules.universe import UNIVERSE_SAHAM, is_syariah, get_sector_data # Ditambahkan get_sector_data

# --- 1. FUNGSI AUDIO ALERT ---
def play_alert_sound():
    """Bunyikan lonceng untuk High Confidence Signal"""
    audio_html = """
    <audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>
    """
    st.components.v1.html(audio_html, height=0)

# --- 2. INDIKATOR TEKNIKAL ---
def calculate_indicators(df, trade_mode):
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    # EMA
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    # ATR untuk SL
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    
    # Indikator Spesifik Mode
    if trade_mode == "Day Trading":
        df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()
    else:
        df['MA50'] = df['Close'].rolling(window=50).mean()
    
    return df

def get_market_session():
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    curr_time = now.hour + now.minute/60
    if now.weekday() >= 5: return "AKHIR PEKAN", "Pasar Tutup."
    if curr_time < 9.0: return "PRA-PASAR", "Data penutupan kemarin."
    elif 9.0 <= curr_time <= 16.0: return "LIVE MARKET", "Data Real-Time."
    else: return "PASCA-PASAR", "Persiapan besok."

# --- 3. MODUL UTAMA ---
def run_screening():
    st.title("🔔 Expert Stock Pro: Multi-Mode Screener")
    st.markdown("---")

    trade_mode = st.radio("Pilih Strategi Trading:", ["Day Trading", "Swing Trading"], horizontal=True)
    
    session, status_desc = get_market_session()
    st.info(f"**Mode:** {trade_mode} | **Sesi:** {session} ({status_desc})")

    if st.button(f"Mulai Scan {trade_mode}"):
        saham_list = []
        for sektor, tickers in UNIVERSE_SAHAM.items():
            for ticker in tickers:
                saham_list.append(f"{ticker}.JK")
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
                if df.empty or len(df) < 200: continue

                df = calculate_indicators(df, trade_mode)
                last = df.iloc[-1]
                prev = df.iloc[-2]
                curr_price = last['Close']
                avg_vol_20 = df['Volume'].rolling(20).mean().iloc[-1]
                avg_val_20 = (df['Close'] * df['Volume']).rolling(20).mean().iloc[-1]

                if avg_val_20 < 1e9: continue

                # LOGIKA SCORING KETAT (100 POIN)
                score = 0
                alasan = []

                if trade_mode == "Day Trading":
                    if curr_price > last['VWAP']: score += 25; alasan.append("Above VWAP")
                    if last['Volume'] > (avg_vol_20 * 1.2): score += 20; alasan.append("Vol Spike")
                    if curr_price >= last['MA200']: score += 15; alasan.append("Above MA200")
                    atr_mult = 1.5
                else:
                    if curr_price > last['MA50']: score += 25; alasan.append("Above MA50")
                    if last['EMA9'] > last['EMA21']: score += 20; alasan.append("EMA Cross")
                    if curr_price >= last['MA200']: score += 15; alasan.append("Major Uptrend")
                    atr_mult = 2.5

                if avg_val_20 > 5e9: score += 10; alasan.append("Liquid (>5M)")
                
                change_pct = ((curr_price - prev['Close']) / prev['Close']) * 100
                if change_pct > 2.0: score += 10; alasan.append(f"Strong Move (+{change_pct:.1f}%)")
                
                if last['EMA9'] > last['EMA21']: score += 10; alasan.append("Short-term Bullish")
                
                if 50 <= last['RSI'] <= 70: score += 5; alasan.append("RSI Ideal")
                if last['RSI'] > prev['RSI']: score += 5; alasan.append("RSI ↗️")

                # TRADING PLAN
                dynamic_support = last['VWAP'] if trade_mode == "Day Trading" else last['EMA9']
                entry_bawah = max(dynamic_support, curr_price * 0.97)
                
                sl_atr = curr_price - (atr_mult * last['ATR'])
                sl_final = max(sl_atr, curr_price * 0.92) 
                
                tp_target = curr_price + (curr_price - sl_final) * 2 
                rrr = (tp_target - curr_price) / (curr_price - sl_final) if curr_price > sl_final else 0

                if score >= 60 and rrr >= 1.5:
                    conf = "High" if score >= 80 else "Medium"
                    if conf == "High": high_score_found = True
                    
                    # Ambil Info Sektor
                    sektor_nama, _ = get_sector_data(ticker_bersih)
                    
                    hasil_lolos.append({
                        "Ticker": ticker_bersih,
                        "Sektor": sektor_nama,
                        "Syariah": "✅ Ya" if is_syariah(ticker_bersih) else "❌ Tidak",
                        "Conf": conf, "Skor": score, "Harga": int(curr_price),
                        "Rentang_Entry": f"Rp {int(entry_bawah)} - {int(curr_price)}",
                        "SL": int(sl_final), "TP": int(tp_target),
                        "Risk_Pct": round(((curr_price-sl_final)/curr_price)*100, 1),
                        "Reward_Pct": round(((tp_target-curr_price)/curr_price)*100, 1),
                        "Signal": ", ".join(alasan), "RRR": f"{rrr:.1f}x"
                    })
            except: continue

        progress_bar.empty()
        if high_score_found: play_alert_sound()

        if hasil_lolos:
            hasil_lolos.sort(key=lambda x: x['Skor'], reverse=True)
            top_3 = hasil_lolos[:3]
            
            st.header(f"🏆 Top 3 Pilihan {trade_mode}")
            cols = st.columns(len(top_3))
            for idx, item in enumerate(top_3):
                with cols[idx]:
                    st.markdown(f"### {item['Ticker']}")
                    st.write(f"**{item['Sektor']}** | Syariah: {item['Syariah']}")
                    st.metric("Skor", f"{item['Skor']} Pts", item['Conf'])
                    st.write(f"**Target:** Rp {item['TP']} (+{item['Reward_Pct']}%)")
                    st.write(f"**Proteksi:** Rp {item['SL']} (-{item['Risk_Pct']}%)")
                    st.info(f"Entry: {item['Rentang_Entry']}")
            
            st.markdown("---")
            st.subheader("📋 Radar Watchlist (Peringkat 4-10)")
            df_res = pd.DataFrame(hasil_lolos[3:10])
            if not df_res.empty:
                st.dataframe(
                    df_res[["Ticker", "Sektor", "Syariah", "Conf", "Skor", "Rentang_Entry", "RRR"]], 
                    use_container_width=True, 
                    hide_index=True
                )
        else:
            st.warning("Tidak ada saham yang memenuhi kriteria ketat hari ini.")

        # --- TAMPILAN DISCLAIMER LENGKAP ---
        st.markdown("---")
        st.caption("""
        ⚠️ **DISCLAIMER:** Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma indikator teknikal dan fundamental. Seluruh informasi yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi tanggung jawab pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik dan **Do Your Own Research (DYOR)**.
        """)

if __name__ == "__main__":
    run_screening()
