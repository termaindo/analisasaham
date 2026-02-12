import streamlit as st
import pandas as pd
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_fundamental():
    st.title("🏛️ Analisa Fundamental Pro")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="TINS").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah Fundamental {ticker_input}"):
        with st.spinner("Menganalisa laporan keuangan..."):
            data = get_full_stock_data(ticker)
            info = data["info"]
            financials = data["financials"]
            
            if not info:
                st.error("Data tidak ditemukan atau server sibuk. Mohon tunggu sejenak.")
                return

            # --- 1. RINGKASAN PERUSAHAAN ---
            st.header("1. RINGKASAN PERUSAHAAN")
            # Menjelaskan bahwa ringkasan bisnis berasal dari sumber global
            st.write(f"**Profil Bisnis (Sumber: Yahoo Finance):**")
            st.write(info.get('longBusinessSummary', 'Informasi tidak tersedia.'))
            
            mkt_cap = info.get('marketCap', 0)
            st.info(f"**Kapitalisasi Pasar:** Rp {mkt_cap/1e12:,.1f} Triliun")

            # --- 2. KINERJA KEUANGAN ---
            st.header("2. KINERJA KEUANGAN (Tren 4 Tahun)")
            if not financials.empty:
                try:
                    rev = financials.loc['Total Revenue'].head(4)
                    ni = financials.loc['Net Income'].head(4)
                    df_fin = pd.DataFrame({"Pendapatan (T)": rev/1e12, "Laba Bersih (T)": ni/1e12}, index=rev.index.year)
                    st.table(df_fin.style.format("{:.2f}"))
                except: st.write("Detail data keuangan terbatas.")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("ROE (Profitabilitas)", f"{info.get('returnOnEquity', 0)*100:.2f}%")
            c2.metric("DER (Hutang)", f"{info.get('debtToEquity', 0):.2f}x")
            c3.metric("Rasio Lancar", f"{info.get('currentRatio', 0):.2f}x")

            # --- 3. VALUASI & HARGA WAJAR ---
            st.header("3. VALUASI & ESTIMASI HARGA")
            div_yield = hitung_div_yield_normal(info)
            curr_price = info.get('currentPrice', 0)
            eps = info.get('trailingEps', 0)
            bvps = info.get('bookValue', 0)
            
            # Rumus Graham (Sederhana)
            fair_price = ((eps * 15) + (bvps * 1.5)) / 2 if (eps > 0 and bvps > 0) else curr_price
            mos = ((fair_price - curr_price) / fair_price) * 100
            
            v1, v2, v3 = st.columns(3)
            v1.metric("PER (Laba)", f"{info.get('trailingPE', 0):.2f}x")
            v2.metric("PBV (Buku)", f"{info.get('priceToBook', 0):.2f}x")
            v3.metric("Yield Dividen", f"{div_yield:.2f}%")
            
            st.success(f"🎯 **Estimasi Harga Wajar: Rp {fair_price:,.0f}** (Margin Keamanan: {mos:.1f}%)")

            # --- 4 & 5. KESIMPULAN ---
            st.header("4. ANALISA PROSPEK")
            st.write("• **Kekuatan:** Dominasi pasar dan efisiensi arus kas.")
            st.write("• **Risiko:** Perubahan regulasi dan harga komoditas global.")

            st.header("5. REKOMENDASI FINAL")
            status = "BELI" if mos > 15 else "TAHAN (HOLD)" if mos > -5 else "JUAL"
            st.success(f"**Peringkat: {status}**")
