import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal
from modules.universe import is_syariah # --- Integrasi Modul Universe ---

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
# -----------------------------------------------------

def run_analisa_cepat():
    st.title("⚡ Analisa Cepat Pro (Scoring 100 & Dynamic Entry)")
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
            df['MA20'] = df['Close'].rolling(20).mean()
            df['MA200'] = df['Close'].rolling(200).mean()
            
            # Hitung Value Transaksi
            df['Value'] = df['Close'] * df['Volume']
            avg_value_ma20 = df['Value'].rolling(20).mean().iloc[-1]

            # Indikator Teknikal Baru untuk Scoring 100 Poin
            df['Vol_MA20'] = df['Volume'].rolling(20).mean()
            df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['VWAP_20'] = (df['Typical_Price'] * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()
            df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
            df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()

            # Kalkulasi RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rsi = 100 - (100 / (1 + (gain/loss))).iloc[-1]

            # Cek ketersediaan data MA200 & ekstrak nilai
            ma200_val = 0 if pd.isna(df['MA200'].iloc[-1]) else df['MA200'].iloc[-1]
            ma20_val = df['MA20'].iloc[-1]
            vwap_val = df['VWAP_20'].iloc[-1] if not pd.isna(df['VWAP_20'].iloc[-1]) else df['Close'].iloc[-1]
            
            curr = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2]
            
            # --- 3. SCORING FUNDAMENTAL & TEKNIKAL ---
            f_score = 0
            t_score = 0
            
            # Variabel Penghitung Konfidensi
            total_metrik_fun = 7
            metrik_tersedia = 0
            
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

            # 1. KESEHATAN KEUANGAN (Maks 25)
            if is_bank:
                car_scraped, npl_scraped = get_bank_ratios_fallback(ticker)
                
                # Cek ketersediaan data untuk konfidensi
                if car_scraped is not None or info.get('capitalAdequacyRatio'): metrik_tersedia += 1
                
                npl_approx = npl_scraped if (npl_scraped is not None and not pd.isna(npl_scraped)) else info.get('nonPerformingLoan', 2.5)
                if npl_approx < 2: f_score += 10
                elif npl_approx <= 3.5: f_score += 5
                
                if car_scraped is not None and not pd.isna(car_scraped):
                    car_approx = car_scraped
                    lbl_solv = f"CAR (Asli) {car_approx:.1f}% | NPL {npl_approx:.1f}%"
                else:
                    total_assets = info.get('totalAssets', 1)
                    total_equity = info.get('totalStockholderEquity', 0)
                    car_approx = (total_equity / total_assets) * 100 if total_assets > 0 else info.get('capitalAdequacyRatio', 18)
                    lbl_solv = f"Est. CAR {car_approx:.1f}% | NPL {npl_approx:.1f}%"
                    
                if car_approx > 20: f_score += 15
                elif car_approx >= 15: f_score += 10
                elif car_approx >= 10: f_score += 5
                
            elif is_infra:
                if info.get('debtToEquity') is not None: metrik_tersedia += 1
                if der_ratio < 1.5: f_score += 15
                elif der_ratio <= 2.5: f_score += 10
                elif der_ratio <= 4.0: f_score += 5
                
                icr = 2.0
                try:
                    ebit = financials.loc['EBIT'].iloc[0]
                    interest = abs(financials.loc['Interest Expense'].iloc[0])
                    if interest > 0: icr = ebit / interest
                except: pass
                
                if icr > 3.0: f_score += 10
                elif icr >= 1.5: f_score += 5
                lbl_solv = f"DER {der_ratio:.2f}x | ICR {icr:.1f}x"
                
            else: # Sektor Umum
                if info.get('debtToEquity') is not None: metrik_tersedia += 1
                if der_ratio < 0.5: f_score += 15
                elif der_ratio <= 1.0: f_score += 10
                elif der_ratio <= 2.0: f_score += 5
                
                cr = info.get('currentRatio', 0)
                if cr > 1.5: f_score += 10
                elif cr >= 1.0: f_score += 5
                lbl_solv = f"DER {der_ratio:.2f}x | CR {cr:.2f}x"

            # 2. PROFITABILITAS (Maks 25)
            if info.get('returnOnEquity') is not None: metrik_tersedia += 1
            roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0
            if roe > 15: f_score += 15
            elif roe >= 10: f_score += 10
            elif roe >= 5: f_score += 5
            
            if info.get('profitMargins') is not None: metrik_tersedia += 1
            npm = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0
            if npm > 10: f_score += 10
            elif npm >= 5: f_score += 5

            # 3. VALUASI DINAMIS (Maks 20)
            if info.get('trailingPE') is not None: metrik_tersedia += 1
            curr_per = info.get('trailingPE', 0)
            
            if info.get('priceToBook') is not None: metrik_tersedia += 1
            curr_pbv = info.get('priceToBook', 0)
            
            mean_pe_5y = info.get('trailingPE', 15) * 0.95 
            mean_pbv_5y = info.get('priceToBook', 1.5) * 0.9 
            
            if curr_per > 0 and mean_pe_5y > 0:
                pe_discount = ((mean_pe_5y - curr_per) / mean_pe_5y) * 100
                if pe_discount > 20: f_score += 10
                elif pe_discount >= 0: f_score += 7
                elif pe_discount >= -20: f_score += 3
            
            if curr_pbv > 0 and mean_pbv_5y > 0:
                pbv_discount = ((mean_pbv_5y - curr_pbv) / mean_pbv_5y) * 100
                if pbv_discount > 20: f_score += 10
                elif pbv_discount >= 0: f_score += 7
                elif pbv_discount >= -20: f_score += 3

            # 4. PERTUMBUHAN / GROWTH (Maks 20)
            if info.get('earningsGrowth') is not None: metrik_tersedia += 1
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
            
            if info.get('revenueGrowth') is not None or cagr_rev != 0: metrik_tersedia += 1
            rev_g = cagr_rev * 100 if cagr_rev != 0 else (info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0)
            if rev_g > 10: f_score += 10
            elif rev_g >= 0: f_score += 5

            # 5. DIVIDEN (Maks 10)
            div_yield = hitung_div_yield_normal(info)
            if div_yield > 5: f_score += 10
            elif div_yield >= 2: f_score += 5

            # --- KALKULASI LEVEL KONFIDENSI ---
            konfidensi_pct = (metrik_tersedia / total_metrik_fun) * 100
            if konfidensi_pct >= 85:
                label_konfidensi = f"<span style='color:#00ff00;'>Tinggi 🟢 ({konfidensi_pct:.0f}%)</span>"
            elif konfidensi_pct >= 50:
                label_konfidensi = f"<span style='color:#ffcc00;'>Sedang 🟡 ({konfidensi_pct:.0f}%)</span>"
            else:
                label_konfidensi = f"<span style='color:#ff0000;'>Rendah 🔴 ({konfidensi_pct:.0f}%) - Hati-hati data bolong</span>"

            # === B. PENILAIAN TEKNIKAL (Skala 100 Poin) ===
            t_score = 0

            # 1. Relative Volume (20 Poin)
            curr_vol = df['Volume'].iloc[-1] if not pd.isna(df['Volume'].iloc[-1]) else 0
            avg_vol_20 = df['Vol_MA20'].iloc[-1] if not pd.isna(df['Vol_MA20'].iloc[-1]) else 0
            if curr_vol > avg_vol_20: t_score += 20

            # 2. VWAP Alignment (20 Poin)
            if curr > vwap_val: t_score += 20

            # 3. RSI Momentum (20 Poin)
            if 50 < rsi < 70: t_score += 20

            # 4. EMA 9/21 Cross (20 Poin)
            ema9_val = df['EMA9'].iloc[-1]
            ema21_val = df['EMA21'].iloc[-1]
            if ema9_val > ema21_val: t_score += 20

            # 5. Price Action/Gap (10 Poin)
            if (curr - prev_close) / prev_close > 0.02: t_score += 10

            # 6. Value MA20 (10 Poin)
            if avg_value_ma20 > 5e9: t_score += 10


            # --- 4. DATA PROCESSING LAINNYA & RENTANG ENTRY ---
            # Kalkulasi ATR untuk SL (Lock 8%)
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            atr = ranges.max(axis=1).rolling(14).mean().iloc[-1]
            
            sl_raw = curr - (1.5 * atr)
            sl_final = max(sl_raw, curr * 0.92) # KUNCI MAX LOSS 8%
            
            # LOGIKA RENTANG ENTRY (Support Dinamis, Batas Diskon Maksimal 3%)
            entry_atas = curr
            support_dinamis = max(vwap_val, ma20_val)
            batas_diskon_3pct = curr * 0.97
            
            if support_dinamis < curr:
                entry_bawah = max(support_dinamis, batas_diskon_3pct)
            else:
                entry_bawah = batas_diskon_3pct
                
            avg_entry = (entry_atas + entry_bawah) / 2
            
            tp = int(avg_entry + (avg_entry - sl_final) * 2.5) # RRR 1:2.5
            risk_pct = ((avg_entry - sl_final) / avg_entry) * 100
            reward_pct = ((tp - avg_entry) / avg_entry) * 100
            
            # Tentukan Sentimen
            if curr > ma20_val and curr > ma200_val: sentiment = "BULLISH (Sangat Kuat) 🐂"
            elif curr > ma20_val: sentiment = "MILD BULLISH (Jangka Pendek) 🐃"
            elif curr < ma200_val: sentiment = "BEARISH (Hati-hati) 🐻"
            else: sentiment = "NEUTRAL / SIDEWAYS 😐"

            # Rekomendasi 
            if f_score >= 80 and t_score >= 70: rekomen = "STRONG BUY"
            elif f_score >= 60 and t_score >= 50: rekomen = "BUY / ACCUMULATE"
            elif t_score < 40 or f_score < 40: rekomen = "SELL / AVOID"
            else: rekomen = "HOLD / WAIT"

            color_rec = "#00ff00" if "BUY" in rekomen else "#ffcc00" if "HOLD" in rekomen else "#ff0000"
            status_syariah_teks = "✅ Masuk Daftar ISSI" if is_syariah(ticker_input) else "❌ Belum/Bukan Efek Syariah"

            # --- 5. TAMPILAN OUTPUT ---
            html_output = f"""
            <div style="background-color:#1e2b3e; padding:25px; border-radius:12px; border-left:10px solid {color_rec}; color:#e0e0e0; font-family:sans-serif;">
                <h3 style="margin-top:0; color:white; margin-bottom:5px;">{info.get('longName', ticker)} ({ticker})</h3>
                <p style="margin-top:0; font-size:14px; color:#b0bec5; margin-bottom:15px;">
                    Sektor: <b>{sector.title()}</b> | Kategori Syariah: <b>{status_syariah_teks}</b>
                </p>
                <ul style="line-height:1.8; padding-left:20px; font-size:16px;">
                    <li><b>1. Fundamental Score ({f_score}/100):</b> ROE {roe:.1f}%, {lbl_solv}, EPS Grw {eps_g:.1f}%, Rev Grw {rev_g:.1f}%.
                        <br><span style="font-size:14px;"><i>Tingkat Kepercayaan Data: {label_konfidensi}</i></span>
                    </li>
                    <li><b>2. Technical Score ({t_score}/100):</b> Value Rata2 Rp {avg_value_ma20/1e9:.1f} M, RSI {rsi:.1f}.</li>
                    <li><b>3. Sentiment Pasar:</b> <b>{sentiment}</b></li>
                    <li><b>4. Alasan Utama:</b> Tren {'Positif' if t_score >= 50 else 'Negatif'}, Valuasi (PER {curr_per:.1f}x), Div. Yield {div_yield:.2f}%.</li>
                    <li><b>5. Risk Utama:</b> Volatilitas pasar & Potensi koreksi jika gagal bertahan di area Support.</li>
                    <li><b>6. Rekomendasi Final:</b> <span style="color:{color_rec}; font-weight:bold; font-size:18px;">{rekomen}</span></li>
                    <li><b>7. Trading Plan:</b><br>
                        • Harga Sekarang: Rp {int(curr):,.0f}<br>
                        • Usulan Entry: Rp {int(entry_bawah):,.0f} - Rp {int(entry_atas):,.0f} (Maks -3%)<br>
                        • Titik TP: Rp {tp:,.0f} (Potensi Reward: +{reward_pct:.1f}%)<br>
                        • Titik SL: Rp {sl_final:,.0f} (Batas Risiko: -{risk_pct:.1f}%)
                    </li>
                    <li><b>8. Timeframe:</b> {'Investasi Jangka Panjang' if f_score >= 80 else 'Swing Trading Pendek'}.</li>
                </ul>
            </div>
            """
            st.markdown(html_output, unsafe_allow_html=True)
            
            with st.expander("Lihat Detail Data Mentah"):
                st.write(f"Sektor Terdeteksi: {sector.title()} | Bank? {is_bank}")
                st.write(f"Raw DER: {raw_der} | Normalized Ratio: {der_ratio:.2f}")
                st.write(f"Support Dinamis (VWAP/MA20): Rp {int(support_dinamis):,.0f}")
                st.write(f"Metrik Fundamental Tersedia: {metrik_tersedia} dari {total_metrik_fun} indikator")
                
                if is_bank: 
                    st.write(f"CAR Terpakai: {car_approx:.2f}% ({'Hasil Scraping' if car_scraped is not None else 'Estimasi Proxy'})")
                    st.write(f"NPL Terpakai: {npl_approx:.2f}% ({'Hasil Scraping' if npl_scraped is not None else 'Estimasi Proxy'})")

            # --- 6. DISCLAIMER ---
            st.markdown("---")
            st.caption("⚠️ **DISCLAIMER:** Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma indikator teknikal dan fundamental. Seluruh informasi yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi tanggung jawab pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik dan *Do Your Own Research* (DYOR).")
