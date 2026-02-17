import streamlit as st
import pandas as pd
import numpy as np
import pytz
import io 
from datetime import datetime
from fpdf import FPDF 
from modules.data_loader import get_full_stock_data 
from modules.universe import UNIVERSE_SAHAM, is_syariah, get_sector_data 

# --- FUNGSI GENERATOR PDF ---
def export_to_pdf(hasil_lolos, trade_mode, session):
    pdf = FPDF()
    pdf.add_page()
    
    # --- HEADER APLIKASI ---
    pdf.set_font("Arial", 'B', 18)
    pdf.set_text_color(30, 136, 229) 
    pdf.cell(190, 12, "EXPERT STOCK PRO", ln=True, align='C')
    
    pdf.set_font("Arial", 'B', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(190, 5, "Quantitative Technical Analysis Report", ln=True, align='C')
    
    pdf.set_font("Arial", 'I', 9)
    safe_session = session.encode('ascii', 'ignore').decode('ascii')
    pdf.cell(190, 8, f"Dihasilkan pada: {datetime.now().strftime('%d-%m-%Y %H:%M WIB')} | Sesi: {safe_session}", ln=True, align='C')
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y()) 
    pdf.ln(5)

    # --- INFORMASI STRATEGI ---
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(50, 8, "Strategi Trading:", 0)
    pdf.set_font("Arial", '', 11)
    pdf.cell(140, 8, f"{trade_mode}", ln=True)
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(50, 8, "Akses Aplikasi Full:", 0)
    pdf.set_font("Arial", 'U', 11)
    pdf.set_text_color(0, 0, 255)
    pdf.cell(140, 8, "lynk.id/hahastoresby", ln=True, link="https://lynk.id/hahastoresby")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # --- SEKSI A: TOP 3 ANALISA MENDALAM ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "A. ANALISA PRIORITAS UTAMA (TOP 3)", 0, ln=True, fill=True)
    pdf.ln(3)

    top_3 = hasil_lolos[:3]
    for item in top_3:
        syariah_txt = "Ya" if "Ya" in item['Syariah'] else "Tidak"
        
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(190, 8, f"Ticker: {item['Ticker']} | Sektor: {item['Sektor']} | Syariah: {syariah_txt}", ln=True)
        
        pdf.set_font("Arial", '', 10)
        # Menampilkan tipe data float dengan rapi jika ada koma (misal 82.5)
        pdf.cell(95, 7, f"Confidence Score: {item['Skor']:g} Pts ({item['Conf']})", 0)
        pdf.cell(95, 7, f"Risk/Reward Ratio: {item['RRR']}", ln=True)
        
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(95, 7, f"Entry Zone: {item['Rentang_Entry']}", 0)
        pdf.set_text_color(200, 0, 0) 
        pdf.cell(95, 7, f"Stop Loss (Proteksi): Rp {item['SL']} (-{item['Risk_Pct']}%)", ln=True)
        
        pdf.set_text_color(0, 128, 0) 
        pdf.cell(95, 7, f"Take Profit (Target): Rp {item['TP']} (+{item['Reward_Pct']}%)", 0)
        
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", 'I', 9)
        rsi_bersih = item['RSI'].replace("↗️", "UP").replace("↘️", "DOWN")
        pdf.cell(95, 7, f"Indikator RSI: {rsi_bersih}", ln=True)
        
        pdf.set_font("Arial", '', 9)
        pdf.multi_cell(180, 6, f"Sinyal Teknis: {item['Signal']}")
        pdf.ln(2)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(3)

    # --- SEKSI B: RADAR WATCHLIST ---
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "B. RADAR WATCHLIST (RANK 4-10)", 0, ln=True, fill=True)
    pdf.ln(3)

    pdf.set_font("Arial", 'B', 9)
    pdf.cell(20, 8, "Ticker", 1, 0, 'C')
    pdf.cell(45, 8, "Sektor", 1, 0, 'C')
    pdf.cell(20, 8, "Skor", 1, 0, 'C')
    pdf.cell(40, 8, "Area Entry", 1, 0, 'C')
    pdf.cell(40, 8, "Target (TP)", 1, 0, 'C')
    pdf.cell(25, 8, "RRR", 1, 1, 'C')

    pdf.set_font("Arial", '', 8)
    for item in hasil_lolos[3:10]:
        pdf.cell(20, 8, item['Ticker'], 1, 0, 'C')
        sektor_pendek = str(item['Sektor'])[:15] 
        pdf.cell(45, 8, sektor_pendek, 1, 0, 'C')
        pdf.cell(20, 8, str(f"{item['Skor']:g}"), 1, 0, 'C')
        rentang_pendek = str(item['Rentang_Entry']).replace("Rp ", "")
        pdf.cell(40, 8, rentang_pendek, 1, 0, 'C')
        pdf.cell(40, 8, f"{item['TP']} (+{item['Reward_Pct']}%)", 1, 0, 'C')
        pdf.cell(25, 8, str(item['RRR']), 1, 1, 'C')

    # --- FOOTER & DISCLAIMER ---
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, "DISCLAIMER:", ln=True) 
    pdf.set_font("Arial", 'I', 7)
    disclaimer_text = ("Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma indikator teknikal "
                       "dan fundamental. Seluruh informasi yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau "
                       "paksaan untuk membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi tanggung jawab "
                       "pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik dan DYOR.")
    pdf.multi_cell(190, 4, disclaimer_text)

    pdf.set_y(-15)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 10, f"Halaman {pdf.page_no()} | Dibuat oleh Expert Stock Pro", 0, 0, 'C')

    return pdf.output(dest='S').encode('latin-1', 'ignore') 
    
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

    if 'hasil_screening' not in st.session_state:
        st.session_state.hasil_screening = []

    if st.button(f"Mulai Scan {trade_mode} (perlu waktu +/- 2 menit)"):
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

                # --- 1. LOGIKA SCORING KETAT & TRADING PLAN ---
                if trade_mode == "Day Trading":
                    if curr_price > last['VWAP']: score += 25; alasan.append("Above VWAP")
                    if last['Volume'] > (avg_vol_20 * 1.2): score += 20; alasan.append("Vol Spike")
                    if curr_price >= last['MA200']: score += 15; alasan.append("Above MA200")
                    if avg_val_20 > 5e9: score += 10; alasan.append("Liquid (>5M)")
                    
                    change_pct = ((curr_price - prev['Close']) / prev['Close']) * 100
                    if change_pct > 2.0: score += 10; alasan.append("Strong Move")
                    
                    if last['EMA9'] > last['EMA21']: score += 10; alasan.append("EMA Cross Trigger Momentum")
                    
                    if 50 <= last['RSI'] <= 70: score += 5; alasan.append("RSI Ideal")
                    if last['RSI'] > prev['RSI']: score += 5; alasan.append("RSI Trend")

                    # Entry Bawah: Maksimal turun 1.5% atau di VWAP
                    entry_bawah = max(last['VWAP'], curr_price * 0.985)
                    # SL: Maksimal turun 3% dari harga beli
                    sl_final = curr_price * 0.97 
                    # TP: RRR 1:1.5
                    tp_target = curr_price + (curr_price - sl_final) * 1.5

                else: # Swing Trading Mode
                    if curr_price >= last['MA200']: score += 20; alasan.append("Major Uptrend")
                    if curr_price >= last['MA50']: score += 20; alasan.append("Medium  Uptrend Batas Psikologi Institusi")
                    
                    change_pct = ((curr_price - prev['Close']) / prev['Close']) * 100
                    if change_pct > 2.0 or curr_price > prev['High']: score += 20; alasan.append("Breakout Action")
                    
                    if last['EMA9'] > last['EMA21']: score += 15; alasan.append("EMA Cross Trigger Momentum")
                    
                    if 50 <= last['RSI'] <= 70: score += 7.5; alasan.append("RSI Ideal")
                    if last['RSI'] > prev['RSI']: score += 7.5; alasan.append("RSI Trend")
                    
                    if avg_val_20 > 5e9: score += 10; alasan.append("Liquid (>5M)")

                    # Entry Bawah: Maksimal turun 4% atau di EMA9
                    entry_bawah = max(last['EMA9'], curr_price * 0.96)
                    # SL: Maksimal turun 8% (menggunakan 2,5x ATR)
                    sl_atr = curr_price - (2.5 * last['ATR'])
                    sl_final = max(sl_atr, curr_price * 0.92) 
                    # TP: RRR 1:2
                    tp_target = curr_price + (curr_price - sl_final) * 2

                rsi_val = f"{last['RSI']:.1f} {'↗️' if last['RSI'] > prev['RSI'] else '↘️'}"
                rrr = (tp_target - curr_price) / (curr_price - sl_final) if curr_price > sl_final else 0

                # Hanya lolos jika RR ratio sesuai batas minimum (otomatis menyesuaikan mode)
                if score >= 60 and rrr >= 1.4: # Diberi buffer ke 1.4 agar 1.5 tetap aman lolos
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
                        "Signal": ", ".join(alasan), "RRR": f"{rrr:.1f}x",
                        "RSI": rsi_val 
                    })
            except Exception as e: 
                continue

        progress_bar.empty()
        if high_score_found: play_alert_sound()
        st.session_state.hasil_screening = hasil_lolos

    # --- BAGIAN TAMPILAN HASIL ---
    if st.session_state.hasil_screening:
        res = st.session_state.hasil_screening
        res.sort(key=lambda x: x['Skor'], reverse=True)
        top_3 = res[:3]
        watchlist = res[3:10]

        # Tombol Simpan PDF
        pdf_data = export_to_pdf(res, trade_mode, session)
        st.download_button(
            label="📄 Simpan Hasil Analisa (PDF)",
            data=pdf_data,
            file_name=f"Analisa_{trade_mode.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )

        st.header(f"🏆 Top 3 Pilihan {trade_mode}")
        cols = st.columns(len(top_3))
        for idx, item in enumerate(top_3):
            with cols[idx]:
                st.markdown(f"### {item['Ticker']}")
                st.write(f"**{item['Sektor']}** | Syariah: {item['Syariah']}")
                st.metric("Skor", f"{item['Skor']:g} Pts", item['Conf'])
                st.write(f"**Target:** Rp {item['TP']} (+{item['Reward_Pct']}%)")
                st.write(f"**Proteksi:** Rp {item['SL']} (-{item['Risk_Pct']}%)")
                st.info(f"Entry: {item['Rentang_Entry']}")
        
        st.markdown("---")
        if watchlist:
            st.subheader(f"📋 Radar Watchlist {trade_mode}")
            st.dataframe(pd.DataFrame(watchlist)[["Ticker", "Sektor", "Syariah", "Conf", "Skor", "Rentang_Entry", "RRR"]], use_container_width=True, hide_index=True)

        st.markdown("---")
        st.caption("""⚠️ **DISCLAIMER:** Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma indikator teknikal dan fundamental. Seluruh informasi yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi tanggung jawab pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik dan DYOR.""")

if __name__ == "__main__":
    run_screening()
