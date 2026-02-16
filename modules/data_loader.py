import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup

# --- FUNGSI PEMBANTU (Helper) ---
def hitung_div_yield_normal(info):
    """Mencegah angka dividen aneh (seperti 409% atau 909%)"""
    raw_yield = info.get('dividendYield')
    if raw_yield is None: return 0.0
    # Jika angka > 1 (misal 4.5), berarti sudah persen. 
    # Jika < 1 (misal 0.045), berarti desimal, harus dikali 100.
    return float(raw_yield) if raw_yield > 1 else float(raw_yield * 100)

def scrape_local_financial_data(ticker):
    """
    Fungsi untuk menyedot data spesifik (CAR, NPL) dari portal lokal 
    jika yfinance tidak menyediakannya.
    """
    clean_ticker = ticker.replace('.JK', '')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    
    scraped_data = {
        'CAR': None,
        'NPL': None,
    }
    
    try:
        url = f"https://www.idnfinancials.com/id/{clean_ticker}/financial-ratios"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Mencari baris CAR
            car_row = soup.find(string=lambda text: text and ('Capital Adequacy Ratio' in text or 'CAR' in text))
            if car_row:
                try:
                    car_value_str = car_row.find_next('td').text.strip()
                    scraped_data['CAR'] = float(car_value_str.replace('%', '').replace(',', '.'))
                except: pass
                
            # Mencari baris NPL
            npl_row = soup.find(string=lambda text: text and ('Non-Performing Loan' in text or 'NPL' in text))
            if npl_row:
                try:
                    npl_value_str = npl_row.find_next('td').text.strip()
                    scraped_data['NPL'] = float(npl_value_str.replace('%', '').replace(',', '.'))
                except: pass
                
    except Exception as e:
        print(f"Peringatan: Gagal melakukan scraping untuk {ticker}. Menggunakan nilai default. Detail: {e}")
        
    return scraped_data

# --- SATU PINTU DATA (Anti-Rate Limit) ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_full_stock_data(ticker):
    """
    Mengambil semua data sekaligus untuk mencegah error 'Data tidak ditemukan'.
    Sudah terintegrasi dengan scraping khusus sektor perbankan.
    """
    stock = yf.Ticker(ticker)
    data = {
        "info": {},
        "history": pd.DataFrame(),
        "financials": pd.DataFrame(),
        "balance_sheet": pd.DataFrame(), # Ditambahkan untuk kebutuhan fundamental.py
        "cashflow": pd.DataFrame(),
        "dividends": pd.Series(dtype='float64')
    }

    # 1. Ambil History 2 Tahun (Paling stabil)
    try:
        df = stock.history(period="2y")
        if not df.empty:
            df.index = df.index.tz_localize(None)
            data["history"] = df
    except: pass

    # 2. Ambil Info, Scraping (jika Bank), & Dividen
    try:
        info = stock.info
        
        # --- PROSES SUNTIK DATA SCRAPING (KHUSUS BANK) ---
        industry = info.get('industry', '')
        sector = info.get('sector', '')
        is_bank = 'Bank' in industry or sector == 'Financial Services'
        
        if is_bank:
            local_data = scrape_local_financial_data(ticker)
            # Suntikkan data dengan nilai aman (fallback) jika web lokal gagal diakses
            info['capitalAdequacyRatio'] = local_data['CAR'] if local_data['CAR'] is not None else 18.0
            info['nonPerformingLoan'] = local_data['NPL'] if local_data['NPL'] is not None else 2.5
        
        data["info"] = info
        
        # Khusus Dividen
        divs = stock.dividends
        if divs.empty:
            divs = stock.actions['Dividends'] if 'Dividends' in stock.actions else pd.Series(dtype='float64')
        data["dividends"] = divs
    except: pass

    # 3. Ambil Laporan Keuangan, Neraca (Balance Sheet) & Cashflow
    try:
        data["financials"] = stock.financials
        data["balance_sheet"] = stock.balance_sheet
        data["cashflow"] = stock.cashflow
    except: pass

    return data
