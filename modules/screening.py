import streamlit as st
import pandas as pd
import numpy as np
import pytz
import os
import base64
import holidays
import io
import plotly.express as px
from datetime import datetime
from fpdf import FPDF 
from modules.data_loader import get_full_stock_data 
from modules.universe import UNIVERSE_SAHAM, is_syariah, get_sector_data 

# --- FUNGSI FORMAT RUPIAH ---
def format_rp(angka):
    """Fungsi untuk memformat angka menjadi format ribuan dengan titik"""
    return f"{int(angka):,}".replace(',', '.')

# --- 1. FUNGSI AUDIO ALERT ---
def play_alert_sound():
    audio_html = """
    <audio autoplay><source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg"></audio>
    """
    st.components.v1.html(audio_html, height=0)

# --- 2. ANALISA ROTASI SEKTOR ---
def analyze_sector_momentum(full_results_df):
    if full_results_df.empty:
        return pd.DataFrame(), []
    sector_summary = full_results_df.groupby('Sektor').agg({
        'Skor': 'mean',
        'Ticker': 'count'
    }).rename(columns={'Ticker': 'Jumlah_Saham', 'Skor': 'Avg_Score'}).sort_values('Avg_Score', ascending=False)
    leading_sectors = sector_summary[sector_summary['Avg_Score'] >= 60].index.tolist()
    return sector_summary, leading_sectors

# --- 3. FUNGSI GENERATOR PDF (INSTITUTIONAL FORMAT) ---
def export_to_pdf(hasil_lolos, trade_mode, session, sector_report, logo_path="logo_expert_stock_pro.png"):
    pdf = FPDF()
    pdf.add_page()
    
    # Header Box
    pdf.set_fill_color(20, 20, 20)
    pdf.rect(0, 0, 210, 25, 'F')
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=10, y=3, w=18, h=18)
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    pdf.set_xy(35, 8) 
    pdf.cell(0, 10, "Expert Stock Pro - Screening Saham Harian Pro", ln=True)
    
    # Hyperlink Sumber 
    pdf.set_y(28)
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(0, 0, 255) 
    pdf.cell(0, 5, "Sumber: https://lynk.id/hahastoresby", ln=True, align='C', link="https://lynk.id/hahastoresby")
    
    # Info Strategi dan Waktu (WIB)
    pdf.ln(3)
    pdf.set_text_color(0, 0, 0) 
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 8, f"Strategi: {trade_mode} | Sesi: {session}", ln=True, align='C')
    
    tz = pytz.timezone('Asia/Jakarta')
    waktu_cetak = datetime.now(tz).strftime('%d-%m-%Y %H:%M WIB')
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 5, f"Dicetak: {waktu_cetak}", ln=True, align='R')
    pdf.ln(2)

    # --- SEKSI A: TOP 3 PRIORITAS ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "A. TOP 3 PRIORITAS TRANSAKSI (HIGH CONVICTION)", 0, ln=True, fill=True)
    pdf.ln(2)

    top_3 = hasil_lolos[:3]
    for item in top_3:
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 6, f"{item['Ticker']} - {item['Sektor']} | Score: {item['Skor']}/100", ln=True) 
        
        pdf.set_font("Arial", '', 9)
        pdf.cell(60, 5, f"Entry: {item['Entry']}", 0)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(60, 5, f"TP Target: Rp {format_rp(item['TP'])}", 0)
        pdf.set_text_color(200, 0, 0)
        pdf.cell(60, 5, f"Stop Loss: Rp {format_rp(item['SL'])}", ln=True)
        pdf.set_text_color(0, 0, 0)
        
        pdf.set_font("Arial", 'I', 8)
        pdf.multi_cell(190, 4, f"Logic: {item['Logic']}")
        pdf.ln(2)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(2)

    # --- SEKSI B: WATCHLIST 4-10 ---
    watchlist = hasil_lolos[3:10]
    if watchlist:
        pdf.ln(3)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(190, 8, "B. RADAR WATCHLIST (RANK 4-10)", 0, ln=True, fill=True)
        pdf.ln(2)
        
        pdf.set_font("Arial", 'B', 8)
        pdf.cell(20, 6, "Ticker", 1, 0, 'C')
        pdf.cell(45, 6, "Sektor", 1, 0, 'C')
        pdf.cell(15, 6, "Skor", 1, 0, 'C')
        pdf.cell(35, 6, "Entry", 1, 0, 'C')
        pdf.cell(25, 6, "SL", 1, 0, 'C')
        pdf.cell(25, 6, "TP", 1, 0, 'C')
        pdf.cell(25, 6, "Maks Lot", 1, 1, 'C')
        
        pdf.set_font("Arial", '', 8)
        for w in watchlist:
            pdf.cell(20, 6, w['Ticker'], 1, 0, 'C')
            pdf.cell(45, 6, w['Sektor'][:20], 1, 0, 'C')
            pdf.cell(15, 6, str(w['Skor']), 1, 0, 'C')
            pdf.cell(35, 6, w['Entry'], 1, 0, 'C')
            pdf.cell(25, 6, format_rp(w['SL']), 1, 0, 'C')
            pdf.cell(25, 6, format_rp(w['TP']), 1, 0, 'C')
            pdf.cell(25, 6, w['Lot_Maks'], 1, 1, 'C')

    # --- DISCLAIMER FOOTER PDF ---
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, "DISCLAIMER:", ln=True) 
    pdf.set_font("Arial", 'I', 7)
    disclaimer_text = ("Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma indikator teknikal dan fundamental. Seluruh informasi yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi tanggung jawab pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik dan Do Your Own Research (DYOR) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.")
    pdf.multi_cell(190, 4, disclaimer_text)

    return pdf.output(dest='S').encode('latin-1', 'ignore')

# --- 4. INDIKATOR TEKNIKAL (MTF ENGINE) ---
def calculate_indicators(df, trade_mode):
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    df['Vol_SMA20'] = df['Volume'].rolling(window=20).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['VWAP'] = (df['Close'] * df['Volume']).rolling(window=5).sum() / df['Volume'].rolling(window=5).sum()
    
    return df

# --- 5. MARKET SESSION ---
def get_market_session():
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    if now.weekday() >= 5: return "AKHIR PEKAN", "Tutup."
    if now.date() in holidays.ID(years=now.year): return "LIBUR NASIONAL", "Tutup."
    curr_time = now.hour + now.minute/60
    if curr_time < 9.0: return "PRA-PASAR", "Wait."
    elif 9.0 <= curr_time <= 16.0: return "LIVE MARKET", "Trading."
    else: return "PASCA-PASAR", "Analysis."

# --- 6. MODUL UTAMA ---
def run_screening():
    st.set_page_config(page_title="🔍 Screening Saham Harian Pro", layout="wide")
    st.markdown("<h1 style='text-align: center;'>🔍 Screening Saham Harian Pro</h1>", unsafe_allow_html=True)
    st.markdown("---")

    # --- INFORMASI JAM OPTIMAL & PEMILIHAN MODE ---
    st.write("### ⚙️ Pemilihan Strategi & Waktu Analisa")
    
    st.info("⏰ **Panduan Waktu Analisa Optimal:** \n"
            "- **Day Trading:** 09.30 - 11.00 WIB (Untuk momentum harian tertinggi).\n"
            "- **Swing Trading:** > 16.00 WIB (Untuk konfirmasi harga penutupan yang solid).")
    
    trade_mode = st.radio("Pilih Strategi Trading (Mode Analisa):", ["Day Trading", "Swing Trading"], horizontal=True)

    # --- PENGATURAN & KALKULATOR DIPINDAHKAN KE HALAMAN UTAMA (DALAM EXPANDER) ---
    with st.expander("🛠️ Pengaturan Filter & Manajemen Risiko (Klik untuk Edit)", expanded=False):
        st.write("**Filter Institusi Tambahan:**")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            mtf_filter = st.checkbox("Hanya saham yang searah dengan tren besar", value=True.")
        with col_f2:
            sector_boost = st.checkbox("Hanya saham dari Sektor yang kuat", value=True.")
        
        st.markdown("---")
        st.write("**💼 Kalkulator Lot Maksimal (Institutional Position Sizing):**")
        st.caption("Manajemen risiko profesional berdasarkan Modal & Batas Kerugian.")
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            total_modal = st.number_input("Total Modal Portofolio Anda (Rp):", min_value=1000000, value=100000000, step=5000000)
        with col_m2:
            modal_risiko = st.number_input("Nominal Maksimal Siap Rugi (Rp):", min_value=10000, value=1000000, step=50000, help="Ketik angka murni tanpa titik.")
        
        # Kalkulasi Persentase untuk Visibilitas
        risiko_persen = (modal_risiko / total_modal) * 100 if total_modal > 0 else 0
        batas_alokasi_persen = 15.0
        batas_alokasi_rp = total_modal * (batas_alokasi_persen / 100)
        
        st.markdown(
            f"""
            <div style="background-color:#d4edda; border-left: 5px solid #28a745; padding: 10px; border-radius: 5px;">
                <p style="margin:0; font-size:12px; color:#155724;">Total Modal: <b>Rp {format_rp(total_modal)}</b></p>
                <p style="margin:0; font-size:12px; color:#155724;">Nominal Siap Rugi (<b>{risiko_persen:.1f}%</b> dari modal):</p>
                <h4 style="margin:0; color:#155724;">Rp {format_rp(modal_risiko)}</h4>
                <p style="margin:0; margin-top:5px; font-size:10px; color:#155724;"><i>*Sistem membatasi maks beli 15% modal (Rp {format_rp(batas_alokasi_rp)}) per saham agar tidak over-konsentrasi.</i></p>
            </div>
            """, unsafe_allow_html=True
        )

    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    curr_time_float = now.hour + now.minute/60
    is_weekend = now.weekday() >= 5
    session, status_desc = get_market_session()

    if "Tutup" in status_desc:
        st.error(f"**Status Market:** {session} ({status_desc})")
    else:
        st.info(f"**Status Market:** {session} ({status_desc})")

    # --- DYNAMIC NOTIFICATIONS ---
    if trade_mode == "Day Trading":
        is_golden = 9.5 <= curr_time_float <= 11.0 and not is_weekend
        if is_golden: 
            st.success("🌟 **GOLDEN HOURS AKTIF (09.30 - 11.00 WIB):** Waktu paling optimal untuk mencari saham potensial dan eksekusi Day Trading. Volatilitas dan volume sedang berada di puncaknya.")
        else: 
            if not is_weekend:
                st.warning("⚠️ **NOTIFIKASI WIN RATE:** Screening & Eksekusi Day Trading disarankan dijalankan pada pukul 09.30-11.00 WIB. Saat ini bukan jam optimal, sinyal mungkin rentan terjebak *sideways*.")
            else:
                st.warning("🚫 **PASAR TUTUP:** Data Day Trading yang dihasilkan adalah hasil penutupan terakhir. Gunakan hanya untuk evaluasi.")
    elif trade_mode == "Swing Trading":
        is_swing = curr_time_float >= 16.0 or is_weekend
        if is_swing: 
            st.success("✅ **WAKTU ANALISA SWING IDEAL:** Data penutupan telah final. Ini adalah waktu terbaik untuk menyusun *Watchlist* dan *Trading Plan* untuk esok hari.")
        else: 
            st.info("ℹ️ **INFO:** Screening Swing Trading paling akurat dilakukan setelah jam 16.00 WIB untuk memastikan struktur harga penutupan harian tidak berubah.")

    st.markdown("---")

    if st.button(f"🚀 JALANKAN ANALISA {trade_mode.upper()}"):
        saham_list = [f"{t}.JK" for tickers in UNIVERSE_SAHAM.values() for t in tickers]
        saham_list = list(set(saham_list))
        
        raw_results = []
        progress_bar = st.progress(0)

        for i, ticker in enumerate(saham_list):
            progress_bar.progress((i + 1) / len(saham_list))
            ticker_bersih = ticker.replace(".JK", "")
            try:
                data = get_full_stock_data(ticker)
                df = calculate_indicators(data['history'], trade_mode)
                last = df.iloc[-1]; prev = df.iloc[-2]
                curr_price = last['Close']
                avg_val_20 = (df['Close'] * df['Volume']).rolling(20).mean().iloc[-1]
                sektor_nama, _ = get_sector_data(ticker_bersih)

                is_macro_bullish = curr_price > last['MA200']
                is_medium_bullish = curr_price > last['MA50']
                is_micro_bullish = curr_price > last['VWAP'] if trade_mode == "Day Trading" else curr_price > last['EMA9']

                if mtf_filter and not (is_macro_bullish and is_medium_bullish): continue

                score = 0; alasan = []
                
                if is_macro_bullish: score += 20; alasan.append("Macro UP (MA200)")
                if is_medium_bullish: score += 15; alasan.append("Medium UP (MA50)")
                if is_micro_bullish: 
                    score += 15
                    alasan.append("Micro Momentum (VWAP)" if trade_mode == "Day Trading" else "Micro Momentum (EMA9)")
                
                if trade_mode == "Day Trading":
                    if curr_price > prev['High']:
                        score += 5; alasan.append("Breakout Prev. High")
                else: 
                    if last['EMA9'] > last['EMA21']:
                        score += 5; alasan.append("Momentum Cross (EMA9>21)")
                
                if last['Volume'] > df['Vol_SMA20'].iloc[-1]: score += 20; alasan.append("Volume Spike")
                if avg_val_20 > (1e10 if trade_mode == "Day Trading" else 5e9): 
                    score += 10; alasan.append("Inst. Liquidity")

                raw_results.append({
                    "Ticker": ticker_bersih, "Sektor": sektor_nama, "Skor": score, 
                    "Harga": int(curr_price), "ATR": last['ATR'], "Alasan": alasan, "RSI": last['RSI']
                })
            except: continue

        df_all = pd.DataFrame(raw_results)
        sector_report, leading_sectors = analyze_sector_momentum(df_all)
        
        final_picks = []
        for stock in raw_results:
            f_score = stock['Skor']
            
            if sector_boost and stock['Sektor'] in leading_sectors:
                f_score += 15; stock['Alasan'].append(f"Sector Hot: {stock['Sektor']}")
            
            # --- PROTEKSI HARD CAP STOP LOSS INSTITUSIONAL ---
            sl_mult = 1.8 if trade_mode == "Day Trading" else 2.5
            atr_sl = int(stock['Harga'] - (sl_mult * stock['ATR']))
            
            max_loss_pct = 0.03 if trade_mode == "Day Trading" else 0.08
            hard_cap_sl = int(stock['Harga'] * (1 - max_loss_pct))
            
            if hard_cap_sl > atr_sl:
                sl = hard_cap_sl
                stock['Alasan'].append(f"SL Hard Cap ({int(max_loss_pct*100)}%)")
            else:
                sl = atr_sl

            tp = int(stock['Harga'] + (stock['Harga'] - sl) * (1.5 if trade_mode == "Day Trading" else 2.0))
            rrr = (tp - stock['Harga']) / (stock['Harga'] - sl) if stock['Harga'] > sl else 0

            # --- LOGIKA POSITION SIZING GANDA INSTITUSI ---
            risiko_per_lembar = stock['Harga'] - sl
            if risiko_per_lembar > 0:
                lembar_maks_risiko = modal_risiko / risiko_per_lembar
                lembar_maks_alokasi = batas_alokasi_rp / stock['Harga']
                
                lembar_final = min(lembar_maks_risiko, lembar_maks_alokasi)
                lot_maksimal = int(lembar_final / 100)
            else:
                lot_maksimal = 0

            if f_score >= 65 and rrr >= 1.4:
                final_picks.append({
                    "Ticker": stock['Ticker'], "Sektor": stock['Sektor'], "Skor": f_score,
                    "Harga_Saat_Ini": int(stock['Harga']),
                    "Entry": f"Rp {format_rp(stock['Harga']*0.99)} - {format_rp(stock['Harga'])}",
                    "SL": sl, "TP": tp, "RRR": f"{rrr:.1f}x",
                    "Status": "🔥 HIGH CONVICTION" if f_score >= 85 else "🎯 READY",
                    "Logic": " | ".join(stock['Alasan']),
                    "Lot_Maks": f"{format_rp(lot_maksimal)} Lot" 
                })

        final_picks.sort(key=lambda x: x['Skor'], reverse=True)
        st.session_state.final_picks = final_picks[:10] 
        st.session_state.sector_report = sector_report
        st.session_state.pdf_session = session 
        progress_bar.empty()
        if any(p['Skor'] >= 85 for p in st.session_state.final_picks): play_alert_sound()

    # --- DISPLAY UI ---
    if 'final_picks' in st.session_state and st.session_state.final_picks:
        res = st.session_state.final_picks
        top_3 = res[:3]
        watchlist = res[3:10]

        st.subheader("🌐 Market Overview")
        c1, c2 = st.columns([2, 1])
        with c1:
            fig = px.bar(st.session_state.sector_report.reset_index(), x='Sektor', y='Avg_Score', color='Avg_Score', color_continuous_scale='Greens', title="Kekuatan Sektor Saat Ini")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.write("**Top Leading Sectors:**")
            for s in st.session_state.sector_report.index[:3]: st.success(s)

        st.markdown("---")
        
        st.header(f"🏆 Top 3 Prioritas {trade_mode}")
        if top_3:
            cols = st.columns(len(top_3))
            for idx, item in enumerate(top_3):
                with cols[idx]:
                    st.markdown(f"### {item['Ticker']}")
                    st.write(f"**Sektor:** {item['Sektor']}")
                    st.metric("Skor Institusi", f"{item['Skor']}/100 Pts", item['Status'])
                    st.write(f"**Target (TP):** Rp {format_rp(item['TP'])}")
                    st.write(f"**Proteksi (SL):** Rp {format_rp(item['SL'])}")
                    st.info(f"Area Entry: {item['Entry']}")
                    st.warning(f"🛡️ **Maks. Aman:** {item['Lot_Maks']}")
                    st.caption(f"💡 {item['Logic']}")
        else:
            st.warning("Belum ada saham yang memenuhi kriteria ketat institusi saat ini.")

        if watchlist:
            st.markdown("---")
            st.subheader(f"📋 Radar Watchlist (Rank 4-10)")
            df_watch_display = pd.DataFrame(watchlist).copy()
            df_watch_display['SL'] = df_watch_display['SL'].apply(format_rp)
            df_watch_display['TP'] = df_watch_display['TP'].apply(format_rp)
            
            kolom_tampil = ["Ticker", "Sektor", "Skor", "Status", "Entry", "SL", "TP", "RRR", "Lot_Maks"]
            st.dataframe(df_watch_display[kolom_tampil], use_container_width=True, hide_index=True)
        
        st.markdown("<br><hr>", unsafe_allow_html=True)
        st.caption("⚠️ **DISCLAIMER:** Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma indikator teknikal dan fundamental. Seluruh informasi yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi tanggung jawab pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik dan *Do Your Own Research* (DYOR) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.")
        st.markdown("<br>", unsafe_allow_html=True)
        
        waktu_cetak_pdf = datetime.now(tz).strftime('%Y%m%d_%H%M')
        pdf_data = export_to_pdf(res, trade_mode, st.session_state.pdf_session, st.session_state.sector_report)
        st.download_button(
            label="📥 UNDUH LAPORAN SCREENING LENGKAP (PDF)", 
            data=pdf_data, 
            file_name=f"ExpertStockPro_{trade_mode}_{waktu_cetak_pdf}.pdf", 
            mime="application/pdf", 
            use_container_width=True
        )

if __name__ == "__main__":
    run_screening()
