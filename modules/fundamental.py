import streamlit as st
import pandas as pd
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_fundamental():
    st.title("🏛️ Analisa Fundamental Pro")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="ASII").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah Fundamental {ticker_input}"):
        with st.spinner("Menganalisa laporan keuangan..."):
            data = get_full_stock_data(ticker)
            info = data["info"]
            financials = data["financials"]
            
            if not info:
                st.error("Data tidak ditemukan atau server sibuk. Coba 1 menit lagi.")
                return

            # --- BAB 1: OVERVIEW ---
            st.header("1. OVERVIEW PERUSAHAAN")
            st.write(f"**Bisnis Utama:** {info.get('longBusinessSummary', 'N/A')[:500]}...")
            mkt_cap = info.get('marketCap', 0)
            posisi = "Market Leader" if mkt_cap > 100e12 else "Challenger"
            st.info(f"**Posisi Industri:** {posisi} | **Market Cap:** Rp {mkt_cap/1e12:,.1f} T")

            # --- BAB 2: ANALISA KEUANGAN ---
            st.header("2. ANALISA KEUANGAN (Trend 4 Tahun)")
            if not financials.empty:
                try:
                    rev = financials.loc['Total Revenue'].head(4)
                    ni = financials.loc['Net Income'].head(4)
                    df_fin = pd.DataFrame({"Revenue (T)": rev/1e12, "Laba Bersih (T)": ni/1e12}, index=rev.index.year)
                    st.table(df_fin.style.format("{:.2f}"))
                except: st.write("Data trend terbatas.")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("ROE", f"{info.get('returnOnEquity', 0)*100:.2f}%")
            c2.metric("DER", f"{info.get('debtToEquity', 0):.2f}x")
            c3.metric("Current Ratio", f"{info.get('currentRatio', 0):.2f}x")

            # --- BAB 3: VALUASI ---
            st.header("3. VALUASI & HARGA WAJAR")
            div_yield = hitung_div_yield_normal(info)
            curr_price = info.get('currentPrice', 0)
            eps = info.get('trailingEps', 0)
            bvps = info.get('bookValue', 0)
            
            # Estimasi Harga Wajar (Graham Number)
            fair_price = ((eps * 15) + (bvps * 1.5)) / 2 if (eps > 0 and bvps > 0) else curr_price
            mos = ((fair_price - curr_price) / fair_price) * 100
            
            v1, v2, v3 = st.columns(3)
            v1.metric("PER (TTM)", f"{info.get('trailingPE', 0):.2f}x")
            v2.metric("PBV", f"{info.get('priceToBook', 0):.2f}x")
            v3.metric("Div. Yield", f"{div_yield:.2f}%")
            
            st.success(f"🎯 **Harga Wajar: Rp {fair_price:,.0f}** (Margin of Safety: {mos:.1f}%)")

            # --- BAB 4 & 5: PROSPEK & REKOMENDASI ---
            st.header("4. PROSPEK & RISIKO")
            st.write("✅ **Catalyst:** Pemulihan daya beli & dominasi sektor.")
            st.write("⚠️ **Risk:** Kenaikan suku bunga & fluktuasi kurs.")

            st.header("5. REKOMENDASI")
            rec = "BUY" if mos > 15 else "HOLD" if mos > -5 else "SELL"
            st.success(f"**Rekomendasi Final: {rec}**")
            st.write(f"Target Jangka Panjang: **Rp {fair_price:,.0f}**")
