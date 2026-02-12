import streamlit as st
import yfinance as yf

# Fungsi ini menyimpan data di memori (Cache) selama 1 jam (3600 detik)
# Sehingga tidak perlu bolak-balik minta ke Yahoo Finance
@st.cache_data(ttl=3600, show_spinner=False)
def ambil_data_saham(ticker, period="1y"):
    """
    Mengambil data history dan info saham dengan caching.
    """
    stock = yf.Ticker(ticker)
    
    # Ambil history
    history = stock.history(period=period)
    
    # Ambil info (Fundamental/Dividen)
    # Kita gunakan try-except agar jika info gagal, history tetap bisa dipakai
    try:
        info = stock.info
    except:
        info = {}
        
    return history, info

@st.cache_data(ttl=3600, show_spinner=False)
def ambil_data_dividen(ticker):
    """
    Khusus untuk mengambil data dividen
    """
    stock = yf.Ticker(ticker)
    try:
        dividends = stock.dividends
        info = stock.info
        return dividends, info
    except:
        return None, None
