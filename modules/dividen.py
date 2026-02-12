import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from modules.data_loader import ambil_data_dividen_lengkap

def run_dividen():
    st.title("💰 Analisa Dividen Pro (Income Investing)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="ITMG").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah Dividen {ticker_input}"):
        with st.spinner("Mengaudit riwayat pembayaran dividen..."):
            # 1. AMBIL DATA DARI CACHE
            info, raw_div, cashflow, financials, history = ambil_data_dividen_lengkap(ticker)
            
            # Validasi Awal
            if raw_div.empty:
                st.warning(f"⚠️ {ticker_input} tidak memiliki riwayat pembagian dividen di database.")
                return

            # Data Harga & Info Dasar
            curr_price = info.get('currentPrice', history['Close'].iloc[-1] if not history.empty else 0)
            dps_ttm = info.get('dividendRate', 0)
            yield_ttm = (dps_ttm / curr_price * 100) if curr_price > 0 else 0
            payout_ratio = info.get('payoutRatio', 0) * 100

            # Header
            st.subheader(f"🏢 {info.get('longName', ticker_input)}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Harga Saham", f"Rp {curr_price:,.0f}")
            c2.metric("Dividend Yield (TTM)", f"{yield_ttm:.2f}%")
            c3.metric("Payout Ratio", f"{payout_ratio:.1f}%")
            c4.metric("Freq Bayar", "1-2x Setahun")

            st.markdown("---")

            # ==========================================
            # 1. DIVIDEND HISTORY (5 TAHUN TERAKHIR)
            # ==========================================
            st.header("1. RIWAYAT DIVIDEN (5 TAHUN)")
            
            # Proses Data Dividen (Group by Year)
            raw_div.index = pd.to_datetime(raw_div.index)
            # Filter 5 tahun terakhir
            current_year = pd.Timestamp.now().year
            df_div_year = raw_div.groupby(raw_div.index.year).sum()
            df_div_5y = df_div_year.loc[current_year-5 : current_year-1] # Ambil 5 tahun full ke belakang
            
            if not df_div_5y.empty:
                # Chart Bar History
                fig = go.Figure(data=[
                    go.Bar(name='Total Dividen/Tahun', x=df_div_5y.index, y=df_div_5y.values, marker_color='gold')
                ])
                fig.update_layout(title="Total Dividen Per Lembar (DPS) Tahunan", height=300)
                st.plotly_chart(fig, use_container_width=True)
                
                # Cek Konsistensi
                is_growing = df_div_5y.is_monotonic_increasing
                avg_div = df_div_5y.mean()
                st.info(f"💡 **Konsistensi:** Rata-rata DPS 5 tahun: Rp {avg_div:,.0f}/lembar. Trend: {'Meningkat/Stabil' if is_growing else 'Fluktuatif'}.")
            else:
                st.warning("Data historis 5 tahun tidak lengkap.")

            # ==========================================
            # 2. KESEHATAN KEUANGAN (SUSTAINABILITY)
            # ==========================================
            st.header("2. KESEHATAN KEUANGAN (Sustainability)")
            
            if not cashflow.empty and not financials.empty:
                try:
                    # Ambil Free Cash Flow (Operating Cash Flow - Capex)
                    ocf = cashflow.loc['Total Cash From Operating Activities'].iloc[0]
                    capex = cashflow.loc['Capital Expenditures'].iloc[0]
                    fcf = ocf + capex # Capex biasanya negatif
                    
                    # Ambil Total Dividen yang Dibayarkan (Cash Flow Financing)
                    div_paid = abs(cashflow.loc['Cash Dividends Paid'].iloc[0]) if 'Cash Dividends Paid' in cashflow.index else 0
                    
                    # Cek Rasio Pembayaran
                    sustainability = (fcf / div_paid) if div_paid > 0 else 0
                    
                    col_h1, col_h2 = st.columns(2)
                    with col_h1:
                        st.write(f"**Free Cash Flow (FCF):** Rp {fcf/1e12:,.1f} T")
                        st.write(f"**Total Dividen Dibayar:** Rp {div_paid/1e12:,.1f} T")
                    with col_h2:
                        if fcf > div_paid:
                            st.success(f"✅ **AMAN (Sustainable):** Perusahaan membayar dividen menggunakan uang tunai hasil operasi (FCF > Dividen).")
                        else:
                            st.error(f"⚠️ **BERISIKO:** Dividen lebih besar dari Free Cash Flow. Perusahaan mungkin menggunakan tabungan atau utang.")
                    
                    # Cek Utang
                    der = info.get('debtToEquity', 0)
                    st.caption(f"Catatan Utang: Debt to Equity Ratio {der:.2f}x. (Ideal < 1.0x untuk pembagi dividen).")

                except:
                    st.warning("Data Cash Flow tidak standar, analisa sustainability dilewati.")
            else:
                st.warning("Laporan Arus Kas tidak tersedia.")

            # ==========================================
            # 3. PROYEKSI TAHUN DEPAN
            # ==========================================
            st.header("3. PROYEKSI DIVIDEN")
            
            # Estimasi Dividen = EPS TTM x Rata-rata Payout Ratio
            eps_ttm = info.get('trailingEps', 0)
            avg_payout = payout_ratio / 100
            
            if avg_payout > 1.0: avg_payout = 0.8 # Cap di 80% jika data aneh
            
            est_dps = eps_ttm * avg_payout
            est_yield = (est_dps / curr_price * 100) if curr_price > 0 else 0
            
            c_p1, c_p2 = st.columns(2)
            c_p1.info(f"🔮 **Est. DPS Tahun Depan:** Rp {est_dps:,.0f}")
            c_p2.metric("Potensi Yield", f"{est_yield:.2f}%", f"{est_yield - yield_ttm:.2f}% vs TTM")
            
            st.write("**Skenario:**")
            st.write(f"Jika kinerja laba stabil (EPS Rp {eps_ttm:,.0f}) dan manajemen membagikan {avg_payout*100:.0f}% labanya.")

            # ==========================================
            # 4. REKOMENDASI & ENTRY PRICE
            # ==========================================
            st.header("4. REKOMENDASI & STRATEGI")
            
            # Logika Rekomendasi
            deposito_rate = 4.5 # Benchmark Deposito Bank BUKU 4
            
            if est_yield > 7 and sustainability > 1: # Yield Tinggi & Aman
                rec = "STRONG BUY (Dividend Gem 💎)"
                color = "green"
            elif est_yield > deposito_rate:
                rec = "BUY (Income Stock)"
                color = "blue"
            elif est_yield > 2:
                rec = "HOLD / GROWTH"
                color = "orange"
            else:
                rec = "NOT ATTRACTIVE"
                color = "red"
            
            # Hitung Harga Diskon untuk Yield Idaman
            target_yield = 7.0 # Kita mau yield minimal 7%
            ideal_price = est_dps / (target_yield/100)
            
            st.markdown(f"""
            <div style="background-color:#1e2b3e; padding:20px; border-radius:10px; border-left:10px solid {color};">
                <h2 style="color:{color}; margin-top:0;">{rec}</h2>
                <p><b>Yield ({est_yield:.1f}%)</b> vs <b>Deposito ({deposito_rate}%)</b></p>
                <hr>
                <p><b>Strategi Maximizing Yield:</b></p>
                <p>Agar mendapatkan Dividend Yield <b>7%</b>, antri beli (Buy Limit) di harga:</p>
                <h3 style="margin:0;">Rp {ideal_price:,.0f}</h3>
            </div>
            """, unsafe_allow_html=True)
