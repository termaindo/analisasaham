import streamlit as st
import yfinance as yf
import pandas as pd

# --- FUNGSI TEKNIKAL & UMUM ---
@st.cache_data(ttl=3600, show_spinner=False)
def ambil_data_saham(ticker, period="1y"):
    stock = yf.Ticker(ticker)
    try:
        history = stock.history(period=period)
        info = stock.info
    except:
        history = pd.DataFrame()
        info = {}
    return history, info

@st.cache_data(ttl=3600, show_spinner=False)
def ambil_data_dividen(ticker):
    stock = yf.Ticker(ticker)
    try:
        dividends = stock.dividends
        info = stock.info
        return dividends, info
    except:
        return None, None

# --- FUNGSI KHUSUS FUNDAMENTAL MENDALAM (NEW) ---
@st.cache_data(ttl=3600, show_spinner=False)
def ambil_data_fundamental_lengkap(ticker):
    """
    Mengambil data Info, Income Statement, Balance Sheet, dan Cash Flow
    secara terpusat agar stabil dan anti-error.
    """
    stock = yf.Ticker(ticker)
    
    # 1. Info Perusahaan
    try:
        info = stock.info
    except:
        info = {}

    # 2. Laporan Keuangan (Income Statement)
    try:
        financials = stock.financials
        if financials.empty:
            financials = stock.income_stmt # Coba alias lain
    except:
        financials = pd.DataFrame()

    # 3. Neraca (Balance Sheet)
    try:
        balance_sheet = stock.balance_sheet
    except:
        balance_sheet = pd.DataFrame()
        
    # 4. Arus Kas (Cash Flow)
    try:
        cashflow = stock.cashflow
    except:
        cashflow = pd.DataFrame()

    # 5. History Harga (Untuk Validasi)
    try:
        history = stock.history(period="1mo")
    except:
        history = pd.DataFrame()

    return info, financials, balance_sheet, cashflow, history
