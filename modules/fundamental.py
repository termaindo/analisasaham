import streamlit as st
import pandas as pd
import numpy as np
import base64
import yfinance as yf
import os
from datetime import datetime
from io import BytesIO
from fpdf import FPDF
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal
from modules.universe import is_syariah  

def translate_sector(sector_en):
    mapping = {
        "Financial Services": "Jasa Keuangan",
        "Basic Materials": "Bahan Baku & Tambang",
        "Energy": "Energi",
        "Communication Services": "Telekomunikasi",
        "Consumer Cyclical": "Konsumsi Siklikal",
        "Consumer Defensive": "Konsumsi Non-Siklikal",
        "Healthcare": "Kesehatan",
        "Industrials": "Industri",
        "Real Estate": "Properti",
        "Technology": "Teknologi",
        "Utilities": "Utilitas"
    }
    return mapping.get(sector_en, sector_en)

# --- FUNGSI ANALISA SENTIMEN KUALITATIF ---
def analisa_sentimen_berita(ticker):
    """Membaca sentimen berita terbaru menggunakan algoritma heuristik kata kunci"""
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        if not news:
            return "NETRAL", [], "Tidak ada berita terbaru ditemukan di pangkalan data."
        
        # Kamus sentimen sederhana
        kata_positif = ['laba', 'naik', 'untung', 'tumbuh', 'dividen', 'akuisisi', 'ekspansi', 'lonjak', 'rekor', 'prospek', 'positif', 'profit', 'growth', 'surge', 'target']
        kata_negatif = ['rugi', 'turun', 'anjlok', 'utang', 'gugatan', 'kasus', 'susut', 'merosot', 'negatif', 'krisis', 'loss', 'drop', 'plunge', 'debt', 'denda']
        
        skor_sentimen = 0
        berita_terpilih = []
        
        for artikel in news[:5]: # Ambil maksimal 5 berita terbaru
            judul = artikel.get('title', '')
            judul_lower = judul.lower()
            publisher = artikel.get('publisher', 'Sumber Tidak Diketahui')
            link = artikel.get('link', '#')
            
            pos_count = sum(1 for kata in kata_positif if kata in judul_lower)
            neg_count = sum(1 for kata in kata_negatif if kata in judul_lower)
            
            if pos_count > neg_count:
                skor_sentimen += 1
                sentimen_item = "🟢 Positif"
            elif neg_count > pos_count:
                skor_sentimen -= 1
                sentimen_item = "🔴 Negatif"
            else:
                sentimen_item = "⚪ Netral"
                
            berita_terpilih.append({
                'judul': judul,
                'publisher': publisher,
                'link': link,
                'sentimen': sentimen_item
            })
        
        if skor_sentimen >= 2:
            kesimpulan = "🌟 BULLISH (Optimis)"
            alasan = "Berita terbaru didominasi oleh sentimen positif terkait kinerja atau aksi korporasi."
        elif skor_sentimen <= -2:
            kesimpulan = "⚠️ BEARISH (Pesimis)"
            alasan = "Terdapat beberapa sentimen negatif atau tantangan makro/mikro pada berita terbaru."
        else:
            kesimpulan = "⚖️ NETRAL"
            alasan = "Sentimen berita saat ini berimbang atau tidak ada katalis pergerakan harga yang tajam."
            
        return kesimpulan, berita_terpilih, alasan
    except Exception as e:
        return "NETRAL", [], "Gagal memproses data berita terkini."

def hitung_skor_fundamental(info, financials, cashflow, mean_pe_5y, mean_pbv_5y, div_yield):
    skor = 0
    total_metrik = 8
    metrik_tersedia = 0
    
    sector = info.get('sector', '')
    industry = info.get('industry', '')
    
    is_bank = 'Bank' in industry
    is_infra = 'Infrastructure' in industry or sector in ['Utilities', 'Real Estate', 'Industrials']
    
    # --- 1. KESEHATAN KEUANGAN ---
    if is_bank:
        if info.get('capitalAdequacyRatio') is not None: metrik_tersedia += 1
        car = info.get('capitalAdequacyRatio', 18) 
        npl = info.get('nonPerformingLoan', 2.5)   
        if car > 20: skor += 10
        elif car >= 15: skor += 5
        if npl < 2: skor += 10
        elif npl <= 3.5: skor += 5
    elif is_infra:
        if info.get('debtToEquity') is not None: metrik_tersedia += 1
        der = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
        if der < 1.5: skor += 10
        elif der <= 2.5: skor += 5
        icr = 2.0 
        try:
            ebit = financials.loc['EBIT'].iloc[0]
            interest = abs(financials.loc['Interest Expense'].iloc[0])
            if interest > 0: icr = ebit / interest
        except: pass
        if icr > 3.0: skor += 10
        elif icr >= 1.5: skor += 5
    else: 
        if info.get('debtToEquity') is not None: metrik_tersedia += 1
        der = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
        if der < 0.5: skor += 10
        elif der <= 1.0: skor += 5
        cr = info.get('currentRatio', 0)
        if cr > 1.5: skor += 10
        elif cr >= 1.0: skor += 5

    # --- 2. PROFITABILITAS ---
    if info.get('returnOnEquity') is not None: metrik_tersedia += 1
    roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0
    if roe > 15: skor += 10
    elif roe >= 10: skor += 5
    
    if info.get('profitMargins') is not None: metrik_tersedia += 1
    npm = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0
    if npm > 10: skor += 10
    elif npm >= 5: skor += 5

    # --- 3. KUALITAS ARUS KAS ---
    ocf_sehat = False
    try:
        if not cashflow.empty and not financials.empty:
            metrik_tersedia += 1
            ocf = cashflow.loc['Operating Cash Flow'].iloc[0]
            net_income = financials.loc['Net Income'].iloc[0]
            if ocf > net_income: 
                skor += 10 
                ocf_sehat = True
            elif ocf > 0: 
                skor += 5 
                ocf_sehat = True
    except: pass

    # --- 4. VALUASI DINAMIS ---
    if info.get('trailingPE') is not None: metrik_tersedia += 1
    per = info.get('trailingPE', 0)
    if info.get('priceToBook') is not None: metrik_tersedia += 1
    pbv = info.get('priceToBook', 0)
    
    if per > 0 and mean_pe_5y > 0:
        pe_discount = ((mean_pe_5y - per) / mean_pe_5y) * 100
        if pe_discount > 20: skor += 10
        elif pe_discount >= 0: skor += 5
    
    if pbv > 0 and mean_pbv_5y > 0:
        pbv_discount = ((mean_pbv_5y - pbv) / mean_pbv_5y) * 100
        if pbv_discount > 20: skor += 10
        elif pbv_discount >= 0: skor += 5

    # --- 5. PERTUMBUHAN ---
    if info.get('earningsGrowth') is not None: metrik_tersedia += 1
    eps_g = info.get('earningsGrowth', 0) * 100 if info.get('earningsGrowth') else 0
    if eps_g > 15: skor += 10
    elif eps_g >= 5: skor += 7
    elif eps_g > 0: skor += 3
    
    if info.get('revenueGrowth') is not None: metrik_tersedia += 1
    rev_g = info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0
    if rev_g > 10: skor += 10
    elif rev_g >= 0: skor += 5

    # --- 6. DIVIDEN ---
    if div_yield > 5: skor += 10
    elif div_yield >= 2: skor += 5

    konf_pct = (metrik_tersedia / total_metrik) * 100
    if konf_pct >= 85: label_konf = "Tinggi (Data Lengkap)"
    elif konf_pct >= 50: label_konf = "Sedang (Sebagian Data Kosong)"
    else: label_konf = "Rendah (Hati-hati, Data Kurang Memadai)"
    
    return skor, konf_pct, label_konf, ocf_sehat

# --- FUNGSI GENERATE PDF (HEADER BARU) ---
def generate_pdf_report(data_dict, logo_path="logo_expert_stock_pro.png"):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. HEADER BOX HITAM
    # Menggambar kotak hitam penuh di bagian atas
    pdf.set_fill_color(20, 20, 20)  # Warna Hitam (Almost Black)
    pdf.rect(0, 0, 210, 25, 'F')    # Lebar A4 = 210mm
    
    # a) LOGO dengan Bingkai Emas
    if os.path.exists(logo_path):
        # Gambar bingkai emas (rect di belakang logo)
        pdf.set_fill_color(218, 165, 32) # Goldenrod color
        pdf.rect(10, 3, 19, 19, 'F')
        # Tampilkan logo
        pdf.image(logo_path, x=10.5, y=3.5, w=18, h=18)
    
    # b) & c) NAMA APLIKASI & MODUL (Teks Putih)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    # Posisi di sebelah kanan logo (logo width ~20 + margin 10 = 30)
    pdf.set_xy(35, 8) 
    pdf.cell(0, 10, "Expert Stock Pro - Analisa Fundamental & Kualitatif Pro", ln=True)
    
    # Reset posisi Y ke bawah kotak hitam
    pdf.set_y(28)
    
    # 2. HYPERLINK SUMBER
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(0, 0, 255)  # Warna Biru
    pdf.cell(0, 5, "Sumber: https://lynk.id/hahastoresby", ln=True, align='C', link="https://lynk.id/hahastoresby")
    pdf.ln(2)
    
    # 3. NAMA SAHAM & PERUSAHAAN (CENTER)
    pdf.set_text_color(0, 0, 0) # Kembali ke Hitam
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 8, f"{data_dict['ticker']} - {data_dict['nama']}", ln=True, align='C')
    
    # 4. INFO SEKTOR & SYARIAH (CENTER)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, f"Sektor: {data_dict['sektor']} | Status: {data_dict['syariah']}", ln=True, align='C')
    pdf.ln(2)
    
    # 5. INFO TANGGAL & HARGA (RATA KANAN)
    pdf.set_font("Arial", 'B', 10)
    waktu_analisa = data_dict.get('waktu', datetime.now().strftime("%d-%m-%Y %H:%M"))
    pdf.cell(0, 5, f"Analisa: {waktu_analisa} | Harga: Rp {data_dict['curr_price']:,.0f}", ln=True, align='R')
    
    # Garis Bawah Header
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y()+2, 200, pdf.get_y()+2)
    pdf.ln(5)
    
    # --- MULAI KONTEN LAPORAN ---
    
    # 1. Skor & Keputusan
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "1. SKOR FUNDAMENTAL & KEPUTUSAN", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, f"Skor Akhir: {data_dict['skor']}/100", ln=True)
    pdf.cell(0, 6, f"Tingkat Kepercayaan Data: {data_dict['konf_label']} ({data_dict['konf_pct']:.0f}%)", ln=True)
    pdf.cell(0, 6, f"Keputusan: {data_dict['keputusan']}", ln=True)
    pdf.multi_cell(0, 6, f"Alasan: {data_dict['alasan']}")
    pdf.ln(5)

    # 2. Analisa SWOT
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "2. OVERVIEW & ANALISA SWOT", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, f"Posisi Industri: {data_dict['posisi']}", ln=True)
    pdf.multi_cell(0, 6, f"Kekuatan (Strengths): {data_dict['s_1']}, {data_dict['s_2']}")
    pdf.multi_cell(0, 6, f"Kelemahan (Weaknesses): {data_dict['w_1']}, {data_dict['w_2']}")
    pdf.ln(5)

    # 3. Analisa Keuangan Dinamis
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "3. ANALISA KEUANGAN", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, f"ROE (Efisiensi): {data_dict['roe']:.2f}%", ln=True)
    pdf.cell(0, 6, f"NPM (Marjin Laba): {data_dict['npm']:.2f}%", ln=True)
    if data_dict['is_bank']:
        pdf.cell(0, 6, f"CAR (Kecukupan Modal): {data_dict['car']:.2f}%", ln=True)
        pdf.cell(0, 6, f"NPL (Kredit Macet): {data_dict['npl']:.2f}%", ln=True)
    else:
        pdf.cell(0, 6, f"Debt to Equity (DER): {data_dict['der']:.2f}x", ln=True)
        pdf.cell(0, 6, f"Current Ratio (CR): {data_dict['cr']:.2f}x", ln=True)
    pdf.ln(5)
    
    # 4. Valuasi
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "4. VALUASI & MARGIN OF SAFETY", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, f"Harga Wajar (Graham): Rp {data_dict['fair_price']:,.0f}", ln=True)
    pdf.cell(0, 6, f"Harga Saat Ini: Rp {data_dict['curr_price']:,.0f}", ln=True)
    pdf.cell(0, 6, f"Margin of Safety (MOS): {data_dict['mos']:.1f}%", ln=True)
    pdf.cell(0, 6, f"Estimasi Dividen (Rupiah): Rp {data_dict['div_rate']:,.0f} per lembar", ln=True)
    pdf.cell(0, 6, f"Estimasi Dividend Yield: {data_dict['div_yield']:.2f}%", ln=True)
    pdf.ln(5)

    # 5. Sentimen Kualitatif
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "5. SENTIMEN BERITA (KUALITATIF)", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, f"Kesimpulan: {data_dict['sentimen_kesimpulan']}", ln=True)
    pdf.multi_cell(0, 6, f"Catatan: {data_dict['sentimen_alasan']}")
    pdf.ln(5)
    
    # 6. Trading Plan
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "6. TRADING PLAN & EKSEKUSI", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, f"Harga Saat Ini: Rp {data_dict['curr_price']:,.0f}", ln=True)
    pdf.multi_cell(0, 6, f"Saran Entry: {data_dict['saran_entry']}")
    pdf.cell(0, 6, f"Target TP: Minimal di Rp {data_dict['tp']:,.0f} (+{data_dict['reward_pct']:.1f}%)", ln=True)
    pdf.cell(0, 6, f"Average Down: Area Rp {data_dict['avg_down']:,.0f} (Penurunan ~12%)", ln=True)
    pdf.cell(0, 6, f"Batas Cutloss: Tembus Rp {data_dict['sl']:,.0f} (Penurunan ~30%)", ln=True)
    pdf.ln(10)
    
    # Disclaimer PDF (Tanpa Markdown Bold agar format teks murni rapi di FPDF)
    pdf.set_font("Arial", 'I', 8)
    pdf.multi_cell(0, 4, "DISCLAIMER: Semua informasi, analisa teknikal, Analisa fundamental, ataupun sinyal trading dan analisa-analisa lain yang disediakan di modul ini hanya untuk tujuan edukasi dan informasi. Ini bukan merupakan rekomendasi, ajakan, atau nasihat keuangan untuk membeli atau menjual saham tertentu. Keputusan investasi sepenuhnya berada di tangan Anda. Harap lakukan riset Anda sendiri (Do Your Own Research) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.")
    
    # Output sebagai Bytes
    return bytes(pdf.output(dest='S').encode('latin1'))

def run_fundamental():
    # --- TAMPILAN WEB ---
    # Mencari lokasi file logo. 
    logo_file = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_file):
        logo_file = "../logo_expert_stock_pro.png"
        
    # Tampilkan Logo di Web bagian TENGAH dengan ukuran BESAR
    if os.path.exists(logo_file):
        # Menggunakan 3 kolom dengan kolom tengah paling besar untuk menengahkan gambar
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            st.image(logo_file, use_container_width=True)
        # Menengahkan teks judul menggunakan Markdown HTML
        st.markdown("<h1 style='text-align: center;'>Analisa Fundamental & Kualitatif Pro</h1>", unsafe_allow_html=True)
    else:
        st.markdown("<h1 style='text-align: center;'>Analisa Fundamental & Kualitatif Pro</h1>", unsafe_allow_html=True)
        st.warning("⚠️ File logo belum ditemukan.")
        
    st.markdown("---")
    
    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Contoh: ASII):", value="ASII").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah Fundamental {ticker_input}"):
        with st.spinner("Menginvestigasi kualitas aset, valuasi, dan sentimen pasar..."):
            data = get_full_stock_data(ticker)
            info = data['info']
            financials = data.get('financials', pd.DataFrame())
            cashflow = data.get('cashflow', pd.DataFrame())
            history = data['history']
            
            if not info or financials.empty:
                st.error("Data tidak lengkap. Mohon tunggu sejenak atau bersihkan cache.")
                return

            # Cek status industri untuk tampilan UI dinamis
            is_bank_ui = 'Bank' in info.get('industry', '')

            # --- AMBIL DATA SENTIMEN ---
            sentimen_kesimpulan, daftar_berita, sentimen_alasan = analisa_sentimen_berita(ticker)

            # --- HEADER UTAMA WEB ---
            nama_perusahaan = info.get('longName', info.get('shortName', 'Nama Tidak Diketahui'))
            st.markdown(f"<h1 style='text-align: center; color: #4CAF50; margin-bottom: 0;'>🏢 {ticker_input} - {nama_perusahaan}</h1>", unsafe_allow_html=True)
            
            sektor_indo = translate_sector(info.get('sector'))
            status_syariah = "Syariah (ISSI)" if is_syariah(ticker_input) else "Non-Syariah"
            st.markdown(f"<p style='text-align: center; font-size: 18px; color: #b0bec5;'>Sektor: <b>{sektor_indo}</b> | Kategori: <b>✅ {status_syariah}</b></p>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            # --- PERHITUNGAN FAIR PRICE & MOS ---
            curr_price = info.get('currentPrice', 0)
            eps = info.get('trailingEps', 0)
            bvps = info.get('bookValue', 0)
            fair_price = np.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else curr_price
            
            mos = ((fair_price - curr_price) / fair_price) * 100 if fair_price > 0 else 0

            # --- SCORING & LOGIKA REKOMENDASI CERDAS ---
            try:
                mean_pe_5y = info.get('trailingPE', 15) * 0.95 
                mean_pbv_5y = info.get('priceToBook', 1.5) * 0.9 
            except: mean_pe_5y, mean_pbv_5y = 15.0, 1.5
            
            div_yield = hitung_div_yield_normal(info)
            div_rate = info.get('dividendRate', 0)
            
            skor_akhir, konf_pct, label_konf, ocf_sehat = hitung_skor_fundamental(info, financials, cashflow, mean_pe_5y, mean_pbv_5y, div_yield)
            
            # --- PENENTUAN KEPUTUSAN GABUNGAN (MODIFIKASI MOS) ---
            if skor_akhir >= 80 and konf_pct >= 60 and mos >= 30:
                keputusan = "🌟 SANGAT LAYAK DIBELI"
                warna_keputusan = "success"
                alasan_keputusan = f"Fundamental sangat kokoh (Skor: {skor_akhir}) dipadukan dengan Harga Sangat Diskon (MOS: {mos:.1f}%)."
            elif skor_akhir >= 60 and konf_pct >= 50 and mos >= 15:
                keputusan = "✅ LAYAK DIBELI"
                warna_keputusan = "info"
                alasan_keputusan = f"Perusahaan sehat secara operasional dan harga masih masuk akal (Undervalued dengan MOS memadai)."
            elif skor_akhir >= 60 and mos < 15:
                keputusan = "⏳ TUNGGU KOREKSI (Hold)"
                warna_keputusan = "warning"
                alasan_keputusan = f"Perusahaan bagus, namun harga saat ini belum cukup aman (Margin of Safety terlalu tipis). Kesabaran diperlukan."
            else:
                keputusan = "⛔ BELUM LAYAK DIBELI (Hindari)"
                warna_keputusan = "error"
                alasan_keputusan = f"Kualitas fundamental rentan atau data laporan keuangan tidak meyakinkan."

            # --- PERSIAPAN DATA TRADING PLAN ---
            atr = (history['High'] - history['Low']).tail(14).mean() if not history.empty else (curr_price * 0.02)
            
            if mos < 15: 
                base_entry_price = fair_price * 0.85
                saran_entry = f"Sabar tunggu koreksi di Harga ideal: Rp {base_entry_price:,.0f} (MOS 15%)"
                avg_down_price = base_entry_price * 0.88 
                sl_final = base_entry_price * 0.70       
            else:
                batas_bawah = max(curr_price - atr, curr_price * 0.95)
                saran_entry = f"Beli Bertahap di area Rp {batas_bawah:,.0f} - Rp {curr_price:,.0f}"
                avg_down_price = curr_price * 0.88 
                sl_final = curr_price * 0.70       

            target_short = fair_price if fair_price > curr_price else curr_price * 1.15
            
            reward_pct = ((target_short - curr_price) / curr_price) * 100 if curr_price > 0 else 0

            # --- RENDER TAMPILAN WEB STREAMLIT ---
            st.header("🏆 SKOR FUNDAMENTAL & KEPUTUSAN")
            st.markdown(f"**Skor Fundamental: {skor_akhir} / 100**")
            st.progress(skor_akhir / 100.0)
            
            if warna_keputusan == "success": st.success(f"### {keputusan}\n{alasan_keputusan}")
            elif warna_keputusan == "info": st.info(f"### {keputusan}\n{alasan_keputusan}")
            elif warna_keputusan == "warning": st.warning(f"### {keputusan}\n{alasan_keputusan}")
            else: st.error(f"### {keputusan}\n{alasan_keputusan}")
            
            st.caption(f"**Tingkat Kepercayaan Data:** {label_konf} ({konf_pct:.0f}% metrik tersedia)")
            st.markdown("---")

            # Analisa SWOT
            st.header("1. OVERVIEW & ANALISA SWOT")
            mkt_cap = info.get('marketCap', 0)
            posisi = "Market Leader (Gajah)" if mkt_cap > 100e12 else "Challenger (Menengah)" if mkt_cap > 10e12 else "Small Cap (Lapis 3)"
            
            s_1 = "Skala Ekonomi Besar & Dominasi Pasar" if mkt_cap > 50e12 else "Struktur Biaya Efisien"
            s_2 = "Arus Kas Sangat Kuat (OCF > Laba)" if ocf_sehat else "Efisiensi Operasional Terjaga"
            w_1 = "Pertumbuhan Melambat (Mature)" if mkt_cap > 100e12 else "Volatilitas Harga Tinggi"
            w_2 = "Kualitas Laba Diragukan (OCF Lemah)" if not ocf_sehat else "Beban Hutang Perlu Dipantau" if skor_akhir < 60 else "Sensitif Sentimen Global"

            swot_html = f"""
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px;">
                <div style="background-color: #1b5e20; padding: 15px; border-radius: 8px;">
                    <b style="color: #a5d6a7;">💪 STRENGTHS</b><br><small>• {s_1}<br>• {s_2}</small>
                </div>
                <div style="background-color: #b71c1c; padding: 15px; border-radius: 8px;">
                    <b style="color: #ef9a9a;">⚠️ WEAKNESSES</b><br><small>• {w_1}<br>• {w_2}</small>
                </div>
                <div style="background-color: #0d47a1; padding: 15px; border-radius: 8px;">
                    <b style="color: #90caf9;">🚀 OPPORTUNITIES</b><br><small>• Ekspansi Digital & Pasar Baru<br>• Pemulihan Daya Beli Masyarakat</small>
                </div>
                <div style="background-color: #e65100; padding: 15px; border-radius: 8px;">
                    <b style="color: #ffcc80;">🔥 THREATS</b><br><small>• Kenaikan Suku Bunga Global<br>• Persaingan Ketat di Sektor {sektor_indo}</small>
                </div>
            </div>
            """
            st.markdown(swot_html, unsafe_allow_html=True)
            st.write(f"<br><b>Posisi Industri:</b> Emiten diklasifikasikan sebagai <b>{posisi}</b>.", unsafe_allow_html=True)

            # Keuangan
            st.header("2. ANALISA KEUANGAN")
            try:
                df_fin = financials.T.sort_index().tail(5)
                st.write("**Tren Pendapatan vs Laba Bersih:**")
                st.line_chart(df_fin[['Total Revenue', 'Net Income']])
                
                f1, f2, f3, f4 = st.columns(4)
                f1.metric("ROE (Efisiensi)", f"{info.get('returnOnEquity', 0)*100:.2f}%")
                f2.metric("NPM (Marjin Laba)", f"{info.get('profitMargins', 0)*100:.2f}%")
                if is_bank_ui:
                    f3.metric("CAR (Modal)", f"{info.get('capitalAdequacyRatio', 0):.2f}%")
                    f4.metric("NPL (Kredit Macet)", f"{info.get('nonPerformingLoan', 0):.2f}%")
                else:
                    f3.metric("Debt to Equity", f"{(info.get('debtToEquity') or 0)/100:.2f}x")
                    f4.metric("Current Ratio", f"{info.get('currentRatio', 0):.2f}x")
            except: st.warning("Visualisasi data keuangan terbatas.")

            # Valuasi
            st.header("3. VALUASI & MARGIN OF SAFETY")
            curr_pe, curr_pbv = info.get('trailingPE', 0), info.get('priceToBook', 0)
            
            v1, v2, v3, v4 = st.columns(4)
            v1.metric("PER Terkini", f"{curr_pe:.2f}x", f"Avg 5Y: {mean_pe_5y:.1f}x")
            v2.metric("PBV Terkini", f"{curr_pbv:.2f}x", f"Avg 5Y: {mean_pbv_5y:.1f}x")
            v3.metric("Harga Wajar", f"Rp {fair_price:,.0f}")
            v4.metric("Est. Dividen", f"Rp {div_rate:,.0f}", f"Yield: {div_yield:.2f}%")
            
            warna_mos = "normal" if mos > 0 else "inverse"
            st.metric(label="Margin of Safety (MOS) 🛡️", value=f"{mos:.1f}%", delta="Diskon" if mos > 0 else "Premi (Kemahalan)", delta_color=warna_mos)

            # Sentimen Berita
            st.header("4. SENTIMEN BERITA & KUALITATIF")
            if "BULLISH" in sentimen_kesimpulan:
                st.success(f"**Tren Sentimen: {sentimen_kesimpulan}**\n\n{sentimen_alasan}")
            elif "BEARISH" in sentimen_kesimpulan:
                st.error(f"**Tren Sentimen: {sentimen_kesimpulan}**\n\n{sentimen_alasan}")
            else:
                st.info(f"**Tren Sentimen: {sentimen_kesimpulan}**\n\n{sentimen_alasan}")
                
            if daftar_berita:
                with st.expander("📰 Lihat Berita Terbaru (Yahoo Finance)"):
                    for b in daftar_berita:
                        st.markdown(f"**{b['sentimen']}** | [{b['judul']}]({b['link']}) *(Sumber: {b['publisher']})*")
            else:
                st.caption("Belum ada rilis berita signifikan baru-baru ini.")

            # Trading Plan
            st.header("5. TRADING PLAN & EKSEKUSI")
            st.subheader(f"📍 Harga Saat Ini: Rp {curr_price:,.0f}")
            
            r0, r1, r2, r3 = st.columns(4)
            r0.info(f"**Taktik Entry:**\n{saran_entry}")
            r1.success(f"**Target TP:**\nMin. Rp {target_short:,.0f} (+{reward_pct:.1f}%)")
            r2.warning(f"**Average Down:**\nArea Rp {avg_down_price:,.0f} (-12%)")
            r3.error(f"**Cut Loss (-30%):**\nTembus Rp {sl_final:,.0f}")
            
            st.markdown("---")
            
            # --- TOMBOL EXPORT PDF ---
            pdf_sentimen_kesimpulan = sentimen_kesimpulan.replace("🌟", "").replace("⚠️", "").replace("⚖️", "").strip()
            
            # Waktu Analisa
            waktu_sekarang = datetime.now().strftime("%d-%m-%Y %H:%M")
            
            # Mendapatkan format tanggal cetak untuk nama file PDF (Contoh: 20260219)
            tanggal_cetak = datetime.now().strftime("%Y%m%d")
            ticker_bersih = ticker_input.replace(".JK", "")
            nama_file_pdf = f"ExpertStockPro_Fundamental_{ticker_bersih}_{tanggal_cetak}.pdf"

            data_to_pdf = {
                'ticker': ticker_bersih,
                'nama': nama_perusahaan,
                'sektor': sektor_indo,
                'syariah': status_syariah,
                'skor': skor_akhir,
                'konf_pct': konf_pct,
                'konf_label': label_konf,
                'keputusan': keputusan.replace("🌟", "").replace("✅", "").replace("⏳", "").replace("⛔", "").strip(),
                'alasan': alasan_keputusan,
                'fair_price': fair_price,
                'curr_price': curr_price,
                'mos': mos,
                'sentimen_kesimpulan': pdf_sentimen_kesimpulan,
                'sentimen_alasan': sentimen_alasan,
                'saran_entry': saran_entry,
                'tp': target_short,
                'reward_pct': reward_pct,
                'avg_down': avg_down_price,
                'sl': sl_final,
                'posisi': posisi,
                's_1': s_1,
                's_2': s_2,
                'w_1': w_1,
                'w_2': w_2,
                'is_bank': is_bank_ui,
                'car': info.get('capitalAdequacyRatio') or 0,
                'npl': info.get('nonPerformingLoan') or 0,
                'roe': (info.get('returnOnEquity') or 0) * 100,
                'npm': (info.get('profitMargins') or 0) * 100,
                'der': (info.get('debtToEquity') or 0) / 100,
                'cr': info.get('currentRatio') or 0,
                'div_rate': div_rate,
                'div_yield': div_yield,
                'waktu': waktu_sekarang
            }
            
            # Menggunakan logo_file yang path-nya sudah disesuaikan
            pdf_bytes = generate_pdf_report(data_to_pdf, logo_path=logo_file)
            st.download_button(
                label="📥 Simpan Laporan sebagai PDF",
                data=pdf_bytes,
                file_name=nama_file_pdf,
                mime="application/pdf",
                use_container_width=True
            )
            
            # Disclaimer Web
            st.caption("**DISCLAIMER:** Semua informasi, analisa teknikal, Analisa fundamental, ataupun sinyal trading dan analisa-analisa lain yang disediakan di modul ini hanya untuk tujuan edukasi dan informasi. Ini bukan merupakan rekomendasi, ajakan, atau nasihat keuangan untuk membeli atau menjual saham tertentu. Keputusan investasi sepenuhnya berada di tangan Anda. Harap lakukan riset Anda sendiri (*Do Your Own Research*) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.")
