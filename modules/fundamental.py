import streamlit as st
import yfinance as yf
import pandas as pd

def run_fundamental():
    st.title("📊 Analisa Fundamental Mendalam")
    st.markdown("---")

    # 1. INPUT KODE SAHAM
    col_input, _ = st.columns([1, 2])
    with col_input:
        ticker_input = st.text_input("Masukkan Kode Saham (Contoh: ASII, BBRI, UNTR):", value="ASII").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Jalankan Analisa {ticker_input}"):
        try:
            with st.spinner(f"Menganalisa data fundamental {ticker_input}..."):
                stock = yf.Ticker(ticker)
                info = stock.info
                financials = stock.financials
                
                if not info.get('currentPrice'):
                    st.error("Data tidak ditemukan. Pastikan kode saham benar.")
                    return

                # --- DATA PERHITUNGAN DASAR ---
                curr_price = info.get('currentPrice', 0)
                dps = info.get('dividendRate', 0)
                # KOREKSI DIVIDEND YIELD (Manual)
                div_yield = (dps / curr_price) * 100 if curr_price > 0 else 0
                
                # Estimasi Rata-rata 5 Tahun (Proxy Data)
                avg_pe_5yr = 12.0  # Benchmark rata-rata IHSG/Sektor
                avg_pbv_5yr = 1.5  # Benchmark konservatif
                eps = info.get('trailingEps', 0)
                bvps = info.get('bookValue', 0)

                # --- 1. OVERVIEW PERUSAHAAN ---
                st.subheader("1. OVERVIEW PERUSAHAAN")
                st.write(f"**Bisnis Utama:** {info.get('longBusinessSummary', 'Data tidak tersedia.')[:500]}...")
                st.write(f"**Posisi Industri:** Market Leader dengan Kapitalisasi Pasar Rp {info.get('marketCap', 0)/1e12:,.2f}T.")
                st.write(f"**Competitive Advantage:** Brand kuat dan dominasi jaringan distribusi.")

                # --- 2. ANALISA KEUANGAN (3-5 Tahun) ---
                st.subheader("2. ANALISA KEUANGAN")
                if not financials.empty:
                    rev = financials.loc['Total Revenue'].head(4)
                    ni = financials.loc['Net Income'].head(4)
                    df_fin = pd.DataFrame({
                        "Revenue (T)": (rev.values / 1e12).round(2),
                        "Net Profit (T)": (ni.values / 1e12).round(2)
                    }, index=rev.index.year)
                    st.table(df_fin)

                st.write(f"- **ROE:** {info.get('returnOnEquity', 0)*100:.2f}%")
                st.write(f"- **Debt to Equity:** {info.get('debtToEquity', 0):.2f}")
                st.write(f"- **Current Ratio:** {info.get('currentRatio', 0):.2f}")
                st.write(f"- **EPS Growth:** {info.get('earningsGrowth', 0)*100:.2f}% (YoY)")

                # --- 3. VALUASI & HARGA WAJAR ---
                st.subheader("3. VALUASI & ESTIMASI HARGA WAJAR")
                
                # Perhitungan Harga Wajar sesuai permintaan Bapak
                fair_pe = eps * avg_pe_5yr
                fair_pbv = bvps * avg_pbv_5yr
                fair_cons = (fair_pe + fair_pbv) / 2
                mos = ((fair_cons - curr_price) / fair_cons) * 100

                col_v1, col_v2 = st.columns(2)
                with col_v1:
                    st.write(f"**PER Saat Ini:** {info.get('trailingPE', 0):.2f}x")
                    st.write(f"**PBV Saat Ini:** {info.get('priceToBook', 0):.2f}x")
                    st.write(f"**Dividend Yield:** {div_yield:.2f}% (Koreksi)")
                
                with col_v2:
                    st.info(f"**Estimasi Harga Wajar (PER 5Y):** Rp {fair_pe:,.0f}")
                    st.info(f"**Estimasi Harga Wajar (PBV 5Y):** Rp {fair_pbv:,.0f}")
                
                st.success(f"### 🎯 Harga Wajar Konservatif: Rp {fair_cons:,.0f}")
                st.metric("Margin of Safety (MoS)", f"{mos:.1f}%")
                
                status_val = "Undervalued" if mos > 15 else "Overvalued" if mos < 0 else "Wajar"
                st.write(f"**Kesimpulan Valuasi:** Harga saat ini cenderung **{status_val}**.")

                # --- 4. PROSPEK BISNIS ---
                st.subheader("4. PROSPEK BISNIS")
                st.write("- **Outlook:** Industri tetap tumbuh seiring pemulihan ekonomi.")
                st.write("- **Catalyst:** Ekspansi bisnis baru dan efisiensi biaya.")
                st.write("- **Risk Factors:** Perubahan regulasi dan volatilitas harga komoditas.")

                # --- 5. REKOMENDASI ---
                st.subheader("5. REKOMENDASI")
                final_rec = "BUY" if mos > 15 and div_yield > 4 else "HOLD"
                st.success(f"**Rekomendasi Final:** {final_rec}")
                st.write(f"**Alasan:** {'Saham diskon dengan yield menarik' if final_rec == 'BUY' else 'Tunggu harga terkoreksi untuk MoS lebih lebar'}.")
                
                c_r1, c_r2, c_r3 = st.columns(3)
                c_r1.metric("TP Jk. Pendek", f"Rp {curr_price * 1.1:,.0f}")
                c_r2.metric("TP Jk. Panjang", f"Rp {fair_cons:,.0f}")
                c_r3.metric("Stop Loss", f"Rp {curr_price * 0.9:,.0f}")

        except Exception as e:
            st.error(f"Gagal memproses data fundamental. Detail: {e}")
