import streamlit as st
import yfinance as yf
import pandas as pd

# --- FUNGSI CACHE KHUSUS FUNDAMENTAL ---
# Kita taruh di sini agar Bapak tidak perlu ubah file data_loader.py lagi
@st.cache_data(ttl=3600, show_spinner=False)
def ambil_data_fundamental(ticker):
    """
    Mengambil data Info, Financials, dan Balance Sheet sekaligus
    dan menyimpannya di memori selama 1 jam.
    """
    stock = yf.Ticker(ticker)
    
    # 1. Ambil Info
    try:
        info = stock.info
    except:
        info = {}
        
    # 2. Ambil Laporan Keuangan (3-4 tahun terakhir)
    try:
        financials = stock.financials
        balance_sheet = stock.balance_sheet
    except:
        financials = pd.DataFrame()
        balance_sheet = pd.DataFrame()
        
    return info, financials, balance_sheet

def run_fundamental():
    st.title("📊 Analisa Fundamental Pro (Deep Dive)")
    st.markdown("---")

    # 1. INPUT
    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="ASII").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah Fundamental {ticker_input}"):
        try:
            with st.spinner(f"Sedang membedah laporan keuangan {ticker_input}..."):
                # --- AMBIL DATA DARI CACHE ---
                info, financials, balance = ambil_data_fundamental(ticker)
                
                if not info or 'currentPrice' not in info:
                    st.error("Data fundamental tidak ditemukan.")
                    return

                # DATA DASAR
                curr_price = info.get('currentPrice', 0)
                market_cap = info.get('marketCap', 0)
                pe = info.get('trailingPE', 0)
                pbv = info.get('priceToBook', 0)
                roe = info.get('returnOnEquity', 0)
                dps = info.get('dividendRate', 0)
                
                # Hitung Yield Manual (Anti Error)
                div_yield = (dps / curr_price) * 100 if curr_price > 0 else 0

                # HEADER METRICS
                st.subheader(f"🏢 {info.get('longName', ticker_input)}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Harga", f"Rp {curr_price:,.0f}")
                c2.metric("Market Cap", f"Rp {market_cap/1e12:,.1f} T")
                c3.metric("ROE", f"{roe*100:.1f}%")
                c4.metric("Div. Yield", f"{div_yield:.2f}%")

                st.markdown("---")

                # --- BAB 1: OVERVIEW PERUSAHAAN ---
                st.subheader("1. OVERVIEW & MODEL BISNIS")
                st.write(f"**Sektor:** {info.get('sector', 'N/A')} | **Industri:** {info.get('industry', 'N/A')}")
                st.info(f"**Bisnis Utama:** {info.get('longBusinessSummary', 'Deskripsi tidak tersedia.')[:500]}...")
                
                posisi = "Market Leader" if market_cap > 100e12 else "Challenger/Second Liner" if market_cap > 10e12 else "Niche Player"
                st.write(f"**Posisi Pasar:** {posisi} dengan kapitalisasi Rp {market_cap/1e12:,.1f} Triliun.")

                # --- BAB 2: KINERJA KEUANGAN (TREND) ---
                st.subheader("2. TREND KINERJA KEUANGAN (Tahunan)")
                if not financials.empty:
                    # Ambil Revenue & Net Income
                    try:
                        rev = financials.loc['Total Revenue']
                        ni = financials.loc['Net Income']
                        
                        # Buat DataFrame rapi
                        df_trend = pd.DataFrame({
                            "Pendapatan (Triliun)": (rev.values / 1e12).round(2),
                            "Laba Bersih (Triliun)": (ni.values / 1e12).round(2),
                            "Net Margin (%)": ((ni.values / rev.values) * 100).round(1)
                        }, index=rev.index.year)
                        
                        st.table(df_trend.head(4)) # Tampilkan 4 tahun terakhir
                        
                        # Analisa Singkat Trend
                        last_ni = ni.iloc[0]
                        prev_ni = ni.iloc[1]
                        growth = ((last_ni - prev_ni) / prev_ni) * 100
                        st.write(f"**Pertumbuhan Laba (YoY):** {growth:+.1f}%")
                        
                    except:
                        st.warning("Format laporan keuangan tidak standar, tabel trend dilewati.")
                else:
                    st.warning("Data historis keuangan tidak tersedia.")

                c_f1, c_f2 = st.columns(2)
                with c_f1:
                    st.write(f"- **Debt to Equity (DER):** {info.get('debtToEquity', 0):.2f}x")
                with c_f2:
                    st.write(f"- **Current Ratio:** {info.get('currentRatio', 0):.2f}x")

                # --- BAB 3: VALUASI & HARGA WAJAR ---
                st.subheader("3. VALUASI WAJAR (FAIR VALUE)")
                
                # Rumus Harga Wajar Konservatif
                eps = info.get('trailingEps', 0)
                bvps = info.get('bookValue', 0)
                
                # Asumsi: PE Wajar 12x, PBV Wajar 1.5x (Bisa disesuaikan)
                fair_pe = eps * 12.0
                fair_pbv = bvps * 1.5
                fair_price = (fair_pe + fair_pbv) / 2
                
                mos = ((fair_price - curr_price) / fair_price) * 100
                
                col_v1, col_v2 = st.columns(2)
                with col_v1:
                    st.write(f"**PER Saat Ini:** {pe:.2f}x")
                    st.write(f"**PBV Saat Ini:** {pbv:.2f}x")
                with col_v2:
                    st.info(f"**Harga Wajar (Est):** Rp {fair_price:,.0f}")
                    st.metric("Margin of Safety (MoS)", f"{mos:.1f}%")

                # --- BAB 4: PROSPEK & RISIKO ---
                st.subheader("4. PROSPEK BISNIS")
                st.write("✅ **Katalis Positif:** Pemulihan ekonomi makro dan efisiensi operasional perusahaan.")
                st.write("⚠️ **Faktor Risiko:** Fluktuasi nilai tukar Rupiah, perubahan regulasi, dan volatilitas harga komoditas.")

                # --- BAB 5: REKOMENDASI ---
                st.subheader("5. REKOMENDASI FINAL")
                
                # Logika Rekomendasi
                if mos > 20 and roe > 0.1:
                    rec = "STRONG BUY"
                    color = "green"
                    reason = "Saham salah harga (Undervalued) dengan fundamental kuat (ROE > 10%)."
                elif mos > 0:
                    rec = "BUY"
                    color = "blue"
                    reason = "Harga masih di bawah nilai wajar, aman untuk akumulasi."
                elif mos > -10:
                    rec = "HOLD"
                    color = "orange"
                    reason = "Harga wajar (Fair Value). Layak simpan untuk dividen."
                else:
                    rec = "SELL / WAIT"
                    color = "red"
                    reason = "Harga sudah premium (Overvalued). Tunggu koreksi."

                st.markdown(f"""
                <div style='background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 10px solid {color};'>
                    <h2 style='color: {color}; margin:0;'>{rec}</h2>
                    <p><b>Alasan:</b> {reason}</p>
                    <hr>
                    <p><b>Target Price (1 Thn):</b> Rp {fair_price:,.0f} | <b>Stop Loss:</b> Rp {curr_price*0.9:,.0f}</p>
                </div>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Terjadi kesalahan saat mengambil data. Coba kode lain. Error: {e}")
