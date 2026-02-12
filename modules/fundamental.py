import streamlit as st
import pandas as pd
from modules.data_loader import ambil_data_fundamental_lengkap # Panggil Gudang Data

def run_fundamental():
    st.title("📊 Analisa Fundamental Pro (Deep Dive)")
    st.markdown("---")

    # 1. INPUT
    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="BBRI").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah Fundamental {ticker_input}"):
        try:
            with st.spinner(f"Mengambil data {ticker_input} dari server pusat..."):
                # --- PANGGIL DATA DARI DATA_LOADER (CACHE) ---
                info, financials, balance, cashflow, history = ambil_data_fundamental_lengkap(ticker)
                
                # VALIDASI DARURAT
                # Jika Info kosong, kita coba bangun info darurat dari history harga
                curr_price = 0
                if info and 'currentPrice' in info:
                    curr_price = info['currentPrice']
                elif not history.empty:
                    curr_price = history['Close'].iloc[-1]
                
                if curr_price == 0:
                    st.error("Data saham tidak ditemukan sama sekali. Cek kode saham.")
                    return

                # --- HEADER DATA ---
                st.subheader(f"🏢 {info.get('longName', ticker_input)}")
                
                market_cap = info.get('marketCap', 0)
                pe = info.get('trailingPE', 0)
                pbv = info.get('priceToBook', 0)
                roe = info.get('returnOnEquity', 0)
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Harga", f"Rp {curr_price:,.0f}")
                c2.metric("Market Cap", f"Rp {market_cap/1e12:,.1f} T" if market_cap else "-")
                c3.metric("ROE", f"{roe*100:.1f}%" if roe else "-")
                c4.metric("PBV", f"{pbv:.2f}x" if pbv else "-")

                st.markdown("---")

                # ==========================================
                # BAB 1: OVERVIEW PERUSAHAAN
                # ==========================================
                st.header("1. OVERVIEW PERUSAHAAN")
                
                # Analisa Posisi Pasar
                if market_cap > 100e12: posisi = "Market Leader (Big Cap)"
                elif market_cap > 10e12: posisi = "Challenger (Mid Cap)"
                else: posisi = "Niche Player (Small Cap)"
                
                st.write(f"**Bisnis Utama:** {info.get('longBusinessSummary', 'Deskripsi tidak tersedia.')[:500]}...")
                st.write(f"**Posisi Industri:** {posisi}")
                st.write(f"**Competitive Advantage:** Brand Equity Kuat & Skala Ekonomi ({info.get('industry', '-')})")

                # ==========================================
                # BAB 2: ANALISA KEUANGAN (3-5 TAHUN)
                # ==========================================
                st.header("2. ANALISA KEUANGAN (Trend 4 Tahun)")
                
                if not financials.empty:
                    # Bersihkan Data
                    rev = financials.loc['Total Revenue'] if 'Total Revenue' in financials.index else pd.Series()
                    ni = financials.loc['Net Income'] if 'Net Income' in financials.index else pd.Series()
                    
                    if not rev.empty and not ni.empty:
                        # Buat DataFrame Trend
                        years = [d.year for d in rev.index]
                        df_trend = pd.DataFrame({
                            "Revenue (T)": (rev.values / 1e12),
                            "Net Income (T)": (ni.values / 1e12),
                            "Net Margin (%)": (ni.values / rev.values) * 100
                        }, index=years)
                        
                        # Tampilkan Tabel (Dibalik agar tahun terbaru di kiri jika perlu, atau default yfinance)
                        st.table(df_trend.head(4).style.format("{:.2f}"))

                        # Analisa Trend
                        last_rev = rev.iloc[0]; prev_rev = rev.iloc[1]
                        rev_growth = ((last_rev - prev_rev) / prev_rev) * 100
                        st.info(f"📈 **Revenue Growth (YoY):** {rev_growth:+.2f}%")
                    else:
                        st.warning("Data detail Revenue/Net Income tidak lengkap.")
                else:
                    st.warning("Laporan keuangan historis tidak tersedia.")
                
                # Rasio Kesehatan
                col_k1, col_k2, col_k3 = st.columns(3)
                col_k1.write(f"**Debt to Equity:** {info.get('debtToEquity', 0):.2f}")
                col_k2.write(f"**Current Ratio:** {info.get('currentRatio', 0):.2f}")
                col_k3.write(f"**EPS Growth:** {info.get('earningsGrowth', 0)*100:.1f}%")

                # ==========================================
                # BAB 3: VALUASI
                # ==========================================
                st.header("3. VALUASI & HARGA WAJAR")
                
                eps = info.get('trailingEps', 0)
                bvps = info.get('bookValue', 0)
                
                # Benchmark Valuasi (Estimasi)
                avg_pe_industry = 15.0 # Benchmark Konservatif
                avg_pbv_industry = 2.0 # Benchmark Konservatif
                
                st.write("#### Perbandingan Valuasi")
                val_data = pd.DataFrame({
                    "Metode": ["PER (Price to Earning)", "PBV (Price to Book)"],
                    "Saham Ini": [f"{pe:.2f}x", f"{pbv:.2f}x"],
                    "Wajar / Industri": [f"{avg_pe_industry:.2f}x", f"{avg_pbv_industry:.2f}x"],
                    "Status": ["Murah" if pe < avg_pe_industry else "Mahal", "Murah" if pbv < avg_pbv_industry else "Mahal"]
                })
                st.table(val_data)

                # Hitung Harga Wajar (Fair Value)
                if eps > 0:
                    fair_pe = eps * avg_pe_industry
                    fair_pbv = bvps * avg_pbv_industry
                    fair_price = (fair_pe + fair_pbv) / 2
                    
                    mos = ((fair_price - curr_price) / fair_price) * 100
                    
                    st.success(f"### 🎯 Harga Wajar (Estimasi): Rp {fair_price:,.0f}")
                    st.metric("Margin of Safety (MoS)", f"{mos:.1f}%")
                else:
                    st.warning("Perusahaan sedang merugi (EPS Negatif), sulit menentukan harga wajar dengan metode PER.")
                    fair_price = curr_price
                    mos = -99

                # ==========================================
                # BAB 4: PROSPEK BISNIS
                # ==========================================
                st.header("4. PROSPEK BISNIS")
                st.write("**Outlook Industri:**")
                st.write("• Industri ini memiliki korelasi positif dengan pertumbuhan PDB dan daya beli masyarakat.")
                
                st.write("**Growth Catalyst:**")
                st.write("• Inovasi digital dan ekspansi pangsa pasar.")
                st.write("• Efisiensi biaya operasional yang berkelanjutan.")
                
                st.write("**Risk Factors:**")
                st.write("• Volatilitas harga komoditas dan bahan baku.")
                st.write("• Ketidakpastian suku bunga dan nilai tukar.")

                # ==========================================
                # BAB 5: REKOMENDASI
                # ==========================================
                st.header("5. REKOMENDASI")
                
                # Logika Rekomendasi
                if mos > 15 and roe > 0.1:
                    status = "BUY"
                    color = "green"
                    msg = "Saham Undervalued dengan fundamental (ROE) yang kuat."
                elif mos > -5:
                    status = "HOLD"
                    color = "orange"
                    msg = "Harga sudah wajar (Fair Value). Layak simpan."
                else:
                    status = "SELL / WAIT"
                    color = "red"
                    msg = "Harga Premium (Overvalued). Tunggu koreksi."

                st.markdown(f"""
                <div style="background-color:#1e2b3e; padding:20px; border-radius:10px; border-left:10px solid {color};">
                    <h2 style="color:{color}; margin-top:0;">{status}</h2>
                    <p><b>Alasan:</b> {msg}</p>
                    <hr>
                    <p><b>Target Price (12 Bln):</b> Rp {fair_price:,.0f}</p>
                    <p><b>Stop Loss (Jaga Modal):</b> Rp {curr_price * 0.9:,.0f}</p>
                </div>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Terjadi kesalahan data: {e}")
