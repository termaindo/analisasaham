import streamlit as st
import yfinance as yf
import pandas as pd

# --- FUNGSI PEMBANTU (Helper) ---
def hitung_div_yield_normal(info):
    """Mencegah angka dividen aneh (seperti 40900%)"""
    raw_yield = info.get('dividendYield')
    if raw_yield is None: return 0.0
    # Normalisasi: Jika > 1 berarti persen, jika < 1 berarti desimal
    return float(raw_yield) if raw_yield > 1 else float(raw_yield * 100)

# --- SATU PINTU DATA (Anti-Rate Limit) ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_full_stock_data(ticker):
    """
    Satu kali panggil untuk semua kebutuhan menu.
    """
    stock = yf.Ticker(ticker)
    data = {
        "info": {},
        "history": pd.DataFrame(),
        "financials": pd.DataFrame(),
        "balance_sheet": pd.DataFrame(),
        "cashflow": pd.DataFrame()
    }

    # Ambil History 2 Tahun
    try:
        df = stock.history(period="2y")
        if not df.empty:
            df.index = df.index.tz_localize(None)
            data["history"] = df
    except: pass

    # Ambil Info & Laporan Keuangan
    try:
        data["info"] = stock.info
        data["financials"] = stock.financials
        data["balance_sheet"] = stock.balance_sheet
        data["cashflow"] = stock.cashflow
    except: pass

    return data
