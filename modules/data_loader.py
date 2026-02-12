import streamlit as st
import yfinance as yf
import pandas as pd

# --- FUNGSI PEMBANTU (Helper) ---
def hitung_div_yield_normal(info):
    """Mencegah angka dividen aneh (seperti 40900%)"""
    raw_yield = info.get('dividendYield')
    if raw_yield is None: return 0.0
    # Jika angka > 1 (misal 4.5), Yahoo sudah kasih dalam persen. 
    # Jika < 1 (misal 0.045), Yahoo kasih dalam desimal, harus dikali 100.
    return float(raw_yield) if raw_yield > 1 else float(raw_yield * 100)

# --- SATU PINTU DATA (Anti-Rate Limit) ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_full_stock_data(ticker):
    """
    Mengambil semua data sekaligus (History, Info, Financials, Dividen) 
    dalam satu kali ketuk pintu ke Yahoo Finance.
    """
    stock = yf.Ticker(ticker)
    data = {
        "info": {},
        "history": pd.DataFrame(),
        "financials": pd.DataFrame(),
        "balance_sheet": pd.DataFrame(),
        "cashflow": pd.DataFrame(),
        "dividends": pd.Series(dtype='float64')
    }

    # 1. Ambil History (Data Utama)
    try:
        df = stock.history(period="2y")
        if not df.empty:
            df.index = df.index.tz_localize(None)
            data["history"] = df
    except: pass

    # 2. Ambil Info (Fundamental & Profil)
    try:
        data["info"] = stock.info
    except: pass

    # 3. Ambil Laporan Keuangan & Cashflow
    try:
        data["financials"] = stock.financials
        data["balance_sheet"] = stock.balance_sheet
        data["cashflow"] = stock.cashflow
    except: pass

    # 4. Ambil Riwayat Dividen
    try:
        data["dividends"] = stock.dividends
    except: pass

    return data
