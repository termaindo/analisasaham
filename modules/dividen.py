import streamlit as st
import yfinance as yf
import pandas as pd

def run_dividen():
    st.title("💰 Analisa Saham Dividen (High Yield)")
    st.markdown("---")

    # 1. INPUT KODE SAHAM
    col_input = st.columns([1, 2])
    with col_input[0]:
        ticker_input = st.text_input("Masukkan Kode Saham:", value="ASII").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Analisa Dividen {ticker_input}"):
        try:
            with st.spinner(f"Sedang membedah data dividen {ticker_input}..."):
                stock = yf.Ticker(ticker)
                info = stock.info
                dividends = stock.dividends

                if not info.get('currentPrice'):
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
                st.write(f"**Bisnis & Model:** {info.get('longBusinessSummary', 'N/A')[:350]}...")
                st.write(f"**Posisi Industri:** Market Cap Rp {info.get('marketCap', 0)/1e12:,.2f} Triliun.")

                # --- 2. ANALISA KEUANGAN (3-5 Tahun) ---
                st.markdown("### 2. ANALISA KEUANGAN")
                st.write(f"* **ROE:** {info.get('returnOnEquity', 0)*100:.2f}%")
                st.write(f"* **Debt to Equity:** {info.get('debtToEquity', 0):.2f}")
                st.write(f"* **Current Ratio:** {info.get('currentRatio', 0):.2f}")

                # --- 3. VALUASI ---
                st.markdown("### 3. VALUASI")
                pbv = info.get('priceToBook', 0)
                st.write(f"* **PER:** {info.get('trailingPE', 0):.2f}x")
                st.write(f"* **PBV:** {pbv:.2f}x")
                st.write(f"* **Status:** {'Undervalued' if pbv < 1.2 else 'Wajar' if pbv < 2.5 else 'Premium'}")

                # --- 4. DIVIDEND HISTORY ---
                st.markdown("### 4. DIVIDEND HISTORY (5 Thn Terakhir)")
                if not dividends.empty:
                    # Ambil dividen per tahun
                    hist_div = dividends.groupby(dividends.index.year).sum().tail(5)
                    st.table(hist_div)
                else:
                    st.write("Data historis tidak tersedia.")

                # --- 5 & 6. KESEHATAN & PROYEKSI ---
                st.markdown("### 5 & 6. KESEHATAN & PROYEKSI")
                fcf = info.get('freeCashflow', 0)
                st.write(f"* **Sustainability:** {'Sangat Baik (Free Cash Flow Positif)' if fcf > 0 else 'Perlu Waspada'}")
                st.write(f"* **Potential Yield:** {div_yield:.2f}% pada harga saat ini.")

                # --- 7. REKOMENDASI ---
                st.markdown("### 7. REKOMENDASI")
                is_layak = "LAYAK" if div_yield > 6 else "MONITOR"
                st.success(f"**Keputusan:** {is_layak} sebagai High Yield Dividend Stock.")
                st.write(f"* **Entry Ideal:** Rp {curr_price * 0.97:,.0f} (Antri 3% di bawah harga sekarang).")

        except Exception as e:
            st.error(f"Gagal mengambil data. Detail: {e}")
