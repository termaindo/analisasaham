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
            with st.spinner(f"Sedang menghitung data dividen {ticker_input}..."):
                stock = yf.Ticker(ticker)
                info = stock.info
                dividends = stock.dividends

                if not info.get('currentPrice'):
                    st.error("Data tidak ditemukan. Pastikan kode saham benar.")
                    return

                # --- PERBAIKAN LOGIKA PERHITUNGAN ---
                curr_price = info.get('currentPrice', 0)
                # dividendRate adalah DPS (dalam Rupiah)
                dps = info.get('dividendRate', 0) 
                # Hitung Yield secara manual agar akurat (DPS / Harga * 100)
                calculated_yield = (dps / curr_price) * 100 if curr_price > 0 else 0
                payout_ratio = info.get('payoutRatio', 0) * 100
                
                st.subheader(f"📊 Summary {info.get('longName', ticker_input)}")
                
                # TAMPILAN HEADER (Sekarang ada 4 kolom agar lebih lengkap)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Harga Saat Ini", f"Rp {curr_price:,.0f}")
                c2.metric("Dividen (DPS)", f"Rp {dps:,.0f}") # Menampilkan Rupiah
                c3.metric("Dividend Yield", f"{calculated_yield:.2f}%") # Menampilkan Persen
                c4.metric("Payout Ratio", f"{payout_ratio:.1f}%")

                st.markdown("---")

                # --- 1. OVERVIEW PERUSAHAAN ---
                st.markdown("### 1. OVERVIEW PERUSAHAAN")
                st.write(f"**Bisnis & Model:** {info.get('longBusinessSummary', 'N/A')[:350]}...")
                st.write(f"**Market Cap:** Rp {info.get('marketCap', 0)/1e12:,.2f} Triliun.")

                # --- 4. DIVIDEND HISTORY (Tabel 5 Tahun Terakhir) ---
                st.markdown("### 4. DIVIDEND HISTORY (5 Tahun Terakhir)")
                if not dividends.empty:
                    # Ambil data dividen dan kelompokkan per tahun
                    df_div = dividends.to_frame()
                    df_div['Year'] = df_div.index.year
                    hist_div = df_div.groupby('Year')['Dividends'].sum().tail(5)
                    
                    # Tampilkan tabel yang rapi
                    st.table(hist_div.rename("Dividen (Rp)"))
                else:
                    st.info("Data riwayat dividen tahunan tidak tersedia di database.")

                # --- 7. REKOMENDASI ---
                st.markdown("### 7. REKOMENDASI")
                # Kriteria: Layak jika yield > 5%
                status_div = "LAYAK (High Yield)" if calculated_yield > 5 else "MODERAT"
                st.success(f"**Kesimpulan:** Saham ini tergolong {status_div}.")
                st.write(f"* **Yield vs Deposito:** {'Lebih tinggi dari rata-rata deposito bank' if calculated_yield > 4 else 'Setara dengan deposito bank'}.")

        except Exception as e:
            st.error(f"Gagal memproses data. Kesalahan: {e}")
