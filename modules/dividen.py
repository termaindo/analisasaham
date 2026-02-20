import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from fpdf import FPDF
from datetime import datetime
import os
import base64  # FIX: Ditambahkan agar tidak error 'base64 is not defined'

# Import dari data_loader & universe
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal
from modules.universe import is_syariah

def clean_text(text):
    """Menghapus karakter non-latin untuk kompatibilitas FPDF"""
    if isinstance(text, str):
        return text.encode('latin-1', 'ignore').decode('latin-1')
    return str(text)

# --- FUNGSI GENERATE PDF (HEADER BOX HITAM & EMAS) ---
def generate_pdf_report(ticker, company, sector, syariah_status, 
                        score, score_status, conf_label, conf_pct,
                        yield_val, payout, konsistensi, cagr, 
                        eps_growth, roe, fcf, der, 
                        est_dps, curr_price, sl_final, entry_price, status_final):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # 1. HEADER BOX HITAM
    pdf.set_fill_color(20, 20, 20)  # Hampir Hitam
    pdf.rect(0, 0, 210, 25, 'F')
    
    logo_path = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_path):
        logo_path = "../logo_expert_stock_pro.png"

    # a) LOGO dengan Bingkai Emas
    if os.path.exists(logo_path):
        pdf.set_fill_color(218, 165, 32) # Goldenrod
        pdf.rect(10, 3, 19, 19, 'F')
        pdf.image(logo_path, x=10.5, y=3.5, w=18, h=18)
    
    # b) NAMA APLIKASI & MODUL (Teks Putih)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    pdf.set_xy(35, 8) 
    pdf.cell(0, 10, "Expert Stock Pro - Analisa Dividen Pro", ln=True)
    
    pdf.set_y(28)
    
    # 2. HYPERLINK SUMBER
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(0, 0, 255)
    pdf.cell(0, 5, "Sumber: https://lynk.id/hahastoresby", ln=True, align='C', link="https://lynk.id/hahastoresby")
    pdf.ln(2)
    
    # 3. NAMA SAHAM & PERUSAHAAN (CENTER)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 8, clean_text(f"{ticker} - {company}"), ln=True, align='C')
    
    # 4. INFO SEKTOR & SYARIAH (CENTER)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, clean_text(f"Sektor: {sector} | Status: {syariah_status}"), ln=True, align='C')
    pdf.ln(2)
    
    # 5. INFO TANGGAL & HARGA (RATA KANAN)
    pdf.set_font("Arial", 'B', 10)
    waktu_analisa = datetime.now().strftime("%d-%m-%Y %H:%M")
    pdf.cell(0, 5, clean_text(f"Analisa: {waktu_analisa} | Harga: Rp {curr_price:,.0f}"), ln=True, align='R')
    
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y()+2, 200, pdf.get_y()+2)
    pdf.ln(5)

    # --- KONTEN ANALISA ---
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, clean_text(f"Skor Kelayakan Dividen: {score}/100 ({score_status})"), ln=1)
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 6, clean_text(f"Tingkat Kepercayaan Data: {conf_label} ({conf_pct:.0f}% metrik tersedia)"), ln=1)
    pdf.ln(5)
    
    sections = [
        ("1. History & Pertumbuhan Dividen", [
            f"- Dividend Yield: {yield_val:.2f}%",
            f"- Payout Ratio: {payout:.1f}%",
            f"- Konsistensi: {konsistensi}/5 Tahun",
            f"- Growth (CAGR): {cagr*100:.1f}%"
        ]),
        ("2. Kinerja Bisnis", [
            f"- EPS Growth (YoY): {eps_growth:.1f}%",
            f"- Return on Equity (ROE): {roe:.1f}%"
        ]),
        ("3. Kesehatan Finansial", [
            f"- Kualitas Kas (FCF): {'Positif (Aman)' if fcf > 0 else 'Negatif (Berisiko)'}",
            f"- Debt to Equity Ratio (DER): {der:.2f}x"
        ]),
        ("4. Proyeksi & Proteksi", [
            f"- Estimasi DPS Mendatang: Rp {est_dps:,.0f} / Lembar",
            f"- Potential Yield: {(est_dps/curr_price)*100 if curr_price > 0 else 0:.2f}%",
            f"- Stop Loss Level (Lock 8%): Rp {sl_final:,.0f}"
        ]),
        ("5. Rekomendasi", [
            f"Status: {status_final}",
            f"Harga wajar bila dividen setara deposito (5%): Rp {entry_price:,.0f}"
        ])
    ]

    for title, lines in sections:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, title, ln=1)
        pdf.set_font("Arial", "", 11)
        for line in lines:
            pdf.cell(0, 6, clean_text(line), ln=1)
        pdf.ln(3)

    # --- DISCLAIMER LENGKAP ---
    pdf.ln(5)
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(100, 100, 100)
    disclaimer_text = ("DISCLAIMER: Semua informasi, analisa teknikal, analisa fundamental, ataupun sinyal trading "
                       "dan analisa-analisa lain yang disediakan di modul ini hanya untuk tujuan edukasi dan informasi. "
                       "Ini bukan merupakan rekomendasi, ajakan, atau nasihat keuangan untuk membeli atau menjual saham tertentu. "
                       "Keputusan investasi sepenuhnya berada di tangan Anda. Harap lakukan riset Anda sendiri (Do Your Own Research) "
                       "dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.")
    pdf.multi_cell(0, 5, clean_text(disclaimer_text))

    try:
        out = pdf.output(dest="S")
        return out.encode("latin-1") if isinstance(out, str) else bytes(out)
    except Exception:
        return bytes(pdf.output())

def run_dividen():
    # --- TAMPILAN WEB (LOGO CENTER) ---
    logo_file = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_file):
        logo_file = "../logo_expert_stock_pro.png"
        
    if os.path.exists(logo_file):
        with open(logo_file, "rb") as f:
            data_img = f.read()
            encoded_img = base64.b64encode(data_img).decode()
        
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; margin-bottom: 10px;">
                <img src="data:image/png;base64,{encoded_img}" width="150">
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown("<h1 style='text-align: center;'>💰 Analisa Dividen Pro</h1>", unsafe_allow_html=True)
    else:
        st.markdown("<h1 style='text-align: center;'>💰 Analisa Dividen Pro</h1>", unsafe_allow_html=True)
        st.warning("⚠️ File logo belum ditemukan.")
        
    st.markdown("---")
    
    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Contoh: ADRO):", value="ADRO").upper()
    
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

            # --- PRE-CALCULATION & SCORING ---
            curr_price = info.get('currentPrice') or 0
            yield_val = hitung_div_yield_normal(info)
            payout = (info.get('payoutRatio') or 0) * 100
            fcf = info.get('freeCashflow') or 0
            roe = (info.get('returnOnEquity') or 0) * 100
            der = (info.get('debtToEquity') or 0) / 100
            eps_growth = (info.get('earningsGrowth') or 0) * 100
            trailing_eps = info.get('trailingEps') or 0
            
            df_div = divs.to_frame(name='Dividends')
            df_div.index = pd.to_datetime(df_div.index).tz_localize(None)
            df_div_annual = df_div.resample('YE').sum().tail(5)
            konsistensi = len(df_div_annual)
            cagr = 0
            if konsistensi >= 2:
                awal, akhir = df_div_annual['Dividends'].iloc[0], df_div_annual['Dividends'].iloc[-1]
                if awal > 0:
                    cagr = ((akhir / awal) ** (1 / (konsistensi - 1))) - 1
            
            total_score = 0
            if fcf > 0: total_score += 20
            if konsistensi == 5 and cagr > 0.05: total_score += 20
            elif konsistensi == 5 and cagr > 0: total_score += 15
            elif yield_val >= 8: total_score += 20
            elif yield_val >= 6: total_score += 15
            if der < 1.0: total_score += 15
            if 30 <= payout <= 70: total_score += 15
            if roe > 15 and eps_growth > 0: total_score += 10

            score_status = "Sangat Layak" if total_score >= 80 else "Layak dengan Pantauan" if total_score >= 60 else "Resiko Tinggi"
            
            # --- HEADER UI & SUMMARY ---
            company_name = info.get('longName') or ticker_input
            status_syr_icon = "✅" if is_syariah(kode_bersih) else "❌"
            sector = info.get('sector') or 'Sektor Tidak Diketahui'

            st.markdown(f"""
                <div style="text-align: center; padding: 20px; background-color: #1E1E1E; border-radius: 10px; border: 1px solid #333;">
                    <h1 style="color: #2ECC71;">🏢 {ticker_input} - {company_name}</h1>
                    <p>Sektor: {sector} | {status_syr_icon} {'Syariah' if is_syariah(kode_bersih) else 'Non-Syariah'}</p>
                    <h3>Skor: {total_score}/100</h3>
                    <div style="background-color: #333; height: 10px; border-radius: 5px;">
                        <div style="background-color: #2ECC71; width: {total_score}%; height: 10px; border-radius: 5px;"></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # --- SECTIONS (History, Biz, Finansial, Proyeksi) ---
            st.header("1. History & Pertumbuhan Dividen")
            st.bar_chart(df_div_annual['Dividends'])
            
            # --- REKOMENDASI ---
            st.header("5. Rekomendasi")
            est_dps = trailing_eps * (payout / 100)
            entry_price = est_dps / 0.05 if est_dps > 0 else 0
            status_final = "SANGAT LAYAK" if (curr_price < entry_price and total_score >= 80) else "TUNGGU KOREKSI"
            
            st.subheader(f"Status: {status_final}")
            st.write(f"**Harga wajar (Yield 5%):** Rp {entry_price:,.0f}")
            st.write(f"**Harga Saat Ini:** Rp {curr_price:,.0f}")

            # --- EXPORT PDF ---
            st.markdown("---")
            # Perhitungan ATR untuk Stop Loss
            try:
                atr = (history['High'] - history['Low']).tail(14).mean()
                if np.isnan(atr): atr = 0
            except: atr = 0
            sl_final = max(curr_price - (1.5 * atr), curr_price * 0.92)

            pdf_bytes = generate_pdf_report(
                ticker_input, company_name, sector, "Syariah" if is_syariah(kode_bersih) else "Non-Syariah",
                total_score, score_status, "Tinggi", 100,
                yield_val, payout, konsistensi, cagr, 
                eps_growth, roe, fcf, der, 
                est_dps, curr_price, sl_final, entry_price, status_final
            )
            
            # Format nama file sesuai instruksi
            file_name_pdf = f"Expert_Stock_Pro_Dividen_{kode_bersih}_{datetime.now().strftime('%Y%m%d')}.pdf"
            
            st.download_button(
                label="📄 Simpan sebagai PDF",
                data=pdf_bytes,
                file_name=file_name_pdf,
                mime="application/pdf",
                use_container_width=True
            )
            
            st.markdown("---")
            st.caption("""**DISCLAIMER:** Semua informasi, analisa teknikal, analisa fundamental, ataupun sinyal trading dan analisa-analisa lain yang disediakan di modul ini hanya untuk tujuan edukasi dan informasi. Ini bukan merupakan rekomendasi, ajakan, atau nasihat keuangan untuk membeli atau menjual saham tertentu. Keputusan investasi sepenuhnya berada di tangan Anda. Harap lakukan riset Anda sendiri (*Do Your Own Research*) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.""")
