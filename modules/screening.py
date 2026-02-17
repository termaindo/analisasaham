import streamlit as st
import pandas as pd
import numpy as np
import pytz
import io # Untuk buffer data
from datetime import datetime
from fpdf import FPDF # Pastikan sudah install: pip install fpdf
from modules.data_loader import get_full_stock_data 
from modules.universe import UNIVERSE_SAHAM, is_syariah, get_sector_data 

# --- FUNGSI GENERATOR PDF ---
def export_to_pdf(hasil_lolos, trade_mode, session):
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, f"Laporan Analisa Expert Stock Pro", ln=True, align='C')
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 10, f"Tanggal: {datetime.now().strftime('%d-%m-%Y %H:%M')} | Mode: {trade_mode}", ln=True, align='C')
    pdf.ln(10)

    # Top 3 Picks
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, f"A. TOP 3 PILIHAN UTAMA ({trade_mode})", ln=True)
    pdf.set_font("Arial", '', 10)
    
    top_3 = hasil_lolos[:3]
    for item in top_3:
        # Menghapus emoji karena FPDF standar tidak mendukung unicode emoji
        syariah_text = "Ya" if "Ya" in item['Syariah'] else "Tidak"
        pdf.multi_cell(190, 7, (
            f"Ticker: {item['Ticker']} ({item['Sektor']}) | Syariah: {syariah_text}\n"
            f"Skor: {item['Skor']} Pts ({item['Conf']})\n"
            f"Rentang Entry: {item['Rentang_Entry']}\n"
            f"Target Profit: Rp {item['TP']} (+{item['Reward_Pct']}%)\n"
            f"Stop Loss: Rp {item['SL']} (-{item['Risk_Pct']}%)\n"
            f"Signal: {item['Signal']}\n"
            f"--------------------------------------------------"
        ))
    
    pdf.ln(5)

    # Watchlist Table
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "B. RADAR WATCHLIST", ln=True)
    pdf.set_font("Arial", 'B', 9)
    # Header Tabel
    pdf.cell(25, 8, "Ticker", 1)
    pdf.cell(35, 8, "Sektor", 1)
    pdf.cell(20, 8, "Syariah", 1)
    pdf.cell(20, 8, "Skor", 1)
    pdf.cell(50, 8, "Rentang Entry", 1)
    pdf.cell(20, 8, "RRR", 1)
    pdf.ln()

    pdf.set_font("Arial", '', 8)
    for item in hasil_lolos[3:10]:
        syariah_text = "Ya" if "Ya" in item['Syariah'] else "Tidak"
        pdf.cell(25, 8, str(item['Ticker']), 1)
        pdf.cell(35, 8, str(item['Sektor']), 1)
        pdf.cell(20, 8, syariah_text, 1)
        pdf.cell(20, 8, str(item['Skor']), 1)
        pdf.cell(50, 8, str(item['Rentang_Entry']), 1)
        pdf.cell(20, 8, str(item['RRR']), 1)
        pdf.ln()

    # Disclaimer
    pdf.ln(10)
    pdf.set_font("Arial", 'I', 8)
    disclaimer = ("DISCLAIMER: Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan "
                  "algoritma indikator teknikal. Seluruh informasi bukan merupakan ajakan atau rekomendasi pasti. "
                  "Keputusan trading sepenuhnya tanggung jawab pribadi. DYOR.")
    pdf.multi_cell(190, 5, disclaimer)

    return pdf.output(dest='S').encode('latin-1', 'ignore') # Mengembalikan bytes data

# --- 1. FUNGSI AUDIO ALERT ---
def play_alert_sound():
    audio_html = """
    <audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>
    """
    st.components.v1.html(audio_html, height=0)

# --- 2. INDIKATOR TEKNIKAL ---
def calculate_indicators(df, trade_mode):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    
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
    st.info(f"**Mode Aktif:** {trade_mode} | **Sesi:** {session} ({status_desc})")

    # Inisialisasi session state untuk menyimpan hasil agar tombol download tidak hilang
    if 'hasil_screening' not in st.session_state:
        st.session_state.hasil_screening = []

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

                score = 0
                alasan = []

                if trade_mode == "Day Trading":
                    if curr_price > last['VWAP']: score += 25; alasan.append("Above VWAP")
                    if last['Volume'] > (avg_vol_20 * 1.2): score += 20; alasan.append("Vol Spike")
                    if curr_price >= last['MA200']: score += 15; alasan.append("Above MA200")
                    atr_mult = 1.5
                    dynamic_support = last['VWAP']
                else:
                    if curr_price > last['MA50']: score += 25; alasan.append("Above MA50")
                    if last['EMA9'] > last['EMA21']: score += 20; alasan.append("EMA Cross")
                    if curr_price >= last['MA200']: score += 15; alasan.append("Major Uptrend")
                    atr_mult = 2.5
                    dynamic_support = last['EMA9']

                if avg_val_20 > 5e9: score += 10; alasan.append("Liquid (>5M)")
                
                change_pct = ((curr_price - prev['Close']) / prev['Close']) * 100
                if change_pct > 2.0: score += 10; alasan.append("Strong Move")
                
                if last['EMA9'] > last['EMA21']: score += 10; alasan.append("Bullish")
                
                if 50 <= last['RSI'] <= 70: score += 5
                if last['RSI'] > prev['RSI']: score += 5
                if last['RSI'] > 50: alasan.append("RSI Positif")

                entry_bawah = max(dynamic_support, curr_price * 0.97)
                sl_atr = curr_price - (atr_mult * last['ATR'])
                sl_final = max(sl_atr, curr_price * 0.92) 
                tp_target = curr_price + (curr_price - sl_final) * 2 
                rrr = (tp_target - curr_price) / (curr_price - sl_final) if curr_price > sl_final else 0

                if score >= 60 and rrr >= 1.5:
                    conf = "High" if score >= 80 else "Medium"
                    if conf == "High": high_score_found = True
                    sektor_nama, _ = get_sector_data(ticker_bersih)
                    
                    hasil_lolos.append({
                        "Ticker": ticker_bersih, "Sektor": sektor_nama,
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
        st.session_state.hasil_screening = hasil_lolos

    # --- BAGIAN TAMPILAN HASIL ---
    if st.session_state.hasil_screening:
        res = st.session_state.hasil_screening
        res.sort(key=lambda x: x['Skor'], reverse=True)
        top_3 = res[:3]
        watchlist = res[3:10]

        # Tombol Simpan PDF (Floating di atas hasil)
        pdf_data = export_to_pdf(res, trade_mode, session)
        st.download_button(
            label="📄 Simpan Hasil Analisa (PDF)",
            data=pdf_data,
            file_name=f"Analisa_{trade_mode}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )

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
        if watchlist:
            st.subheader(f"📋 Radar Watchlist {trade_mode}")
            st.dataframe(pd.DataFrame(watchlist)[["Ticker", "Sektor", "Syariah", "Conf", "Skor", "Rentang_Entry", "RRR"]], use_container_width=True, hide_index=True)

        st.markdown("---")
        st.caption("⚠️ **DISCLAIMER:** Laporan analisa ini dihasilkan secara otomatis. DYOR.")

if __name__ == "__main__":
    run_screening()
