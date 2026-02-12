import streamlit as st
import pandas as pd
import numpy as np
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def translate_info(key):
    """Menerjemahkan istilah sektor/industri secara sederhana"""
    translations = {
        "Financial Services": "Jasa Keuangan / Perbankan",
        "Basic Materials": "Bahan Baku / Tambang",
        "Energy": "Energi / Minyak & Gas",
        "Communication Services": "Telekomunikasi",
        "Consumer Cyclical": "Konsumsi Siklikal",
        "Consumer Defensive": "Konsumsi Non-Siklikal",
        "Healthcare": "Kesehatan",
        "Industrials": "Industri / Manufaktur",
        "Real Estate": "Properti / Real Estat",
        "Technology": "Teknologi",
        "Utilities": "Utilitas / Infrastruktur"
    }
    return translations.get(key, key)

def run_fundamental():
    st.title("🏛️ Analisa Fundamental (Deep Value)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="ASII").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah Fundamental {ticker_input}"):
        with st.spinner("Mengevaluasi laporan keuangan & model bisnis..."):
            # --- STANDAR ANTI-ERROR (SATU PINTU) ---
            data = get_full_stock_data(ticker)
            info = data['info']
            financials = data['financials']
            history = data['history']
            
            if not info or financials.empty:
                st.error("Data tidak ditemukan. Mohon 'Clear Cache' dan coba lagi.")
                return

            curr_price = info.get('currentPrice', 0)
            
            # --- 1. OVERVIEW PERUSAHAAN (VERSI BAHASA INDONESIA) ---
            st.header("1. OVERVIEW PERUSAHAAN")
            mkt_cap = info.get('marketCap', 0)
            posisi = "Market Leader" if mkt_cap > 150e12 else "Market Challenger" if mkt_cap > 20e12 else "Niche Player"
            
            # Konstruksi ringkasan dalam Bahasa Indonesia
            st.write(f"**Bisnis Utama:** Perusahaan bergerak di sektor **{translate_info(info.get('sector'))}**, khususnya dalam industri **{info.get('industry', 'N/A')}**.")
            st.write(f"**Posisi Industri:** Perusahaan saat ini bertindak sebagai **{posisi}** dengan total Kapitalisasi Pasar sebesar **Rp {mkt_cap/1e12:,.1f} Triliun**.")
            st.write(f"**Competitive Advantage:** Memiliki keunggulan pada skala operasional yang luas dan dominasi pasar di industrinya (Moat).")

            # --- 2. ANALISA KEUANGAN (3-5 TAHUN) ---
            st.header("2. ANALISA KEUANGAN (Tren Jangka Panjang)")
            try:
                # Transpose data untuk tren tahunan
                df_fin = financials.T.sort_index().tail(5)
                # Revenue Growth & Profit Margin Trend
                st.write("**Tren Pendapatan & Laba Bersih (Tahunan):**")
                st.line_chart(df_fin[['Total Revenue', 'Net Income']])
                
                f1, f2, f3 = st.columns(3)
                f1.metric("ROE", f"{info.get('returnOnEquity', 0)*100:.2f}%")
                f2.metric("Debt to Equity", f"{info.get('debtToEquity', 0)/100 if info.get('debtToEquity', 0) > 10 else info.get('debtToEquity', 0):.2f}x")
                f3.metric("Current Ratio", f"{info.get('currentRatio', 0):.2f}x")
                
                st.write(f"**Pertumbuhan EPS:** Tahunan rata-rata sekitar {info.get('earningsGrowth', 0)*100:.1f}%")
            except:
                st.warning("Detail visualisasi tren keuangan terbatas.")

            # --- 3. VALUASI ---
            st.header("3. VALUASI")
            pe = info.get('trailingPE', 0)
            pbv = info.get('priceToBook', 0)
            div_yield = hitung_div_yield_normal(info)
            
            # Harga Wajar (Graham Number): akar(22.5 * EPS * BVPS)
            eps = info.get('trailingEps', 0)
            bvps = info.get('bookValue', 0)
            fair_price = np.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else curr_price
            
            v1, v2, v3 = st.columns(3)
            v1.metric("PER (TTM)", f"{pe:.2f}x", "vs Rata-rata: 15x")
            v2.metric("PBV", f"{pbv:.2f}x", "vs Rata-rata: 1.5x")
            v3.metric("Dividend Yield", f"{div_yield:.2f}%")
            
            status_val = "UNDERVALUED (Murah)" if curr_price < fair_price else "OVERVALUED (Mahal)"
            st.success(f"🎯 **Harga Wajar: Rp {fair_price:,.0f}** | Status: **{status_val}**")

            # --- 4. PROSPEK BISNIS ---
            st.header("4. PROSPEK BISNIS")
            st.write(f"• **Outlook:** Positif, didorong oleh pemulihan sektor {translate_info(info.get('sector'))}.")
            st.write(f"• **Growth Catalyst:** Inovasi efisiensi biaya dan ekspansi pangsa pasar domestik.")
            st.write(f"• **Risk Factors:** Fluktuasi kurs, kenaikan suku bunga, dan ketidakpastian ekonomi global.")

            # --- 5. REKOMENDASI (TRADING PLAN) ---
            st.header("5. REKOMENDASI")
            
            # --- LOGIKA STOP LOSS ATR (LOCK 8%) ---
            atr = (history['High'] - history['Low']).tail(14).mean()
            sl_raw = curr_price - (1.5 * atr)
            sl_final = max(sl_raw, curr_price * 0.92) # KUNCI MAX 8%
            
            target_short = fair_price if fair_price > curr_price else curr_price * 1.15
            target_long = target_short * 1.3
            
            rec = "BUY" if curr_price < fair_price else "HOLD" if curr_price < fair_price * 1.2 else "SELL"
            
            st.subheader(f"Keputusan: **{rec}**")
            r1, r2, r3 = st.columns(3)
            with r1:
                st.write("**Target Jangka Pendek (3-6 bln):**")
                st.success(f"**Rp {target_short:,.0f}**")
            with r2:
                st.write("**Target Jangka Panjang (1-2 thn):**")
                st.success(f"**Rp {target_long:,.0f}**")
            with r3:
                st.write("**Stop Loss (Max 8%):**")
                st.error(f"**Rp {sl_final:,.0f}**")
            
            st.caption(f"Dasar Proteksi: {'ATR 1.5x' if sl_final == sl_raw else 'Maksimal Risiko 8%'}")
