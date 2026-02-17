import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from fpdf import FPDF
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

# --- FUNGSI FALLBACK SCRAPING RASIO BANK ---
def get_bank_ratios_fallback(ticker):
    """
    Mencoba melakukan scraping data CAR dan NPL dari portal finansial.
    Mengembalikan tuple (car_val, npl_val). Jika gagal, mengembalikan (None, None).
    """
    clean_ticker = ticker.replace(".JK", "").upper()
    car_val, npl_val = None, None
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        url = f"https://www.idnfinancials.com/{clean_ticker}/financial-ratios"
        res = requests.get(url, headers=headers, timeout=5)
        
        if res.status_code == 200:
            tables = pd.read_html(res.text)
            for df in tables:
                if len(df.columns) > 1:
                    for _, row in df.iterrows():
                        col_name = str(row[0]).lower()
                        if 'capital adequacy' in col_name or 'car' in col_name:
                            car_val = pd.to_numeric(str(row[1]).replace('%', '').strip(), errors='coerce')
                        elif 'non-performing' in col_name or 'npl' in col_name:
                            npl_val = pd.to_numeric(str(row[1]).replace('%', '').strip(), errors='coerce')
    except Exception:
        pass
        
    return car_val, npl_val

# --- FUNGSI GENERATOR PDF ANALISA CEPAT ---
def export_analisa_cepat_to_pdf(ticker, company_name, sector, f_score, roe, lbl_solv, eps_g, rev_g,
                                t_score, avg_value_ma20, rsi, sentiment, curr_per, div_yield,
                                rekomen, curr, entry_bawah, entry_atas, tp, reward_pct, sl_final, risk_pct, alasan_tek):
    pdf = FPDF()
    pdf.add_page()
    
    # --- HEADER APLIKASI ---
    pdf.set_font("Arial", 'B', 18)
    pdf.set_text_color(30, 136, 229) 
    pdf.cell(190, 10, "EXPERT STOCK PRO", ln=True, align='C')
    
    pdf.set_font("Arial", 'B', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(190, 5, "Quantitative Quick Analysis Report", ln=True, align='C')
    
    pdf.set_font("Arial", 'I', 9)
    pdf.cell(190, 6, f"Dihasilkan pada: {datetime.now().strftime('%d-%m-%Y %H:%M WIB')}", ln=True, align='C')
    pdf.ln(2)
    
    # --- AKSES APLIKASI ---
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(40, 6, "Akses Full App:", 0)
    pdf.set_font("Arial", 'U', 10)
    pdf.set_text_color(0, 0, 255)
    pdf.cell(150, 6, "lynk.id/hahastoresby", ln=True, link="https://lynk.id/hahastoresby")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y()) 
    pdf.ln(5)

    # --- INFORMASI SAHAM ---
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(190, 10, f" {company_name} ({ticker})", 0, ln=True, fill=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(190, 8, f" Sektor: {sector.title()} | Syariah: Perlu Cek ISSI/JII", ln=True)
    pdf.ln(3)

    # --- 1. SKOR FUNDAMENTAL & TEKNIKAL ---
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "1. Ringkasan Skor & Sentimen", ln=True)
    pdf.set_font("Arial", '', 10)
    
    safe_lbl_solv = str(lbl_solv).encode('ascii', 'ignore').decode('ascii')
    safe_sentiment = str(sentiment).encode('ascii', 'ignore').decode('ascii')
    
    pdf.multi_cell(190, 6, f"- Fundamental Score: {f_score}/100 (ROE {roe:.1f}%, {safe_lbl_solv}, EPS Grw {eps_g:.1f}%, Rev Grw {rev_g:.1f}%)")
    pdf.multi_cell(190, 6, f"- Technical Score: {t_score:g}/100 (Trigger: {alasan_tek})")
    pdf.cell(190, 6, f"- Valuasi Dasar: PER {curr_per:.1f}x | Div. Yield {div_yield:.2f}%", ln=True)
    pdf.cell(190, 6, f"- Sentiment Pasar: {safe_sentiment}", ln=True)
    pdf.ln(4)

    # --- 2. TRADING PLAN & REKOMENDASI ---
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "2. Rekomendasi & Trading Plan (Swing Mode)", ln=True)
    pdf.set_font("Arial", '', 10)
    
    if "All-in" in rekomen: pdf.set_text_color(0, 150, 0)
    elif "Dicicil" in rekomen: pdf.set_text_color(200, 150, 0)
    else: pdf.set_text_color(200, 0, 0)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.multi_cell(190, 6, f">> {rekomen} <<")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    pdf.ln(2)
    
    pdf.cell(190, 6, f"- Harga Sekarang: Rp {int(curr):,.0f}", ln=True)
    pdf.cell(190, 6, f"- Usulan Entry: Rp {int(entry_bawah):,.0f} - Rp {int(entry_atas):,.0f} (Maks -4% / EMA9)", ln=True)
    
    pdf.set_text_color(0, 128, 0) 
    pdf.cell(190, 6, f"- Take Profit (TP): Rp {tp:,.0f} (+{reward_pct:.1f}%)", ln=True)
    
    pdf.set_text_color(200, 0, 0) 
    pdf.cell(190, 6, f"- Stop Loss (SL): Rp {sl_final:,.0f} (-{risk_pct:.1f}%)", ln=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)

    # --- FOOTER & DISCLAIMER ---
    pdf.set_y(-30)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, "DISCLAIMER:", ln=True) 
    pdf.set_font("Arial", 'I', 7)
    disclaimer_text = ("Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma indikator teknikal "
                       "dan fundamental. Seluruh informasi yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau "
                       "paksaan untuk membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi tanggung jawab "
                       "pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik dan DYOR.")
    pdf.multi_cell(190, 4, disclaimer_text)

    return pdf.output(dest='S').encode('latin-1', 'ignore')

# -----------------------------------------------------

def run_analisa_cepat():
    st.title("⚡ Analisa Cepat Pro")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Quick Scan):", value="BBCA").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Jalankan Analisa {ticker_input}"):
        with st.spinner("Mengkalkulasi indikator teknikal & fundamental..."):
            # --- 1. STANDAR ANTI-ERROR ---
            data = get_full_stock_data(ticker)
            info = data['info']
            df = data['history']
            financials = data.get('financials', pd.DataFrame()) 
            
            if df.empty or not info:
                st.error("Data gagal dimuat. Mohon tunggu 1 menit lalu 'Clear Cache' di pojok kanan atas.")
                return

            # --- 2. DATA TEKNIKAL & INDIKATOR SCORING ---
            df['MA50'] = df['Close'].rolling(50).mean()
            df['MA200'] = df['Close'].rolling(200).mean()
            
            # Hitung Value Transaksi
            df['Value'] = df['Close'] * df['Volume']
            avg_value_ma20 = df['Value'].rolling(20).mean().iloc[-1]

            # Indikator Teknikal Baru
            df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
            df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()

            # Kalkulasi RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df['RSI'] = 100 - (100 / (1 + (gain/loss)))

            # Cek ketersediaan data
            ma200_val = 0 if pd.isna(df['MA200'].iloc[-1]) else df['MA200'].iloc[-1]
            ma50_val = 0 if pd.isna(df['MA50'].iloc[-1]) else df['MA50'].iloc[-1]
            ema9_val = df['EMA9'].iloc[-1]
            ema21_val = df['EMA21'].iloc[-1]
            rsi_curr = df['RSI'].iloc[-1]
            rsi_prev = df['RSI'].iloc[-2]
            
            curr = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            prev_high = df['High'].iloc[-2]
            
            # --- 3. SCORING FUNDAMENTAL & TEKNIKAL ---
            f_score = 0
            t_score = 0
            
            # === A. PENILAIAN FUNDAMENTAL (Skala 100 Poin) ===
            sector = str(info.get('sector', '')).lower()
            industry = str(info.get('industry', '')).lower()
            name = str(info.get('longName', '')).lower()
            
            is_bank = 'bank' in industry or 'bank' in sector or 'bank' in name or sector == 'financial services'
            is_infra = 'infrastructure' in industry or sector in ['utilities', 'real estate', 'industrials'] or 'construction' in industry or 'karya' in name
            
            raw_der = info.get('debtToEquity', 0)
            der_ratio = raw_der / 100 if raw_der > 10 else raw_der

            lbl_solv = ""
            car_approx, npl_approx = 0, 0
            car_scraped, npl_scraped = None, None
