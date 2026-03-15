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

            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df['RSI'] = 100 - (100 / (1 + (gain/loss)))

            curr = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            
            ma200_val = 0 if pd.isna(df['MA200'].iloc[-1]) else df['MA200'].iloc[-1]
            ma50_val = 0 if pd.isna(df['MA50'].iloc[-1]) else df['MA50'].iloc[-1]
            ema9_val = df['EMA9'].iloc[-1]
            ema21_val = df['EMA21'].iloc[-1]
            
            vol_curr = df['Volume'].iloc[-1]
            vol_ma20 = df['Vol_MA20'].iloc[-1]
            
            # --- 3. SCORING FUNDAMENTAL (Tetap Sama) ---
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
            if div_yield > 5: f_score += 10
            elif div_yield >= 2: f_score += 5


            # === B. PENILAIAN TEKNIKAL SWING TRADING (100 Poin Baru) ===
            t_score = 0
            alasan_tek = []

            # a) Filter Tren Utama (Maks 35)
            if curr > ma200_val: t_score += 20; alasan_tek.append("Macro UP (MA200)")
            if curr > ma50_val: t_score += 15; alasan_tek.append("Medium UP (MA50)")

            # b) Sinyal Eksekusi / Micro Momentum (Maks 20)
            if curr > ema9_val: t_score += 15; alasan_tek.append("Micro Momentum (EMA9)")
            if ema9_val > ema21_val: t_score += 5; alasan_tek.append("Momentum Cross (EMA9>21)")

            # c) Konfirmasi Volume & Likuiditas (Maks 30)
            if vol_curr > vol_ma20: t_score += 20; alasan_tek.append("Volume Spike")
            if avg_value_ma20 > 5000000000: t_score += 10; alasan_tek.append("Inst. Liquidity")

            # d) Ekstra Poin Sektor / Bonus Makro (Maks 15)
            # Kita gunakan f_score saham sebagai proxy rotasi karena sektor yang fundamentalnya > 60 cenderung diakumulasi
            if f_score >= 60: 
                t_score += 15; alasan_tek.append(f"Sector Hot: [{sector.title()}]")

            teks_alasan = ", ".join(alasan_tek) if alasan_tek else "Tidak ada sinyal kuat"

            # --- 4. RENTANG ENTRY & TRADING PLAN (Berbasis ATR & Sizing) ---
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            atr = ranges.max(axis=1).rolling(14).mean().iloc[-1]
            
            entry_atas = curr
            entry_bawah = curr * 0.99 # Diskon 1% (Buy on Weakness)
            avg_entry = (entry_atas + entry_bawah) / 2
            
            # SL Ganda (Cari yang paling aman)
            sl_atr = avg_entry - (2.5 * atr)
            sl_hard_cap = avg_entry * 0.92 # Maksimal turun 8%
            
            if sl_hard_cap > sl_atr:
                sl_final = sl_hard_cap
                sl_note = " (SL Hard Cap)"
            else:
                sl_final = sl_atr
                sl_note = " (ATR SL)"
                
            # TP RRR 1:2
            tp = avg_entry + ((avg_entry - sl_final) * 2) 
            
            risk_pct = ((avg_entry - sl_final) / avg_entry) * 100
            reward_pct = ((tp - avg_entry) / avg_entry) * 100

            # --- 5. KALKULASI POSITION SIZING ---
            selisih_risiko = avg_entry - sl_final
            if selisih_risiko <= 0: selisih_risiko = 1 # Mencegah error division by zero
            
            # 1. Batas Toleransi Kerugian (Risk-Based)
            max_shares_risk = maks_risiko / selisih_risiko
            
            # 2. Batas Diversifikasi (Capital-Based Maks 15%)
            max_shares_cap = (0.15 * modal_awal) / avg_entry
            
            # 3. Keputusan Final
            final_shares = min(max_shares_risk, max_shares_cap)
            max_lot = int(final_shares // 100)
            if max_lot < 0: max_lot = 0
            
            alasan_lot = "Maks. Risiko per Trade" if max_shares_risk < max_shares_cap else "Maks. 15% dari Total Modal"

            # --- 6. INTERPRETASI SKOR ---
            if curr > ma50_val and curr > ma200_val: sentiment = "BULLISH (Sangat Kuat) 🐂"
            elif curr > ema21_val: sentiment = "MILD BULLISH (Jangka Pendek) 🐃"
            elif curr < ma200_val: sentiment = "BEARISH (Hati-hati) 🐻"
            else: sentiment = "NEUTRAL / SIDEWAYS 😐"

            trading_plan_html = ""

            if t_score >= 85:
                rekomen = "Boleh Trading -> Silakan ambil posisi sesuai saran di bawah ini:"
                color_rec = "#00ff00"
                
                trading_plan_html = f"""<li><b>6. Trading Plan & Sizing (Swing Target 1:2):</b><br>
                    • Harga Sekarang: Rp {int(curr):,.0f}<br>
                    • Usulan Entry: Rp {int(entry_bawah):,.0f} - Rp {int(entry_atas):,.0f} (Buy on Weakness -1%)<br>
                    • Titik Target (TP): Rp {int(tp):,.0f} (Potensi Reward: +{reward_pct:.1f}%)<br>
                    • Batas Risiko (SL): Rp {int(sl_final):,.0f} (Risiko Maks: -{risk_pct:.1f}%){sl_note}<br>
                    • <span style='color:#00e676; font-size:16px;'><b>Max Lot Pembelian: {max_lot} Lot</b> <i>({alasan_lot})</i></span>
                </li>"""
                
            elif t_score >= 70:
                rekomen = "Hati-hati -> Indikator cukup mendukung untuk saham ini dimasukkan dalam daftar pantauan ('watch list'), atau boleh trading dengan lot sebagian dulu."
                color_rec = "#ffcc00"
                
                trading_plan_html = f"""<li><b>6. Trading Plan & Sizing (Swing Target 1:2):</b><br>
                    • Harga Sekarang: Rp {int(curr):,.0f}<br>
                    • Usulan Entry: Rp {int(entry_bawah):,.0f} - Rp {int(entry_atas):,.0f} (Buy on Weakness -1%)<br>
                    • Titik Target (TP): Rp {int(tp):,.0f} (Potensi Reward: +{reward_pct:.1f}%)<br>
                    • Batas Risiko (SL): Rp {int(sl_final):,.0f} (Risiko Maks: -{risk_pct:.1f}%){sl_note}<br>
                    • <span style='color:#ffb300; font-size:16px;'><b>Max Lot Pembelian: {max_lot} Lot</b> <i>({alasan_lot})</i></span>
                </li>"""
                
            else:
                rekomen = "Dilarang Trading -> Tidak Disarankan untuk melakukan trading dulu, karena belum didukung oleh indikator teknikal yang memadai."
                color_rec = "#ff0000"
                trading_plan_html = f"<li><b>6. Trading Plan:</b><br><span style='color:#ff5252; font-weight:bold;'>Tidak Disarankan untuk Melakukan Trading dulu, karena belum didukung oleh indikator teknikal yang memadai.</span></li>"

            company_name = info.get('longName', ticker)

            # --- TAMPILAN OUTPUT ---
            html_output = f"""
            <div style="background-color:#1e2b3e; padding:25px; border-radius:12px; border-left:10px solid {color_rec}; color:#e0e0e0; font-family:sans-serif;">
                <h3 style="margin-top:0; color:white; margin-bottom:5px;">{company_name} ({ticker})</h3>
                <p style="margin-top:0; font-size:14px; color:#b0bec5; margin-bottom:15px;">
                    Sektor: <b>{sector.title()}</b> | Kategori Syariah: <b>Perlu Cek ISSI/JII</b>
                </p>
                <ul style="line-height:1.8; padding-left:20px; font-size:16px;">
                    <li><b>1. Fundamental Score ({f_score}/100):</b> ROE {roe:.1f}%, {lbl_solv}, EPS Grw {eps_g:.1f}%, Arus Kas {'Positif' if ocf>0 else 'Negatif'}.</li>
                    <li><b>2. Technical Score ({t_score:g}/100):</b> Trigger -> {teks_alasan}</li>
                    <li><b>3. Sentiment Pasar:</b> <b>{sentiment}</b></li>
                    <li><b>4. Rekomendasi Final:</b> <br><span style="color:{color_rec}; font-weight:bold; font-size:17px;">{rekomen}</span></li>
                    <li><b>5. Timeframe:</b> Swing Trading (Menengah)</li>
                    {trading_plan_html}
                </ul>
            </div>
            """
            st.markdown(html_output, unsafe_allow_html=True)
            
            with st.expander("Lihat Detail Data Mentah"):
                st.write(f"Modal Terinput: Rp {modal_awal:,.0f} | Maks Risiko: Rp {maks_risiko:,.0f}")
                st.write(f"Jarak Entry ke SL (Risiko/Lembar): Rp {selisih_risiko:,.0f}")
                st.write(f"VWAP 20: Rp {int(vwap_val):,.0f} | MACD: {macd_val:.2f} (Signal: {signal_val:.2f})")

            # --- TOMBOL DOWNLOAD PDF ---
            pdf_data = export_analisa_cepat_to_pdf(
                ticker, company_name, sector, f_score, roe, lbl_solv, eps_g, rev_g,
                t_score, avg_value_ma20, rsi_curr, sentiment, curr_per, div_yield,
                rekomen, curr, entry_bawah, entry_atas, tp, reward_pct, sl_final, risk_pct, teks_alasan,
                modal_awal, maks_risiko, max_lot, alasan_lot, sl_note
            )
            
            tanggal_cetak = datetime.now().strftime('%Y%m%d')
            nama_file_pdf = f"ExpertStockPro_AnalisaCepat_{ticker.replace('.JK', '')}_{tanggal_cetak}.pdf"
            
            st.markdown("<br>", unsafe_allow_html=True) 
            _, col_pdf, _ = st.columns([1, 2, 1])
            with col_pdf:
                st.download_button(
                    label="📄 Simpan Analisa Cepat (PDF)",
                    data=pdf_data,
                    file_name=nama_file_pdf,
                    mime="application/pdf",
                    use_container_width=True
                )

            st.markdown("---")
            st.markdown("**DISCLAIMER:** Semua informasi, analisa teknikal, analisa fundamental, ataupun sinyal trading dan analisa-analisa lain yang disediakan di modul ini hanya untuk tujuan edukasi dan informasi. Ini bukan merupakan rekomendasi, ajakan, atau nasihat keuangan untuk membeli atau menjual saham tertentu. Keputusan investasi sepenuhnya berada di tangan Anda. Harap lakukan riset Anda sendiri (*Do Your Own Research*) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.")
