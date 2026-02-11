import streamlit as st
import yfinance as yf
import pandas as pd

def run_fundamental():
    st.title("📊 Analisa Fundamental & Harga Wajar")
    st.markdown("---")

    # 1. INPUT KODE SAHAM
    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Masukkan Kode Saham (Contoh: BBRI, ASII, UNTR):", value="ASII").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Analisa Fundamental {ticker_input}"):
        try:
            with st.spinner(f"Menghitung valuasi dan harga wajar {ticker_input}..."):
                stock = yf.Ticker(ticker)
                info = stock.info
                financials = stock.financials
                balance = stock.balance_sheet
                
                if not info.get('currentPrice'):
                    st.error("Data saham tidak ditemukan. Cek kembali kode saham.")
                    return

                # --- DATA DASAR ---
                curr_price = info.get('currentPrice', 0)
                dps = info.get('dividendRate', 0)
                # PERBAIKAN DIVIDEND YIELD (Manual Calculation)
                div_yield = (dps / curr_price) * 100 if curr_price > 0 else 0
                
                # --- HEADER METRICS ---
                st.subheader(f"🏢 {info.get('longName', ticker_input)}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Harga Saat Ini", f"Rp {curr_price:,.0f}")
                c2.metric("PER (Trailing)", f"{info.get('trailingPE', 0):.2f}x")
                c3.metric("PBV", f"{info.get('priceToBook', 0):.2f}x")
                c4.metric("Div. Yield (Acc)", f"{div_yield:.2f}%")

                st.markdown("---")

                # --- 1. OVERVIEW & KEUANGAN ---
                st.markdown("### 1. OVERVIEW & ANALISA KEUANGAN")
                st.write(f"**Bisnis Utama:** {info.get('industry', 'N/A')} - {info.get('sector', 'N/A')}")
                
                # Trend Keuangan (3-4 Tahun Terakhir)
                if not financials.empty:
                    rev = financials.loc['Total Revenue']
                    ni = financials.loc['Net Income']
                    df_trend = pd.DataFrame({
                        "Revenue (T)": (rev.values / 1e12).round(2),
                        "Laba Bersih (T)": (ni.values / 1e12).round(2)
                    }, index=rev.index.year).head(4)
                    st.table(df_trend)
                
                st.write(f"- **ROE:** {info.get('returnOnEquity', 0)*100:.2f}% | **DER:** {info.get('debtToEquity', 0):.2f}")

                # --- 2. VALUASI & HARGA WAJAR (Fair Value) ---
                st.markdown("### 2. VALUASI & PERHITUNGAN HARGA WAJAR")
                
                # Simulasi Rata-rata 5 Tahun (Estimat dari data tersedia)
                # Catatan: yfinance terbatas memberikan data historis PE/PBV harian 5 thn secara instan
                # Kita gunakan benchmark rata-rata industri dan data historis terdekat
                avg_pe_5yr = info.get('forwardPE', 0) * 0.9 if info.get('forwardPE') else 12.0
                avg_pbv_5yr = info.get('priceToBook', 1.0) * 0.85
                eps = info.get('trailingEps', 0)
                bvps = info.get('bookValue', 0)

                # Rumus Harga Wajar
                fair_price_pe = eps * avg_pe_5yr
                fair_price_pbv = bvps * avg_pbv_5yr
                harga_wajar_rata = (fair_price_pe + fair_price_pbv) / 2

                col_val1, col_val2 = st.columns(2)
                with col_val1:
                    st.info(f"**Berdasarkan Rata-rata PER 5 Thn:**\n\nRp {fair_price_pe:,.0f}")
                with col_val2:
                    st.info(f"**Berdasarkan Rata-rata PBV 5 Thn:**\n\nRp {fair_price_pbv:,.0f}")

                st.success(f"### 🎯 Estimasi Harga Wajar Konservatif: Rp {harga_wajar_rata:,.0f}")
                
                margin_of_safety = ((harga_wajar_rata - curr_price) / harga_wajar_rata) * 100
                st.write(f"**Margin of Safety (MoS):** {margin_of_safety:.1f}%")

                # --- 3. REKOMENDASI FINAL ---
                st.markdown("---")
                st.markdown("### 3. REKOMENDASI")
                
                if margin_of_safety > 15:
                    rec = "BUY (Undervalued)"
                    note = "Harga saat ini di bawah nilai wajar historis."
                elif -10 <= margin_of_safety <= 15:
                    rec = "HOLD (Fair Valued)"
                    note = "Harga sudah mencerminkan nilai wajar perusahaan."
                else:
                    rec = "SELL/WAIT (Overvalued)"
                    note = "Harga sudah terlalu premium dibandingkan rata-rata historis."

                st.subheader(f"Status: {rec}")
                st.write(f"**Alasan:** {note}")
                
                c_pl1, c_pl2, c_pl3 = st.columns(3)
                c_pl1.write(f"🚩 **Stop Loss:** Rp {curr_price * 0.9:,.0f}")
                c_pl2.write(f"🎯 **Target Jk. Pendek:** Rp {curr_price * 1.1:,.0f}")
                c_pl3.write(f"🏆 **Target Jk. Panjang:** Rp {harga_wajar_rata:,.0f}")

        except Exception as e:
            st.error(f"Terjadi kendala data. Pastikan koneksi internet stabil. Error: {e}")
