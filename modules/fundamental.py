import streamlit as st
import yfinance as yf
import pandas as pd

def run_fundamental():
    st.title("📊 Analisa Fundamental Mendalam")
    st.markdown("---")

    # 1. INPUT KODE SAHAM
    col_inp1, _ = st.columns([1, 2])
    with col_inp1:
        ticker_input = st.text_input("Masukkan Kode Saham (Contoh: ASII, UNTR, ICBP):", value="ASII").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Analisa Fundamental {ticker_input}"):
        try:
            with st.spinner(f"Menganalisa laporan keuangan {ticker_input}..."):
                stock = yf.Ticker(ticker)
                info = stock.info
                financials = stock.financials
                balance = stock.balance_sheet
                
                if not info.get('currentPrice'):
                    st.error("Data saham tidak ditemukan.")
                    return

                # --- HEADER RINGKASAN ---
                st.subheader(f"🏢 {info.get('longName', ticker_input)}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Harga", f"Rp {info.get('currentPrice', 0):,.0f}")
                c2.metric("PER", f"{info.get('trailingPE', 0):.2f}x")
                c3.metric("PBV", f"{info.get('priceToBook', 0):.2f}x")
                c4.metric("ROE", f"{info.get('returnOnEquity', 0)*100:.1f}%")

                # --- 1. OVERVIEW PERUSAHAAN ---
                st.markdown("### 1. OVERVIEW PERUSAHAAN")
                st.write(f"**Bisnis Utama:** {info.get('industry', 'N/A')} ({info.get('sector', 'N/A')})")
                st.write(f"**Deskripsi:** {info.get('longBusinessSummary', 'N/A')[:400]}...")
                st.write(f"**Competitive Advantage:** Market Cap Rp {info.get('marketCap', 0)/1e12:,.2f}T (Dominasi Pasar).")

                # --- 2. ANALISA KEUANGAN (Trend 3-4 Tahun) ---
                st.markdown("### 2. ANALISA KEUANGAN")
                if not financials.empty and not balance.empty:
                    # Menyiapkan data trend
                    revenue = financials.loc['Total Revenue'] if 'Total Revenue' in financials.index else pd.Series()
                    net_income = financials.loc['Net Income'] if 'Net Income' in financials.index else pd.Series()
                    
                    st.write("**Trend Pertumbuhan:**")
                    df_trend = pd.DataFrame({
                        "Tahun": revenue.index.year,
                        "Revenue (T)": (revenue.values / 1e12).round(2),
                        "Net Income (T)": (net_income.values / 1e12).round(2)
                    }).set_index("Tahun")
                    st.table(df_trend)

                    st.write(f"- **Profit Margin:** {info.get('profitMargins', 0)*100:.2f}%")
                    st.write(f"- **Debt to Equity:** {info.get('debtToEquity', 0):.2f}")
                    st.write(f"- **Current Ratio:** {info.get('currentRatio', 0):.2f}")
                else:
                    st.warning("Data trend tahunan terbatas di database.")

                # --- 3. VALUASI ---
                st.markdown("### 3. VALUASI")
                pbv = info.get('priceToBook', 0)
                pe = info.get('trailingPE', 0)
                status_v = "Undervalued" if pbv < 1.2 else "Overvalued" if pbv > 3 else "Wajar"
                
                st.write(f"- **PER vs Industri:** {pe:.2f}x (Estimasi Forward: {info.get('forwardPE', 'N/A')}x)")
                st.write(f"- **PBV vs Industri:** {pbv:.2f}x")
                st.write(f"- **Dividend Yield:** {info.get('dividendYield', 0)*100:.2f}%")
                st.write(f"- **Kesimpulan Valuasi:** Harga saat ini cenderung **{status_v}**.")

                # --- 4. PROSPEK BISNIS ---
                st.markdown("### 4. PROSPEK BISNIS")
                st.write(f"- **Catalyst:** Pemulihan konsumsi domestik dan efisiensi operasional.")
                st.write(f"- **Risk Factors:** Fluktuasi kurs Rupiah dan perubahan regulasi sektoral.")

                # --- 5. REKOMENDASI ---
                st.markdown("### 5. REKOMENDASI")
                rec = "BUY" if status_v != "Overvalued" and info.get('returnOnEquity', 0) > 0.1 else "HOLD"
                curr = info.get('currentPrice', 0)
                
                st.success(f"**Rekomendasi Final: {rec}**")
                st.write(f"- **Alasan:** {'Fundamental solid dengan ROE tinggi' if rec == 'BUY' else 'Valuasi sudah cukup premium'}.")
                
                c_plan1, c_plan2 = st.columns(2)
                c_plan1.write(f"🎯 **Target Jk. Pendek:** Rp {curr * 1.1:,.0f}")
                c_plan1.write(f"🎯 **Target Jk. Panjang:** Rp {curr * 1.3:,.0f}")
                c_plan2.write(f"🛑 **Stop Loss (Jaga Modal):** Rp {curr * 0.9:,.0f}")

        except Exception as e:
            st.error(f"Gagal mengambil data fundamental. Error: {e}")

    st.caption("Analisa ini berbasis data historis. Keputusan investasi tetap berada di tangan Anda, Pak Musa.")
