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
    pdf.cell(0, 8, "1. SKOR FUNDAMENTAL & KEPUTUSAN", ln
