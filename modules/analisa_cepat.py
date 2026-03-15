import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from fpdf import FPDF
import os
import base64
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

# --- FUNGSI PEMBERSIH TEKS PDF ANTI-ERROR ---
def clean_pdf_text(text):
    """Menghapus karakter non-latin-1 agar tidak merusak FPDF"""
    return str(text).encode('latin-1', 'ignore').decode('latin-1')

# --- FUNGSI GENERATOR PDF ANALISA CEPAT ---
def export_analisa_cepat_to_pdf(ticker, company_name, sector, f_score, roe, lbl_solv, eps_g, rev_g,
                                t_score, avg_value_ma20, rsi, sentiment, curr_per, div_yield,
                                rekomen, curr, entry_bawah, entry_atas, tp, reward_pct, sl_final, risk_pct, alasan_tek,
                                modal_awal, maks_risiko, max_lot, alasan_lot, sl_note):
    pdf = FPDF()
    pdf.add_page()
    
    # Pembersihan Data Teks
    safe_company = clean_pdf_text(company_name)
    safe_sector = clean_pdf_text(sector).title()
    safe_lbl_solv = clean_pdf_text(lbl_solv)
    safe_sentiment = clean_pdf_text(sentiment)
    safe_rekomen = clean_pdf_text(rekomen)
    safe_alasan = clean_pdf_text(alasan_tek)
    
    # 1. HEADER BOX HITAM
    logo_path = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_path):
        logo_path = "../logo_expert_stock_pro.png"

    pdf.set_fill_color(20, 20, 20) 
    pdf.rect(0, 0, 210, 25, 'F')    
    
    if os.path.exists(logo_path):
        pdf.set_fill_color(218, 165, 32) 
        pdf.rect(10, 3, 19, 19, 'F')
        pdf.image(logo_path, x=10.5, y=3.5, w=18, h=18)
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    pdf.set_xy(35, 8) 
    pdf.cell(0, 10, "Expert Stock Pro - Analisa Cepat Pro", ln=True)
    
    pdf.set_y(28)
    
    # 2. HYPERLINK SUMBER
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(0, 0, 255)  
    pdf.cell(0, 5, "Sumber: https://bit.ly/sahampintar", ln=True, align='C', link="https://bit.ly/sahampintar")
    pdf.ln(2)
    
    # 3. NAMA SAHAM & PERUSAHAAN
    pdf.set_text_color(0, 0, 0) 
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 8, f"{ticker} - {safe_company}", ln=True, align='C')
    
    # 4. INFO SEKTOR & SYARIAH
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, f"Sektor: {safe_sector} | Status: Perlu Cek ISSI/JII", ln=True, align='C')
    pdf.ln(2)
    
    # 5. INFO TANGGAL & HARGA
    pdf.set_font("Arial", 'B', 10)
    waktu_analisa = datetime.now().strftime("%d-%m-%Y %H:%M WIB")
    pdf.cell(0, 5, f"Analisa: {waktu_analisa} | Harga: Rp {int(curr):,.0f}", ln=True, align='R')
    
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y()+2, 200, pdf.get_y()+2)
    pdf.ln(5)

    # --- 1. SKOR FUNDAMENTAL & TEKNIKAL ---
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(190, 8, "1. Ringkasan Skor & Sentimen", ln=True)
    pdf.set_font("Arial", '', 10)
    
    pdf.multi_cell(190, 6, f"- Fundamental Score: {f_score}/100 (ROE {roe:.1f}%, {safe_lbl_solv}, EPS Grw {eps_g:.1f}%, Rev Grw {rev_g:.1f}%)")
    pdf.multi_cell(190, 6, f"- Technical Score: {t_score:g}/100 (Trigger: {safe_alasan})")
    pdf.cell(190, 6, f"- Valuasi Dasar: PER {curr_per:.1f}x | Div. Yield {div_yield:.2f}%", ln=True)
    pdf.cell(190, 6, f"- Sentiment Pasar: {safe_sentiment}", ln=True)
    pdf.ln(4)

    # --- 2. TRADING PLAN & REKOMENDASI ---
    pdf.set_font("Arial", 'B', 11)
    
    if t_score < 70:
        pdf.cell(190, 8, "2. Rekomendasi & Trading Plan", ln=True)
    else:
        pdf.cell(190, 8, "2. Rekomendasi, Trading Plan & Sizing (RRR 1:2)", ln=True)
        
    pdf.set_font("Arial", '', 10)
    
    if t_score >= 85: pdf.set_text_color(0, 150, 0)
    elif t_score >= 70: pdf.set_text_color(200, 150, 0)
    else: pdf.set_text_color(200, 0, 0)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.multi_cell(190, 6, f">> {safe_rekomen} <<")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    pdf.ln(2)
    
    if t_score < 70:
        pdf.set_text_color(200, 0, 0) 
        pdf.multi_cell(190, 6, "Tidak Disarankan untuk Melakukan Trading dulu, karena belum didukung oleh indikator teknikal yang memadai.")
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.cell(190, 6, f"- Modal Maksimal: Rp {modal_awal:,.0f} | Risiko Maksimal: Rp {maks_risiko:,.0f}", ln=True)
        pdf.cell(190, 6, f"- Harga Sekarang: Rp {int(curr):,.0f}", ln=True)
        pdf.cell(190, 6, f"- Usulan Entry: Rp {int(entry_bawah):,.0f} - Rp {int(entry_atas):,.0f} (Buy on Weakness -1%)", ln=True)
        
        pdf.set_text_color(0, 128, 0) 
        pdf.cell(190, 6, f"- Take Profit (TP): Rp {tp:,.0f} (+{reward_pct:.1f}%)", ln=True)
        
        pdf.set_text_color(200, 0, 0) 
        pdf.cell(190, 6, f"- Stop Loss (SL): Rp {sl_final:,.0f} (-{risk_pct:.1f}%){sl_note}", ln=True)
        
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 6, f"- Max Lot Pembelian: {max_lot} Lot ({alasan_lot})", ln=True)
        pdf.set_font("Arial", '', 10)
        
    pdf.ln(10)

    # --- FOOTER & DISCLAIMER ---
    pdf.set_y(-35)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, "DISCLAIMER:", ln=True) 
    pdf.set_font("Arial", 'I', 7)
    disclaimer_text = clean_pdf_text("Semua informasi, analisa teknikal, analisa fundamental, ataupun sinyal trading dan analisa-analisa lain "
                       "yang disediakan di modul ini hanya untuk tujuan edukasi dan informasi. Ini bukan merupakan rekomendasi, "
                       "ajakan, atau nasihat keuangan untuk membeli atau menjual saham tertentu. Keputusan investasi sepenuhnya "
                       "berada di tangan Anda. Harap lakukan riset Anda sendiri (Do Your Own Research) dan pertimbangkan "
                       "profil risiko sebelum mengambil keputusan di pasar modal.")
    pdf.multi_cell(190, 4, disclaimer_text)

    return pdf.output(dest='S').encode('latin-1', 'ignore')

# -----------------------------------------------------

def run_analisa_cepat():
    # --- TAMPILAN WEB & LOGO ---
    logo_file = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_file):
        logo_file = "../logo_expert_stock_pro.png"
        
    if os.path.exists(logo_file):
        with open(logo_file, "rb") as f:
            data = f.read()
            encoded_img = base64.b64encode(data).decode()
        
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; margin-bottom: 10px;">
                <img src="data:image/png;base64,{encoded_img}" width="150">
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown("<h1 style='text-align: center;'>Analisa Cepat Pro</h1>", unsafe_allow_html=True)
    else:
        st.markdown("<h1 style='text-align: center;'>Analisa Cepat Pro</h1>", unsafe_allow_html=True)
        st.warning("⚠️ File logo belum ditemukan.")
        
    st.markdown("---")

    # --- FORM INPUT ---
    st.markdown("### ⚙️ Konfigurasi Manajemen Risiko")
    col_inp1, col_inp2, col_inp3 = st.columns([1, 1, 1])
    with col_inp1:
        ticker_input = st.text_input("Kode Saham (Quick Scan):", value="BBCA").upper()
    with col_inp2:
        modal_awal = st.number_input("Total Modal Trading (Rp):", min_value=100000, value=10000000, step=500000)
    with col_inp3:
        maks_risiko = st.number_input("Maks. Nominal Risiko (Rp):", min_value=10000, value=500000, step=50000)

    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"
    st.markdown("<br>", unsafe_allow_html=True)

    if st.button(f"Jalankan Analisa {ticker_input}", type="primary"):
        with st.spinner("Mengkalkulasi indikator teknikal & fundamental..."):
            # --- 1. STANDAR ANTI-ERROR ---
            data = get_full_stock_data(ticker)
            info = data['info']
            df = data['history']
            financials = data.get('financials', pd.DataFrame()) 
            cashflow = data.get('cashflow', pd.DataFrame()) 
            
            if df.empty or not info:
                st.error("Data gagal dimuat. Mohon tunggu 1 menit lalu 'Clear Cache' di pojok kanan atas.")
                return

            # --- 2. DATA TEKNIKAL & INDIKATOR SCORING ---
            df['MA20'] = df['Close'].rolling(20).mean()
            df['MA50'] = df['Close'].rolling(50).mean()
            df['MA200'] = df['Close'].rolling(200).mean()
            
            df['Value'] = df['Close'] * df['Volume']
            avg_value_ma20 = df['Value'].rolling(20).mean().iloc[-1]
            df['Vol_MA20'] = df['Volume'].rolling(20).mean()
            
            df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['VWAP_20'] = (df['Typical_Price'] * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()

            df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
            df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
            
            # Tambahan kalkulasi indikator pelengkap
            df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
            df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = df['EMA12'] - df['EMA26']
            df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df['RSI'] = 100 - (100 / (1 + (gain/loss)))

            curr = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            
            # --- MENGEMBALIKAN VARIABEL YANG HILANG ---
            ma200_val = 0 if pd.isna(df['MA200'].iloc[-1]) else df['MA200'].iloc[-1]
            ma50_val = 0 if pd.isna(df['MA50'].iloc[-1]) else df['MA50'].iloc[-1]
            ema9_val = df['EMA9'].iloc[-1]
            ema21_val = df['EMA21'].iloc[-1]
            vwap_val = 0 if pd.isna(df['VWAP_20'].iloc[-1]) else df['VWAP_20'].iloc[-1]
            
            vol_curr = df['Volume'].iloc[-1]
            vol_ma20 = df['Vol_MA20'].iloc[-1]
            
            macd_val = df['MACD'].iloc[-1]
            signal_val = df['Signal'].iloc[-1]
            rsi_curr = df['RSI'].iloc[-1]
            
            # --- 3. SCORING FUNDAMENTAL ---
            f_score = 0
            sector = info.get('sector', '')
            industry = info.get('industry', '')
            
            is_bank = 'Bank' in industry or sector == 'Financial Services'
            is_infra = 'Infrastructure' in industry or sector in ['Utilities', 'Real Estate', 'Industrials', 'Energy', 'Basic Materials']
            
            der_ratio = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
            lbl_solv = ""
            car, npl = 0, 0

            if is_bank:
                car = info.get('capitalAdequacyRatio', 18) 
                if car > 20: f_score += 10
                elif car >= 15: f_score += 5
                
                npl = info.get('nonPerformingLoan', 2.5)   
                if npl < 2: f_score += 10
                elif npl <= 3.5: f_score += 5
                lbl_solv = f"CAR {car:.1f}% | NPL {npl:.1f}%"
                
            elif is_infra:
                if der_ratio < 1.5: f_score += 10
                elif der_ratio <= 2.5: f_score += 5
                
                icr = 2.0 
                try:
                    ebit = financials.loc['EBIT'].iloc[0] if 'EBIT' in financials.index else (financials.loc['Operating Income'].iloc[0] if 'Operating Income' in financials.index else 0)
                    interest = abs(financials.loc['Interest Expense'].iloc[0]) if 'Interest Expense' in financials.index else 0
                    if interest > 0: icr = ebit / interest
                except: pass
                
                if icr > 3.0: f_score += 10
                elif icr >= 1.5: f_score += 5
                lbl_solv = f"DER {der_ratio:.2f}x | ICR {icr:.1f}x"
                
            else: 
                if der_ratio < 0.5: f_score += 10
                elif der_ratio <= 1.0: f_score += 5
                
                cr = info.get('currentRatio', 0)
                if cr > 1.5: f_score += 10
                elif cr >= 1.0: f_score += 5
                lbl_solv = f"DER {der_ratio:.2f}x | CR {cr:.2f}x"

            roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0
            if roe > 15: f_score += 10
            elif roe >= 10: f_score += 5
            
            npm = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0
            if npm > 10: f_score += 10
            elif npm >= 5: f_score += 5

            try:
                mean_pe_5y = info.get('trailingPE', 15) * 0.95 
                mean_pbv_5y = info.get('priceToBook', 1.5) * 0.9 
            except: 
                mean_pe_5y, mean_pbv_5y = 15.0, 1.5

            curr_per = info.get('trailingPE', 0)
            if curr_per > 0 and mean_pe_5y > 0:
                pe_discount = ((mean_pe_5y - curr_per) / mean_pe_5y) * 100
                if pe_discount > 20: f_score += 10
                elif pe_discount >= 0: f_score += 5
            
            curr_pbv = info.get('priceToBook', 0)
            if curr_pbv > 0 and mean_pbv_5y > 0:
                pbv_discount = ((mean_pbv_5y - curr_pbv) / mean_pbv_5y) * 100
                if pbv_discount > 20: f_score += 10
                elif pbv_discount >= 0: f_score += 5

            eps_g = info.get('earningsGrowth', 0) * 100 if info.get('earningsGrowth') else 0
            if eps_g > 15: f_score += 10
            elif eps_g >= 5: f_score += 7
            elif eps_g > 0: f_score += 3
            
            rev_g = info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0
            if rev_g > 10: f_score += 10
            elif rev_g >= 0: f_score += 5

            ocf = 0
            try:
                if not cashflow.empty and not financials.empty:
                    ocf = cashflow.loc['Operating Cash Flow'].iloc[0] if 'Operating Cash Flow' in cashflow.index else 0
                    net_income = financials.loc['Net Income'].iloc[0] if 'Net Income' in financials.index else 0
                    if ocf > net_income: f_score += 10
                    elif ocf > 0: f_score += 5
            except: pass

            div_yield = hitung_div_yield_normal(info)
            if div_yield > 5:
