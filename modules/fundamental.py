import streamlit as st
import pandas as pd
import numpy as np
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal
from modules.universe import is_syariah  # --- MODIFIKASI: Memanggil fungsi dari universe.py ---

def translate_sector(sector_en):
    """Menerjemahkan sektor ke Bahasa Indonesia"""
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

def hitung_skor_fundamental(info, financials, mean_pe_5y, mean_pbv_5y, div_yield):
    """Menghitung skor fundamental (Maks 100) berdasarkan sektor & metrik dinamis"""
    skor = 0
    total_metrik = 7
    metrik_tersedia = 0
    
    sector = info.get('sector', '')
    industry = info.get('industry', '')
    
    # Deteksi Sektor
    is_bank = 'Bank' in industry or sector == 'Financial Services'
    is_infra = 'Infrastructure' in industry or sector in ['Utilities', 'Real Estate', 'Industrials']
    
    # --- 1. KESEHATAN KEUANGAN (Maks 25) ---
    if is_bank:
        if info.get('capitalAdequacyRatio') is not None: metrik_tersedia += 1
        car = info.get('capitalAdequacyRatio', 18) 
        npl = info.get('nonPerformingLoan', 2.5)   
        
        if car > 20: skor += 15
        elif car >= 15: skor += 10
        elif car >= 10: skor += 5
        
        if npl < 2: skor += 10
        elif npl <= 3.5: skor += 5
        
    elif is_infra:
        if info.get('debtToEquity') is not None: metrik_tersedia += 1
        der = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
        if der < 1.5: skor += 15
        elif der <= 2.5: skor += 10
        elif der <= 4.0: skor += 5
        
        icr = 2.0 
        try:
            ebit = financials.loc['EBIT'].iloc[0]
            interest = abs(financials.loc['Interest Expense'].iloc[0])
            if interest > 0: icr = ebit / interest
        except:
            pass
            
        if icr > 3.0: skor += 10
        elif icr >= 1.5: skor += 5
        
    else: 
        if info.get('debtToEquity') is not None: metrik_tersedia += 1
        der = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
        if der < 0.5: skor += 15
        elif der <= 1.0: skor += 10
        elif der <= 2.0: skor += 5
        
        cr = info.get('currentRatio', 0)
        if cr > 1.5: skor += 10
        elif cr >= 1.0: skor += 5

    # --- 2. PROFITABILITAS (Maks 25) ---
    if info.get('returnOnEquity') is not None: metrik_tersedia += 1
    roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0
    if roe > 15: skor += 15
    elif roe >= 10: skor += 10
    elif roe >= 5: skor += 5
    
    if info.get('profitMargins') is not None: metrik_tersedia += 1
    npm = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0
    if npm > 10: skor += 10
    elif npm >= 5: skor += 5

    # --- 3. VALUASI DINAMIS (Maks 20) ---
    if info.get('trailingPE') is not None: metrik_tersedia += 1
    per = info.get('trailingPE', 0)
    
    if info.get('priceToBook') is not None: metrik_tersedia += 1
    pbv = info.get('priceToBook', 0)
    
    if per > 0 and mean_pe_5y > 0:
        pe_discount = ((mean_pe_5y - per) / mean_pe_5y) * 100
        if pe_discount > 20: skor += 10
        elif pe_discount >= 0: skor += 7
        elif pe_discount >= -20: skor += 3
    
    if pbv > 0 and mean_pbv_5y > 0:
        pbv_discount = ((mean_pbv_5y - pbv) / mean_pbv_5y) * 100
        if pbv_discount > 20: skor += 10
        elif pbv_discount >= 0: skor += 7
        elif pbv_discount >= -20: skor += 3

    # --- 4. PERTUMBUHAN / GROWTH (Maks 20) ---
    if info.get('earningsGrowth') is not None: metrik_tersedia += 1
    eps_g = info.get('earningsGrowth', 0) * 100 if info.get('earningsGrowth') else 0
    if eps_g > 15: skor += 10
    elif eps_g >= 5: skor += 7
    elif eps_g >= 0: skor += 3
    
    if info.get('revenueGrowth') is not None: metrik_tersedia += 1
    rev_g = info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0
    if rev_g > 10: skor += 10
    elif rev_g >= 0: skor += 5

    # --- 5. DIVIDEN (Maks 10) ---
    if div_yield > 5: skor += 10
    elif div_yield >= 2: skor += 5

    # --- KLASIFIKASI AKHIR ---
    if skor >= 80: kelas = "Strong Buy (Fundamental Sangat Sehat & Undervalued)"
    elif skor >= 60: kelas = "Investable / Accumulate (Fundamental Baik)"
    elif skor >= 40: kelas = "Watchlist / Hold (Pas-pasan atau Kemahalan)"
    else: kelas = "High Risk / Sell (Risiko Tinggi)"
    
    # --- LEVEL KONFIDENSI ---
    konf_pct = (metrik_tersedia / total_metrik) * 100
    if konf_pct >= 85: label_konf = "🟢 Tinggi (Data Lengkap)"
    elif konf_pct >= 50: label_konf = "🟡 Sedang (Sebagian Data Kosong)"
    else: label_konf = "🔴 Rendah (Hati-hati, Data Kurang Memadai)"
    
    return skor, kelas, konf_pct, label_konf

def run_fundamental():
    st.title("🏛️ Analisa Fundamental Pro (Deep Value Investigation)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="ASII").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st
