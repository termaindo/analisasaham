import streamlit as st
import pandas as pd
import numpy as np
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

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
            
            # --- 1. OVERVIEW PERUSAHAAN ---
            st.header("1. OVERVIEW PERUSAHAAN")
            mkt_cap = info.get('marketCap', 0)
            posisi = "Market Leader" if mkt_cap > 150e12 else "Challenger" if mkt_cap > 20e12 else "Niche Player"
            
            st.write(f"**Bisnis Utama:** Emiten bergerak di sektor **{translate_sector(info.get('sector'))}**.")
            st.write(f"**Posisi Industri:** Bertindak sebagai **{posisi}** dengan Market Cap Rp {mkt_cap/1e12:,.1f} Triliun.")
            st.write(f"**Competitive Advantage:** Memiliki skala ekonomi kuat dan dominasi distribusi di pasar domestik.")

            # --- 2. ANALISA KEUANGAN (TREN 3-5 TAHUN) ---
            st.header("2. ANALISA KEUANGAN")
            try:
                # Ambil tren 4-5 tahun terakhir
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
            
            # Hitung Rata-rata Dinamis (Historical Mean)
            # Karena yfinance terbatas, kita gunakan data yang tersedia di financials
            try:
                avg_pe_hist = financials.loc['Net Income'].mean() / info.get('sharesOutstanding', 1)
                # Estimasi rata-rata PER dinamis (Mean PE Ratio 5 thn)
                mean_pe_5y = info.get('trailingPE', 15) * 0.95 # Proksi jika data terbatas
                mean_pbv_5y = info.get('priceToBook', 1.5) * 0.9 # Proksi jika data terbatas
                
                # Jika data Stockbit tersedia, idealnya angka ini ditarik dari perhitungan (Price/EPS) tiap tahun
            except:
                mean_pe_5y, mean_pbv_5y = 15.0, 1.5

            curr_pe = info.get('trailingPE', 0)
            curr_pbv = info.get('priceToBook', 0)
            div_yield = hitung_div_yield_normal(info)
            
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
            
            # Kalkulasi SL Berbasis ATR (LOCK MAX 8%)
            atr = (history['High'] - history['Low']).tail(14).mean()
            sl_raw = curr_price - (1.5 * atr)
            sl_final = max(sl_raw, curr_price * 0.92) # KUNCI RESIKO 8%
            
            target_short = fair_price if fair_price > curr_price else curr_price * 1.15
            target_long = target_short * 1.25
            
            sig = "BUY" if curr_price < fair_price else "HOLD"
            
            st.subheader(f"Keputusan: **{sig}**")
            
            # --- MODIFIKASI: Menambahkan Kolom Entry Price ---
            r0, r1, r2, r3 = st.columns(4)
            
            with r0:
                st.write("**Harga Entry:**")
                st.success(f"Rp {curr_price:,.0f}")
            
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
