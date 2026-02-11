import streamlit as st
import yfinance as yf
import pandas as pd
import datetime

def run_dividen():
    st.title("💰 Analisa Saham Dividen (High Yield)")
    st.markdown("---")

    # 1. INPUT KODE SAHAM
    col1, col2 = st.columns([1, 2])
    with col1:
        ticker_input = st.text_input("Masukkan Kode Saham (Contoh: BBRI, ASII, PTBA):", value="PTBA").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Analisa Dividen {ticker_input}"):
        try:
            with st.spinner(f"Sedang mengumpulkan data dividen & keuangan {ticker_input}..."):
                stock = yf.Ticker(ticker)
                info = stock.info
                
                # Ambil Data Laporan Keuangan
                financials = stock.financials
                cashflow = stock.cashflow
                balance = stock.balance_sheet
                dividends = stock.dividends

                if info.get('quoteType') is None:
                    st.error("Data tidak ditemukan. Pastikan kode saham benar.")
                    return

                # --- HEADER RINGKASAN ---
                curr_price = info.get('currentPrice', 0)
                div_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
                
                st.subheader(f"📊 Summary {info.get('longName', ticker_input)}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Harga Saat Ini", f"Rp {curr_price:,.0f}")
                c2.metric("Dividend Yield", f"{div_yield:.2f}%")
                c3.metric("Payout Ratio", f"{info.get('payoutRatio', 0)*100:.1f}%")

                st.markdown("---")

                # --- 1. OVERVIEW PERUSAHAAN ---
                st.markdown("### 1. OVERVIEW PERUSAHAAN")
                st.write(f"- **Bisnis Utama:** {info.get('industry', 'N/A')} di sektor {info.get('sector', 'N/A')}.")
                st.write(f"- **Deskripsi:** {info.get('longBusinessSummary', 'N/A')[:300]}...")
                st.write(f"- **Posisi Industri:** Market Cap Rp {info.get('marketCap', 0)/1e12:,.2f} Triliun.")

                # --- 2. ANALISA KEUANGAN (3-5 Tahun) ---
                st.markdown("### 2. ANALISA KEUANGAN")
                if not financials.empty:
                    rev = financials.loc['Total Revenue'] if 'Total Revenue' in financials.index else pd.Series()
                    net_inc = financials.loc['Net Income'] if 'Net Income' in financials.index else pd.Series()
                    
                    st.write(f"- **Trend Pendapatan:** { 'Meningkat' if rev.iloc[0] > rev.iloc[-1] else 'Berfluktuasi' } dalam 4 tahun terakhir.")
                    st.write(f"- **Profit Margin:** {info.get('profitMargins', 0)*100:.2f}%")
                    st.write(f"- **ROE:** {info.get('returnOnEquity', 0)*100:.2f}%")
                    st.write(f"- **Debt to Equity:** {info.get('debtToEquity', 0):.2f}")
                else:
                    st.write("Data laporan keuangan tahunan tidak tersedia lengkap.")

                # --- 3. VALUASI ---
                st.markdown("### 3. VALUASI")
                pe_curr = info.get('trailingPE', 0)
                pbv_curr = info.get('priceToBook', 0)
                st.write(f"- **PER Saat Ini:** {pe_curr:.2f}x (Rata-rata Industri: {info.get('forwardPE', 'N/A')})")
                st.write(f"- **PBV Saat Ini:** {pbv_curr:.2f}x")
                st.write(f"- **Status:** {'Undervalued' if pbv_curr < 1.5 else 'Wajar/Premium'}")

                # --- 4. DIVIDEND HISTORY (5 Tahun Terakhir) ---
                st.markdown("### 4. DIVIDEND HISTORY")
                if not dividends.empty:
                    last_5_years = dividends.groupby(dividends.index.year).sum().tail(5)
                    st.write("- **Pembayaran per Saham (5 Thn Terakhir):**")
                    st.table(last_5_years)
                    st.write(f"- **Konsistensi:** Perusahaan membayar dividen secara berkala.")
                else:
                    st.write("- Data dividen historis tidak ditemukan di database.")

                # --- 5. KESEHATAN K
