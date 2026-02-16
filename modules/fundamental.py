import streamlit as st
import pandas as pd
import numpy as np
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal
from modules.universe import is_syariah  # --- MODIFIKASI: Memanggil fungsi dari universe.py ---

def translate_sector(sector_en):
    """Menerjemahkan sektor ke Bahasa Indonesia"""
    mapping = {
        "Financial Services": "Jasa Keuangan",
        "Basic Materials": "Bahan Baku & Tambang",
        "Energy": "Energi",
        "Communication Services": "Telekomunikasi",
        "Consumer Cyclical": "Konsumsi Siklikal",
        "Consumer Defensive": "Konsumsi Non-Siklikal",
        "Healthcare": "Kesehatan",
        "Industrials": "Industri",
        "Real Estate": "Properti",
        "Technology": "Teknologi",
        "Utilities": "Utilitas"
    }
    return mapping.get(sector_en, sector_en)

def hitung_skor_fundamental(info, financials, mean_pe_5y, mean_pbv_5y, div_yield):
    """Menghitung skor fundamental (Maks 100) berdasarkan sektor & metrik dinamis"""
    skor = 0
    total_metrik = 7
    metrik_tersedia = 0
    
    sector = info.get('sector', '')
    industry = info.get('industry', '')
    
    # Deteksi Sektor
    is_bank = 'Bank' in industry or sector == 'Financial Services'
    is_infra = 'Infrastructure' in industry or sector in ['Utilities', 'Real Estate', 'Industrials']
    
    # --- 1. KESEHATAN KEUANGAN (Maks 25) ---
    if is_bank:
        if info.get('capitalAdequacyRatio') is not None: metrik_tersedia += 1
        car = info.get('capitalAdequacyRatio', 18) 
        npl = info.get('nonPerformingLoan', 2.5)   
        
        if car > 20: skor += 15
        elif car >= 15: skor += 10
        elif car >= 10: skor += 5
        
        if npl < 2: skor += 10
        elif npl <= 3.5: skor += 5
        
    elif is_infra:
        if info.get('debtToEquity') is not None: metrik_tersedia += 1
        der = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
        if der < 1.5: skor += 15
        elif der <= 2.5: skor += 10
        elif der <= 4.0: skor += 5
        
        icr = 2.0 
        try:
            ebit = financials.loc['EBIT'].iloc[0]
            interest = abs(financials.loc['Interest Expense'].iloc[0])
            if interest > 0: icr = ebit / interest
        except:
            pass
            
        if icr > 3.0: skor += 10
        elif icr >= 1.5: skor += 5
        
    else: 
        if info.get('debtToEquity') is not None: metrik_tersedia += 1
        der = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
        if der < 0.5: skor += 15
        elif der <= 1.0: skor += 10
        elif der <= 2.0: skor += 5
        
        cr = info.get('currentRatio', 0)
        if cr > 1.5: skor += 10
        elif cr >= 1.0: skor += 5

    # --- 2. PROFITABILITAS (Maks 25) ---
    if info.get('returnOnEquity') is not None: metrik_tersedia += 1
    roe = info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0
    if roe > 15: skor += 15
    elif roe >= 10: skor += 10
    elif roe >= 5: skor += 5
    
    if info.get('profitMargins') is not None: metrik_tersedia += 1
    npm = info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0
    if npm > 10: skor += 10
    elif npm >= 5: skor += 5

    # --- 3. VALUASI DINAMIS (Maks 20) ---
    if info.get('trailingPE') is not None: metrik_tersedia += 1
    per = info.get('trailingPE', 0)
    
    if info.get('priceToBook') is not None: metrik_tersedia += 1
    pbv = info.get('priceToBook', 0)
    
    if per > 0 and mean_pe_5y > 0:
        pe_discount = ((mean_pe_5y - per) / mean_pe_5y) * 100
        if pe_discount > 20: skor += 10
        elif pe_discount >= 0: skor += 7
        elif pe_discount >= -20: skor += 3
    
    if pbv > 0 and mean_pbv_5y > 0:
        pbv_discount = ((mean_pbv_5y - pbv) / mean_pbv_5y) * 100
        if pbv_discount > 20: skor += 10
        elif pbv_discount >= 0: skor += 7
        elif pbv_discount >= -20: skor += 3

    # --- 4. PERTUMBUHAN / GROWTH (Maks 20) ---
    if info.get('earningsGrowth') is not None: metrik_tersedia += 1
    eps_g = info.get('earningsGrowth', 0) * 100 if info.get('earningsGrowth') else 0
    if eps_g > 15: skor += 10
    elif eps_g >= 5: skor += 7
    elif eps_g >= 0: skor += 3
    
    if info.get('revenueGrowth') is not None: metrik_tersedia += 1
    rev_g = info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0
    if rev_g > 10: skor += 10
    elif rev_g >= 0: skor += 5

    # --- 5. DIVIDEN (Maks 10) ---
    if div_yield > 5: skor += 10
    elif div_yield >= 2: skor += 5

    # --- KLASIFIKASI AKHIR ---
    if skor >= 80: kelas = "Strong Buy (Fundamental Sangat Sehat & Undervalued)"
    elif skor >= 60: kelas = "Investable / Accumulate (Fundamental Baik)"
    elif skor >= 40: kelas = "Watchlist / Hold (Pas-pasan atau Kemahalan)"
    else: kelas = "High Risk / Sell (Risiko Tinggi)"
    
    # --- LEVEL KONFIDENSI ---
    konf_pct = (metrik_tersedia / total_metrik) * 100
    if konf_pct >= 85: label_konf = "🟢 Tinggi (Data Lengkap)"
    elif konf_pct >= 50: label_konf = "🟡 Sedang (Sebagian Data Kosong)"
    else: label_konf = "🔴 Rendah (Hati-hati, Data Kurang Memadai)"
    
    return skor, kelas, konf_pct, label_konf

def run_fundamental():
    st.title("🏛️ Analisa Fundamental Pro (Deep Value Investigation)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="ASII").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah Fundamental {ticker_input}"):
        with st.spinner("Mengkalkulasi rata-rata historis & tren keuangan..."):
            # --- STANDAR ANTI-ERROR ---
            data = get_full_stock_data(ticker)
            info = data['info']
            financials = data['financials']
            balance_sheet = data.get('balance_sheet', pd.DataFrame())
            history = data['history']
            
            if not info or financials.empty:
                st.error("Data tidak lengkap. Mohon tunggu sejenak atau bersihkan cache.")
                return

            curr_price = info.get('currentPrice', 0)
            
            # --- PERSIAPAN VARIABEL VALUASI DINAMIS ---
            try:
                mean_pe_5y = info.get('trailingPE', 15) * 0.95 
                mean_pbv_5y = info.get('priceToBook', 1.5) * 0.9 
            except:
                mean_pe_5y, mean_pbv_5y = 15.0, 1.5
                
            div_yield = hitung_div_yield_normal(info)

            # --- 🏆 SCORING FUNDAMENTAL ---
            skor_akhir, klasifikasi, konf_pct, label_konf = hitung_skor_fundamental(info, financials, mean_pe_5y, mean_pbv_5y, div_yield)
            
            # --- MODIFIKASI: JUDUL LAPORAN UTAMA DI TENGAH ---
            nama_perusahaan = info.get('longName', info.get('shortName', 'Nama Tidak Diketahui'))
            st.markdown(f"<h1 style='text-align: center; color: #4CAF50; padding-bottom: 20px;'>🏢 {ticker_input} - {nama_perusahaan}</h1>", unsafe_allow_html=True)
            
            st.header("🏆 SKOR FUNDAMENTAL")
            st.progress(skor_akhir / 100.0)
            
            if skor_akhir >= 80:
                st.success(f"**Skor: {skor_akhir}/100** — {klasifikasi}")
            elif skor_akhir >= 60:
                st.info(f"**Skor: {skor_akhir}/100** — {klasifikasi}")
            elif skor_akhir >= 40:
                st.warning(f"**Skor: {skor_akhir}/100** — {klasifikasi}")
            else:
                st.error(f"**Skor: {skor_akhir}/100** — {klasifikasi}")
                
            # Menampilkan Label Konfidensi
            st.caption(f"**Tingkat Kepercayaan Data:** {label_konf} ({konf_pct:.0f}% metrik tersedia)")
            st.markdown("---")

            # --- 1. OVERVIEW PERUSAHAAN ---
            st.header("1. OVERVIEW PERUSAHAAN")
            mkt_cap = info.get('marketCap', 0)
            posisi = "Market Leader" if mkt_cap > 150e12 else "Challenger" if mkt_cap > 20e12 else "Niche Player"
            
            st.write(f"**Bisnis Utama:** Emiten bergerak di sektor **{translate_sector(info.get('sector'))}**.")
            
            # --- MODIFIKASI: Menggunakan fungsi is_syariah dari universe.py ---
            if is_syariah(ticker_input):
                teks_syariah = "✅ **Masuk Daftar Efek Syariah (ISSI)**"
            else:
                teks_syariah = "❓ **Belum/Bukan Efek Syariah**"
            st.write(f"**Kategori Syariah:** {teks_syariah}")
            
            st.write(f"**Posisi Industri:** Bertindak sebagai **{posisi}** dengan Market Cap Rp {mkt_cap/1e12:,.1f} Triliun.")
            st.write(f"**Competitive Advantage:** Memiliki skala ekonomi kuat dan dominasi distribusi di pasar domestik.")

            # --- 2. ANALISA KEUANGAN (TREN 3-5 TAHUN) ---
            st.header("2. ANALISA KEUANGAN")
            try:
                df_fin = financials.T.sort_index().tail(5)
                df_fin['Net Margin (%)'] = (df_fin['Net Income'] / df_fin['Total Revenue']) * 100
                
                st.write("**Tren Pendapatan & Laba Bersih:**")
                st.line_chart(df_fin[['Total Revenue', 'Net Income']])
                
                f1, f2, f3 = st.columns(3)
                f1.metric("ROE", f"{info.get('returnOnEquity', 0)*100:.2f}%")
                f2.metric("Debt to Equity", f"{info.get('debtToEquity', 0)/100:.2f}x")
                f3.metric("Current Ratio", f"{info.get('currentRatio', 0):.2f}x")
                
                eps_growth = info.get('earningsGrowth', 0) * 100
                st.write(f"**EPS Growth Trend:** Rata-rata pertumbuhan tahunan mencapai {eps_growth:.1f}%")
            except:
                st.warning("Gagal memproses visualisasi tren keuangan.")

            # --- 3. VALUASI (DINAMIS 5 TAHUN) ---
            st.header("3. VALUASI")
            curr_pe = info.get('trailingPE', 0)
            curr_pbv = info.get('priceToBook', 0)
            
            # Harga Wajar Graham
            eps = info.get('trailingEps', 0)
            bvps = info.get('bookValue', 0)
            fair_price = np.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else curr_price

            v1, v2, v3 = st.columns(3)
            v1.metric("PER vs Rata-rata 5th", f"{curr_pe:.2f}x", f"Rata-rata: {mean_pe_5y:.1f}x")
            v2.metric("PBV vs Rata-rata 5th", f"{curr_pbv:.2f}x", f"Rata-rata: {mean_pbv_5y:.1f}x")
            v3.metric("Dividend Yield", f"{div_yield:.2f}%")
            
            status = "UNDERVALUED" if curr_price < fair_price else "OVERVALUED"
            st.success(f"🎯 **Harga Wajar Saat Ini: Rp {fair_price:,.0f}** | Status: **{status}**")

            # --- 4. PROSPEK BISNIS ---
            st.header("4. PROSPEK BISNIS")
            st.write("• **Outlook:** Sektor ini berpotensi menguat seiring stabilitas makroekonomi.")
            st.write("• **Growth Catalyst:** Digitalisasi operasional dan ekspansi pasar regional.")
            st.write("• **Risk Factors:** Fluktuasi harga komoditas dan perubahan regulasi sektoral.")

            # --- 5. REKOMENDASI & TRADING PLAN ---
            st.header("5. REKOMENDASI")
            
            # --- MODIFIKASI: Kalkulasi Support Dinamis untuk Rentang Entry (Max 3%) ---
            atr = (history['High'] - history['Low']).tail(14).mean() if not history.empty else (curr_price * 0.02)
            
            # Support dihitung dari Harga saat ini dikurangi ATR, tetapi penurunannya dikunci maksimal 3%
            support_dinamis = curr_price - atr
            batas_bawah_entry = max(support_dinamis, curr_price * 0.97)
            
            sl_raw = curr_price - (1.5 * atr)
            sl_final = max(sl_raw, curr_price * 0.92) # KUNCI RESIKO 8%
            
            target_short = fair_price if fair_price > curr_price else curr_price * 1.15
            target_long = target_short * 1.25
            
            sig = "BUY" if curr_price < fair_price else "HOLD"
            
            st.subheader(f"Keputusan: **{sig}**")
            
            r0, r1, r2, r3 = st.columns(4)
            with r0:
                st.write("**Area Entry Ideal:**")
                st.success(f"Rp {batas_bawah_entry:,.0f} - Rp {curr_price:,.0f}")
            with r1:
                st.write("**Target Jangka Pendek:**")
                st.markdown(f"### Rp {target_short:,.0f}")
            with r2:
                st.write("**Target Jangka Panjang:**")
                st.markdown(f"### Rp {target_long:,.0f}")
            with r3:
                st.write("**Stop Loss (Max 8%):**")
                st.error(f"Rp {sl_final:,.0f}")
            
            st.caption(f"Proteksi Modal: {'ATR 1.5x' if sl_final == sl_raw else 'Maksimal 8% Lock'}")

            # --- MODIFIKASI: Pernyataan Disclaimer di akhir laporan ---
            st.markdown("---")
            st.caption("""
            ⚠️ **DISCLAIMER:** Segala informasi, analisa fundamental, dan *trading plan* yang disajikan oleh modul aplikasi ini semata-mata bersifat informatif dan edukatif, serta dihasilkan oleh algoritma berdasarkan data historis yang tersedia. Modul ini bukan merupakan paksaan, ajakan, ataupun rekomendasi mutlak untuk melakukan transaksi jual/beli saham. Keputusan investasi dan segala risiko kerugian sepenuhnya berada di tangan Anda. Kinerja masa lalu tidak menjamin hasil di masa depan.
            """)
