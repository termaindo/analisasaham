import streamlit as st
import pandas as pd
from modules.data_loader import ambil_data_fundamental_lengkap

def run_fundamental():
    st.title("🏛️ Analisa Fundamental Mendalam")
    st.markdown("---")

    col1, _ = st.columns([1, 2])
    with col1:
        ticker_input = st.text_input("Kode Saham:", value="BBCA").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Analisa Fundamental {ticker_input}"):
        with st.spinner("Mengambil data laporan keuangan..."):
            try:
                info, financials, cashflow = ambil_data_fundamental_lengkap(ticker)
                
                if not info:
                    st.error("Data tidak ditemukan.")
                    return

                # --- FIX LOGIKA DIVIDEN YIELD ---
                raw_yield = info.get('dividendYield', 0)
                if raw_yield is None:
                    div_yield = 0
                elif raw_yield > 1: 
                    # Jika data sudah dalam bentuk persen (misal 4.5), biarkan
                    div_yield = raw_yield
                else: 
                    # Jika data dalam bentuk desimal (misal 0.045), kali 100
                    div_yield = raw_yield * 100

                # --- TAMPILAN DASHBOARD ---
                st.subheader(f"Profil Perusahaan: {info.get('longName', ticker)}")
                st.write(info.get('longBusinessSummary', 'Tidak ada ringkasan.'))

                # 1. Metrik Utama (Baris 1)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Current Price", f"Rp {info.get('currentPrice', 0):,.0f}")
                m2.metric("PER (TTM)", f"{info.get('trailingPE', 0):,.2f}x")
                m3.metric("PBV", f"{info.get('priceToBook', 0):,.2f}x")
                m4.metric("Div. Yield", f"{div_yield:,.2f}%")

                # 2. Profitabilitas (Baris 2)
                p1, p2, p3, p4 = st.columns(4)
                roe = info.get('returnOnEquity', 0) * 100
                npm = info.get('profitMargins', 0) * 100
                p1.metric("ROE", f"{roe:,.2f}%")
                p2.metric("NPM", f"{npm:,.2f}%")
                p3.metric("EPS", f"{info.get('trailingEps', 0):,.0f}")
                p4.metric("Market Cap", f"Rp {info.get('marketCap', 0)/1e12:,.2f} T")

                st.markdown("---")

                # 3. Analisa Pertumbuhan (Financials)
                st.subheader("📈 Pertumbuhan Laba & Pendapatan (4 Tahun Terakhir)")
                if not financials.empty:
                    # Ambil data Revenue dan Net Income
                    growth_df = financials.T[['Total Revenue', 'Net Income']].sort_index()
                    st.bar_chart(growth_df)
                    
                    with st.expander("Lihat Detail Angka Laporan Keuangan"):
                        st.dataframe(financials)
                else:
                    st.warning("Data laporan laba rugi tahunan tidak tersedia.")

                # 4. Arus Kas (Cash Flow)
                st.subheader("💸 Analisa Arus Kas (Cash Flow)")
                if not cashflow.empty:
                    c1, c2 = st.columns(2)
                    free_cf = info.get('freeCashflow', 0)
                    op_cf = info.get('operatingCashflow', 0)
                    
                    c1.write(f"**Operating Cash Flow:** Rp {op_cf:,.0f}")
                    c2.write(f"**Free Cash Flow:** Rp {free_cf:,.0f}")
                    
                    if free_cf > 0:
                        st.success("✅ Perusahaan menghasilkan kas bersih positif (Sehat).")
                    else:
                        st.warning("⚠️ Free Cash Flow negatif. Perhatikan beban belanja modal.")
                
                # 5. Kesimpulan Fundamental
                st.markdown("---")
                st.subheader("📝 Kesimpulan Fundamental")
                
                # Logika Skor Sederhana
                f_score = 0
                if roe > 15: f_score += 1
                if npm > 10: f_score += 1
                if div_yield > 3: f_score += 1
                if 0 < info.get('trailingPE', 0) < 15: f_score += 1
                if info.get('priceToBook', 0) < 2: f_score += 1

                if f_score >= 4:
                    st.success(f"**Status: SANGAT KUAT ({f_score}/5)** - Perusahaan memiliki fundamental solid dan valuasi menarik.")
                elif f_score >= 2:
                    st.info(f"**Status: MODERAT ({f_score}/5)** - Kinerja cukup baik, namun perhatikan nilai valuasi atau profitabilitas.")
                else:
                    st.error(f"**Status: LEMAH ({f_score}/5)** - Fundamental kurang memuaskan untuk investasi jangka panjang.")

            except Exception as e:
                st.error(f"Terjadi kesalahan saat memproses data: {e}")
