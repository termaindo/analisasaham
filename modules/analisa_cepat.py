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

# --- FUNGSI GENERATOR PDF ANALISA CEPAT (HEADER BARU) ---
def export_analisa_cepat_to_pdf(ticker, company_name, sector, f_score, roe, lbl_solv, eps_g, rev_g,
                                t_score, avg_value_ma20, rsi, sentiment, curr_per, div_yield,
                                rekomen, curr, entry_bawah, entry_atas, tp, reward_pct, sl_final, risk_pct, alasan_tek):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. HEADER BOX HITAM
    logo_path = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_path):
        logo_path = "../logo_expert_stock_pro.png"

    # Menggambar kotak hitam penuh di bagian atas
    pdf.set_fill_color(20, 20, 20)  # Warna Hitam (Almost Black)
    pdf.rect(0, 0, 210, 25, 'F')    # Lebar A4 = 210mm
    
    # a) LOGO dengan Bingkai Emas
    if os.path.exists(logo_path):
        # Gambar bingkai emas (rect di belakang logo)
        pdf.set_fill_color(218, 165, 32) # Goldenrod color
        pdf.rect(10, 3, 19, 19, 'F')
        # Tampilkan logo
        pdf.image(logo_path, x=10.5, y=3.5, w=18, h=18)
    
    # b) & c) NAMA APLIKASI & MODUL (Teks Putih)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    # Posisi di sebelah kanan logo (logo width ~20 + margin 10 = 30)
    pdf.set_xy(35, 8) 
    pdf.cell(0, 10, "Expert Stock Pro - Analisa Cepat Pro", ln=True)
    
    # Reset posisi Y ke bawah kotak hitam
    pdf.set_y(28)
    
    # 2. HYPERLINK SUMBER
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(0, 0, 255)  # Warna Biru
    pdf.cell(0, 5, "Sumber: https://lynk.id/hahastoresby", ln=True, align='C', link="https://lynk.id/hahastoresby")
    pdf.ln(2)
    
    # 3. NAMA SAHAM & PERUSAHAAN (CENTER)
    pdf.set_text_color(0, 0, 0) # Kembali ke Hitam
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 8, f"{ticker} - {company_name}", ln=True, align='C')
    
    # 4. INFO SEKTOR & SYARIAH (CENTER)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, f"Sektor: {sector.title()} | Status: Perlu Cek ISSI/JII", ln=True, align='C')
    pdf.ln(2)
    
    # 5. INFO TANGGAL & HARGA (RATA KANAN)
    pdf.set_font("Arial", 'B', 10)
    waktu_analisa = datetime.now().strftime("%d-%m-%Y %H:%M WIB")
    pdf.cell(0, 5, f"Analisa: {waktu_analisa} | Harga: Rp {int(curr):,.0f}", ln=True, align='R')
    
    # Garis Bawah Header
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y()+2, 200, pdf.get_y()+2)
    pdf.ln(5)

    # --- BAGIAN KONTEN ANALISA ---
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
    pdf.set_y(-35)
    pdf.set_font("Arial", 'B', 8)
    pdf.cell(190, 5, "DISCLAIMER:", ln=True) 
    pdf.set_font("Arial", 'I', 7)
    disclaimer_text = ("Semua informasi, analisa teknikal, analisa fundamental, ataupun sinyal trading dan analisa-analisa lain "
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
        
    # Tampilkan Logo di Web bagian TENGAH (CENTER) dengan ukuran 150px
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
            # MA Dasar
            df['MA20'] = df['Close'].rolling(20).mean()
            df['MA50'] = df['Close'].rolling(50).mean()
            df['MA200'] = df['Close'].rolling(200).mean()
            
            # Volume & Likuiditas
            df['Value'] = df['Close'] * df['Volume']
            avg_value_ma20 = df['Value'].rolling(20).mean().iloc[-1]
            df['Vol_MA20'] = df['Volume'].rolling(20).mean()
            
            # VWAP 20 Hari
            df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['VWAP_20'] = (df['Typical_Price'] * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()

            # Indikator Momentum / Agresivitas
            df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
            df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
            
            # MACD
            df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
            df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = df['EMA12'] - df['EMA26']
            df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

            # Bollinger Bands
            df['STD20'] = df['Close'].rolling(20).std()
            df['UpperBand'] = df['MA20'] + (df['STD20'] * 2)

            # Kalkulasi RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df['RSI'] = 100 - (100 / (1 + (gain/loss)))

            # Ekstrak Value Akhir
            curr = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            
            ma200_val = 0 if pd.isna(df['MA200'].iloc[-1]) else df['MA200'].iloc[-1]
            ma50_val = 0 if pd.isna(df['MA50'].iloc[-1]) else df['MA50'].iloc[-1]
            ma20_val = 0 if pd.isna(df['MA20'].iloc[-1]) else df['MA20'].iloc[-1]
            ema9_val = df['EMA9'].iloc[-1]
            ema21_val = df['EMA21'].iloc[-1]
            vwap_val = 0 if pd.isna(df['VWAP_20'].iloc[-1]) else df['VWAP_20'].iloc[-1]
            upper_band = 0 if pd.isna(df['UpperBand'].iloc[-1]) else df['UpperBand'].iloc[-1]
            
            vol_curr = df['Volume'].iloc[-1]
            vol_ma20 = df['Vol_MA20'].iloc[-1]
            macd_val = df['MACD'].iloc[-1]
            signal_val = df['Signal'].iloc[-1]
            
            rsi_curr = df['RSI'].iloc[-1]
            rsi_prev = df['RSI'].iloc[-2]
            
            
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

            # i) KESEHATAN KEUANGAN & SOLVABILITAS (Maks 20)
            if is_bank:
                car_scraped, npl_scraped = get_bank_ratios_fallback(ticker)
                
                # NPL (Maks 10)
                npl_approx = npl_scraped if (npl_scraped is not None and not pd.isna(npl_scraped)) else info.get('nonPerformingLoan', 2.5)
                if npl_approx < 2: f_score += 10
                elif npl_approx <= 3.5: f_score += 5
                
                # CAR (Maks 10)
                if car_scraped is not None and not pd.isna(car_scraped):
                    car_approx = car_scraped
                    lbl_solv = f"CAR (Asli) {car_approx:.1f}% | NPL {npl_approx:.1f}%"
                else:
                    total_assets = info.get('totalAssets', 1)
                    total_equity = info.get('totalStockholderEquity', 0)
                    car_approx = (total_equity / total_assets) * 100 if total_assets > 0 else info.get('capitalAdequacyRatio', 18)
                    lbl_solv = f"Est. CAR {car_approx:.1f}% | NPL {npl_approx:.1f}%"
                    
                if car_approx > 20: f_score += 10
                elif car_approx >= 15: f_score += 5
                
            elif is_infra:
                # DER Khusus (Maks 10)
                if der_ratio < 1.5: f_score += 10
                elif der_ratio <= 2.5: f_score += 5
                
                # ICR (Maks 10)
                icr = 2.0
                try:
                    ebit = financials.loc['EBIT'].iloc[0]
                    interest = abs(financials.loc['Interest Expense'].iloc[0])
                    if interest > 0: icr = ebit / interest
                except: pass
                
                if icr > 3.0: f_score += 10
                elif icr >= 1.5: f_score += 5
                lbl_solv = f"DER {der_ratio:.2f}x | ICR {icr:.1f}x"
                
            else: 
                # DER Umum (Maks 10)
                if der_ratio < 0.5: f_score += 10
                elif der_ratio <= 1.0: f_score += 5
                
                # CR (Maks 10)
                cr = info.get('currentRatio', 0)
                if cr > 1.5: f_score += 10
                elif cr >= 1.0: f_score += 5
                lbl_solv = f"DER {der_ratio:.2f}x | CR {cr:.2f}x"

            # ii) PROFITABILITAS / EFISIENSI (Maks 20)
            roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0
            if roe > 15: f_score += 10
            elif roe >= 10: f_score += 5
            
            npm = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0
            if npm > 10: f_score += 10
            elif npm >= 5: f_score += 5

            # iii) VALUASI HARGA DINAMIS (Maks 20)
            curr_per = info.get('trailingPE', 0)
            curr_pbv = info.get('priceToBook', 0)
            mean_pe_5y = info.get('trailingPE', 15) * 0.95 
            mean_pbv_5y = info.get('priceToBook', 1.5) * 0.9 
            
            # PER Diskon (Maks 10)
            if curr_per > 0 and mean_pe_5y > 0:
                pe_discount = ((mean_pe_5y - curr_per) / mean_pe_5y) * 100
                if pe_discount > 20: f_score += 10
                elif pe_discount >= 0: f_score += 5
            
            # PBV Diskon (Maks 10)
            if curr_pbv > 0 and mean_pbv_5y > 0:
                pbv_discount = ((mean_pbv_5y - curr_pbv) / mean_pbv_5y) * 100
                if pbv_discount > 20: f_score += 10
                elif pbv_discount >= 0: f_score += 5

            # iv) PERTUMBUHAN / GROWTH (Maks 20)
            eps_g = info.get('earningsGrowth', 0) * 100 if info.get('earningsGrowth') else 0
            if eps_g > 15: f_score += 10
            elif eps_g >= 5: f_score += 7
            elif eps_g >= 0: f_score += 3
            
            cagr_rev = 0
            if not financials.empty and 'Total Revenue' in financials.index:
                try:
                    revs = financials.loc['Total Revenue']
                    if len(revs) >= 2:
                        years = len(revs) - 1
                        cagr_rev = ((revs.iloc[0] / revs.iloc[-1]) ** (1/years)) - 1
                except: pass
            
            rev_g = cagr_rev * 100 if cagr_rev != 0 else (info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0)
            if rev_g > 10: f_score += 10
            elif rev_g >= 0: f_score += 5

            # v) KUALITAS ARUS KAS (Maks 10)
            ocf = info.get('operatingCashflow', 0)
            net_inc = info.get('netIncomeToCommon', 0)
            if ocf > net_inc and net_inc != 0: f_score += 10
            elif ocf > 0: f_score += 5

            # vi) DIVIDEN & BUKTI KAS (Maks 10)
            div_yield = hitung_div_yield_normal(info)
            if div_yield > 5: f_score += 10
            elif div_yield >= 2: f_score += 5


            # === B. PENILAIAN TEKNIKAL SWING TRADING (Skala 100 Poin) ===
            t_score = 0
            alasan_tek = []

            # i) Tren Utama (Maks 30)
            if curr > ma200_val: t_score += 10; alasan_tek.append("Uptrend (MA200)")
            if curr > ma50_val: t_score += 10; alasan_tek.append("Uptrend (MA50)")
            if curr > ma20_val: t_score += 10; alasan_tek.append("Uptrend (MA20)")

            # ii) Konfirmasi Volume & Likuiditas (Maks 20)
            if vol_curr > vol_ma20: t_score += 10; alasan_tek.append("Volume > Rata-rata")
            if curr > vwap_val: t_score += 10; alasan_tek.append("Harga > VWAP")

            # iii) Kekuatan Momentum (Maks 20)
            if 50 <= rsi_curr <= 70: t_score += 5; alasan_tek.append("RSI 50-70")
            if rsi_curr > rsi_prev: t_score += 5; alasan_tek.append("RSI Naik")
            if macd_val > signal_val: t_score += 10; alasan_tek.append("MACD Bullish")

            # iv) Agresivitas Aksi Harga (Maks 20)
            if ema9_val > ema21_val: t_score += 10; alasan_tek.append("EMA 9>21 Cross")
            if curr > prev_close: t_score += 10; alasan_tek.append("Close > Prev")

            # v) Volatilitas & Risiko (Maks 10)
            if ma20_val < curr < upper_band: t_score += 10; alasan_tek.append("Posisi Bollinger Aman")

            teks_alasan = ", ".join(alasan_tek) if alasan_tek else "Tidak ada sinyal kuat"

            # --- 4. RENTANG ENTRY & TRADING PLAN ---
            # Kalkulasi ATR untuk SL
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            atr = ranges.max(axis=1).rolling(14).mean().iloc[-1]
            
            # LOGIKA RENTANG ENTRY (Maksimal -4% atau EMA9)
            entry_atas = curr
            batas_diskon_4pct = curr * 0.96
            
            if ema9_val < curr:
                entry_bawah = max(ema9_val, batas_diskon_4pct)
            else:
                entry_bawah = batas_diskon_4pct
                
            avg_entry = (entry_atas + entry_bawah) / 2
            
            # LOGIKA SL: 2.5x ATR, Maksimal Loss 8%
            sl_atr = curr - (2.5 * atr)
            sl_final = max(sl_atr, curr * 0.92) 
            
            # LOGIKA TP: RRR 1:2
            tp = int(avg_entry + (avg_entry - sl_final) * 2)
            
            risk_pct = ((avg_entry - sl_final) / avg_entry) * 100
            reward_pct = ((tp - avg_entry) / avg_entry) * 100
            
            # Tentukan Sentimen
            if curr > ma50_val and curr > ma200_val: sentiment = "BULLISH (Sangat Kuat) 🐂"
            elif curr > ema21_val: sentiment = "MILD BULLISH (Jangka Pendek) 🐃"
            elif curr < ma200_val: sentiment = "BEARISH (Hati-hati) 🐻"
            else: sentiment = "NEUTRAL / SIDEWAYS 😐"

            # --- Rekomendasi Swing Trading ---
            if t_score >= 80:
                rekomen = "High Confidence -> Saham Super Trend, Layak All-in (Sesuaikan Sizing)"
                color_rec = "#00ff00"
            elif t_score >= 60:
                rekomen = "Medium Confidence -> Saham Bagus, Layak Dicicil Bertahap"
                color_rec = "#ffcc00"
            else:
                rekomen = "Abaikan -> Risiko Reversal Masih Terlalu Tinggi"
                color_rec = "#ff0000"

            company_name = info.get('longName', ticker)

            # --- 5. TAMPILAN OUTPUT ---
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
                    <li><b>5. Trading Plan (Swing Target 1:2):</b><br>
                        • Harga Sekarang: Rp {int(curr):,.0f}<br>
                        • Usulan Entry: Rp {int(entry_bawah):,.0f} - Rp {int(entry_atas):,.0f} (Maks -4% / EMA9)<br>
                        • Titik Target (TP): Rp {tp:,.0f} (Potensi Reward: +{reward_pct:.1f}%)<br>
                        • Batas Risiko (SL): Rp {sl_final:,.0f} (Risiko Maks: -{risk_pct:.1f}%)
                    </li>
                    <li><b>6. Timeframe:</b> Swing Trading (Menengah)</li>
                </ul>
            </div>
            """
            st.markdown(html_output, unsafe_allow_html=True)
            
            with st.expander("Lihat Detail Data Mentah"):
                st.write(f"Sektor Terdeteksi: {sector.title()} | Bank? {is_bank}")
                st.write(f"Raw DER: {raw_der} | Normalized Ratio: {der_ratio:.2f}")
                st.write(f"VWAP 20: Rp {int(vwap_val):,.0f} | MACD: {macd_val:.2f} (Signal: {signal_val:.2f})")
                st.write(f"Upper Bollinger Band: Rp {int(upper_band):,.0f}")
                
                if is_bank: 
                    st.write(f"CAR Terpakai: {car_approx:.2f}% ({'Hasil Scraping' if car_scraped is not None else 'Estimasi Proxy'})")
                    st.write(f"NPL Terpakai: {npl_approx:.2f}% ({'Hasil Scraping' if npl_scraped is not None else 'Estimasi Proxy'})")

            # --- 5.5 TAMPILKAN TOMBOL DOWNLOAD PDF (Posisi Baru & Menonjol) ---
            pdf_data = export_analisa_cepat_to_pdf(
                ticker, company_name, sector, f_score, roe, lbl_solv, eps_g, rev_g,
                t_score, avg_value_ma20, rsi_curr, sentiment, curr_per, div_yield,
                rekomen, curr, entry_bawah, entry_atas, tp, reward_pct, sl_final, risk_pct, teks_alasan
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

            # --- 6. DISCLAIMER ---
            st.markdown("---")
            st.markdown("**DISCLAIMER:** Semua informasi, analisa teknikal, analisa fundamental, ataupun sinyal trading dan analisa-analisa lain yang disediakan di modul ini hanya untuk tujuan edukasi dan informasi. Ini bukan merupakan rekomendasi, ajakan, atau nasihat keuangan untuk membeli atau menjual saham tertentu. Keputusan investasi sepenuhnya berada di tangan Anda. Harap lakukan riset Anda sendiri (*Do Your Own Research*) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.")
