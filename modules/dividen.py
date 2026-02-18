import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from fpdf import FPDF
from datetime import datetime

# Import dari data_loader & universe
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal
from modules.universe import is_syariah

def clean_text(text):
    """Menghapus karakter non-latin untuk kompatibilitas FPDF"""
    if isinstance(text, str):
        return text.encode('latin-1', 'ignore').decode('latin-1')
    return str(text)

def generate_pdf_report(ticker, company, sector, syariah_status, 
                        score, score_status, conf_label, conf_pct,
                        yield_val, payout, konsistensi, cagr, 
                        eps_growth, roe, fcf, der, 
                        est_dps, curr_price, sl_final, entry_price, status_final):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- HEADER PDF (Style Match: Teknikal Pro) ---
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 8, "Expert Stock Pro - Analisa Dividen Pro", ln=True, align="C")
    
    # Tautan Aktif berwarna Biru
    pdf.set_font("Arial", "U", 12)
    pdf.set_text_color(0, 0, 255)
    pdf.cell(0, 8, "Sumber: https://lynk.id/hahastoresby", ln=True, align="C", link="https://lynk.id/hahastoresby")
    pdf.set_text_color(0, 0, 0) # Kembalikan ke teks hitam
    pdf.ln(8)
    
    # --- IDENTITAS SAHAM ---
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 8, clean_text(f"{ticker} - {company}"), ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 6, clean_text(f"Sektor: {sector} | Status: {syariah_status}"), ln=True, align="C")
    pdf.ln(8)

    # Tanggal dan Harga
    current_date = datetime.now().strftime("%d %B %Y")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, clean_text(f"Tanggal Analisa: {current_date} | Harga: Rp {curr_price:,.0f}"), ln=True, align="R")
    
    # Garis Pembatas
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(8)

    # --- INFORMASI SKOR ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, clean_text(f"Skor Kelayakan Dividen: {score}/100 ({score_status})"), ln=True)
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 6, clean_text(f"Tingkat Kepercayaan Data: {conf_label} ({conf_pct:.0f}% metrik tersedia)"), ln=True)
    pdf.ln(5)
    
    # --- 1. HISTORY DIVIDEN ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "1. History & Pertumbuhan Dividen", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, f"- Dividend Yield: {yield_val:.2f}%", ln=True)
    pdf.cell(0, 6, f"- Payout Ratio: {payout:.1f}%", ln=True)
    pdf.cell(0, 6, f"- Konsistensi: {konsistensi}/5 Tahun", ln=True)
    pdf.cell(0, 6, f"- Growth (CAGR): {cagr*100:.1f}%", ln=True)
    pdf.ln(3)

    # --- 2. KINERJA BISNIS ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "2. Kinerja Bisnis", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, f"- EPS Growth (YoY): {eps_growth:.1f}%", ln=True)
    pdf.cell(0, 6, f"- Return on Equity (ROE): {roe:.1f}%", ln=True)
    pdf.ln(3)

    # --- 3. KESEHATAN FINANSIAL ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "3. Kesehatan Finansial", ln=True)
    pdf.set_font("Arial", "", 11)
    fcf_status = "Positif (Aman)" if fcf > 0 else "Negatif (Berisiko)"
    pdf.cell(0, 6, f"- Kualitas Kas (FCF): {fcf_status}", ln=True)
    pdf.cell(0, 6, f"- Debt to Equity Ratio (DER): {der:.2f}x", ln=True)
    pdf.ln(3)

    # --- 4. PROYEKSI & PROTEKSI ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "4. Proyeksi & Proteksi", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, f"- Estimasi DPS Mendatang: Rp {est_dps:,.0f} / Lembar", ln=True)
    pot_yield = (est_dps/curr_price)*100 if curr_price > 0 else 0
    pdf.cell(0, 6, f"- Potential Yield: {pot_yield:.2f}%", ln=True)
    pdf.cell(0, 6, f"- Stop Loss Level (Lock 8%): Rp {sl_final:,.0f}", ln=True)
    pdf.ln(3)

    # --- 5. REKOMENDASI ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "5. Rekomendasi", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, clean_text(f"Status: {status_final}"), ln=True)
    pdf.cell(0, 6, clean_text(f"Harga wajar bila dividen setara deposito (5%): Rp {entry_price:,.0f}"), ln=True)
    pdf.ln(8)

    # --- DISCLAIMER ---
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(100, 100, 100)
    disclaimer_text = "Laporan ini dihasilkan secara otomatis oleh sistem algoritma Expert Stock Pro. Semua informasi, analisa, dan sinyal trading disediakan hanya untuk tujuan edukasi. Keputusan investasi sepenuhnya berada di tangan Anda. Kinerja masa lalu tidak selalu menjamin hasil masa depan."
    pdf.multi_cell(0, 5, disclaimer_text)

    # Kembalikan sebagai bytes
    try:
        return pdf.output(dest="S").encode("latin-1")
    except AttributeError:
        # Menangani jika menggunakan versi fpdf2 terbaru
        return bytearray(pdf.output())

def run_dividen():
    st.title("💰 Analisa Dividen Pro (Passive Income Investing)")
    st.markdown("---")

    # --- INPUT SECTION ---
    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Dividend Check):", value="ITMG").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"
    kode_bersih = ticker_input.replace(".JK", "").upper()

    if st.button(f"Jalankan Analisa Lengkap {ticker_input}"):
        with st.spinner("Mengevaluasi fundamental & kelayakan dividen..."):
            data = get_full_stock_data(ticker)
            info = data['info']
            divs = data['dividends']
            history = data['history']
            
            if not info or divs.empty:
                st.error("Data dividen tidak ditemukan atau emiten tidak membagikan dividen.")
                return

            # --- 1. PRE-CALCULATION UNTUK SCORING ---
            curr_price = info.get('currentPrice', 0)
            yield_val = hitung_div_yield_normal(info)
            payout = info.get('payoutRatio', 0) * 100
            fcf = info.get('freeCashflow', 0)
            roe = info.get('returnOnEquity', 0) * 100
            der = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
            eps_growth = info.get('earningsGrowth', 0) * 100
            
            # Hitung CAGR & Konsistensi Dividen
            df_div = divs.to_frame(name='Dividends')
            df_div.index = pd.to_datetime(df_div.index).tz_localize(None)
            df_div_annual = df_div.resample('YE').sum().tail(5)
            
            konsistensi = len(df_div_annual)
            cagr = 0
            if konsistensi >= 2:
                awal, akhir = df_div_annual['Dividends'].iloc[0], df_div_annual['Dividends'].iloc[-1]
                if awal > 0:
                    cagr = ((akhir / awal) ** (1 / (konsistensi - 1))) - 1
            
            # --- 2. LOGIKA SCORING AKURAT (100 POIN) ---
            total_score = 0
            if fcf > 0: total_score += 20
            if konsistensi == 5 and cagr > 0.05: total_score += 20
            elif konsistensi == 5 and cagr > 0: total_score += 15
            elif konsistensi >= 3: total_score += 10
            
            if yield_val >= 8: total_score += 20
            elif yield_val >= 6: total_score += 15
            elif yield_val >= 4: total_score += 10
            
            if der < 1.0: total_score += 15
            elif der <= 2.0: total_score += 10
            
            if 30 <= payout <= 70: total_score += 15
            elif 70 < payout <= 90: total_score += 10
            elif payout > 0: total_score += 5
            
            if roe > 15 and eps_growth > 0: total_score += 10
            elif roe > 8: total_score += 5
