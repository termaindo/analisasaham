import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- FUNGSI PEMBANTU (Helper) ---
def hitung_div_yield_normal(info):
    """Mencegah angka dividen aneh (seperti 409% atau 909%)"""
    raw_yield = info.get('dividendYield')
    if raw_yield is None: return 0.0
    # Jika angka > 1 (misal 4.5), berarti sudah persen. 
    # Jika < 1 (misal 0.045), berarti desimal, harus dikali 100.
    return float(raw_yield) if raw_yield > 1 else float(raw_yield * 100)

# --- SATU PINTU DATA (Anti-Rate Limit) ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_full_stock_data(ticker):
    """
    Mengambil semua data sekaligus untuk mencegah error 'Data tidak ditemukan'.
    """
    stock = yf.Ticker(ticker)
    data = {
        "info": {},
        "history": pd.DataFrame(),
        "financials": pd.DataFrame(),
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

    # 2. Ambil Info & Dividen (Raw)
    try:
        data["info"] = stock.info
        # Khusus Dividen: Jika properti .dividends kosong, coba ambil dari .actions
        divs = stock.dividends
        if divs.empty:
            divs = stock.actions['Dividends'] if 'Dividends' in stock.actions else pd.Series()
        data["dividends"] = divs
    except: pass

    # 3. Ambil Laporan Keuangan & Cashflow
    try:
        data["financials"] = stock.financials
        data["cashflow"] = stock.cashflow
    except: pass

    return data
