import streamlit as st
import yfinance as yf
import pandas as pd

# --- CACHE 1: KHUSUS HARGA & CHART (Ringan & Cepat) ---
@st.cache_data(ttl=3600, show_spinner=False)
def ambil_data_history(ticker, period="1y"):
    """Hanya mengambil data harga OHLCV. Jarang error."""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        # Bersihkan timezone agar kompatibel dengan plot
        if not df.empty:
            df.index = df.index.tz_localize(None)
        return df
    except Exception:
        return pd.DataFrame()

# --- CACHE 2: KHUSUS FUNDAMENTAL (Berat) ---
@st.cache_data(ttl=3600, show_spinner=False)
def ambil_data_fundamental_lengkap(ticker):
    """Mengambil Info, Financials, Balance Sheet dengan Error Handling per item."""
    stock = yf.Ticker(ticker)
    
    # 1. Info (Profil & Rasio)
    try:
        info = stock.info
    except:
        info = {}

    # 2. Laporan Laba Rugi (Income Statement)
    try:
        financials = stock.financials
        if financials.empty:
            financials = stock.income_stmt
    except:
        financials = pd.DataFrame()

    # 3. Neraca (Balance Sheet)
    try:
        balance_sheet = stock.balance_sheet
    except:
        balance_sheet = pd.DataFrame()

    return info, financials, balance_sheet

# --- CACHE 3: KHUSUS DIVIDEN (TARUH DI BAGIAN BAWAH FILE) ---
@st.cache_data(ttl=3600, show_spinner=False)
def ambil_data_dividen_lengkap(ticker):
    """
    Mengambil data khusus untuk analisa dividen:
    1. Riwayat Dividen (Series)
    2. Info (Yield, Payout Ratio)
    3. Cashflow (Untuk cek sustainability)
    4. Financials (Untuk cek Laba Bersih)
    """
    stock = yf.Ticker(ticker)
    
    # 1. Info
    try: info = stock.info
    except: info = {}

    # 2. Riwayat Dividen
    try: dividends = stock.dividends
    except: dividends = pd.Series(dtype='float64')

    # 3. Cash Flow (Penting untuk cek uang tunai vs dividen)
    try: cashflow = stock.cashflow
    except: cashflow = pd.DataFrame()

    # 4. Financials (Untuk Payout Ratio manual)
    try: financials = stock.financials
    except: financials = pd.DataFrame()

    # 5. History Harga (Untuk yield historis)
    try: history = stock.history(period="1y")
    except: history = pd.DataFrame()

    return info, dividends, cashflow, financials, history
