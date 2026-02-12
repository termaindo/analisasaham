import streamlit as st
import pandas as pd
from modules.data_loader import ambil_data_fundamental_lengkap, ambil_data_history

def format_idr(value):
    """Format angka ke Triliun/Miliar Rupiah"""
    if value is None or value == 0: return "-"
    if abs(value) >= 1e12: return f"{value/1e12:.2f} T"
    if abs(value) >= 1e9: return f"{value/1e9:.2f} M"
    return f"{value:,.0f}"

def run_fundamental():
    st.title("📊 Analisa Fundamental: Deep Value")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Fund):", value="ASII").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah {ticker_input}"):
        with st.spinner("Menggali data fundamental..."):
            # 1. AMBIL DATA
            info, financials, balance = ambil_data_fundamental_lengkap(ticker)
            df_hist = ambil_data_history(ticker, period="1mo") # Ambil harga untuk backup

            # 2. DATA BACKUP (Jika Info Kosong)
            if df_hist.empty:
                st.error("Data saham tidak ditemukan.")
                return
            
            curr_price = info.get('currentPrice', df_hist['Close'].iloc[-1])
            shares = info.get('sharesOutstanding', 0)
            
            # Jika Market Cap kosong di Info, hitung manual
            market_cap = info.get('marketCap', 0)
            if market_cap == 0 and shares > 0:
                market_cap = curr_price * shares

            # 3. HEADER
            st.subheader(f"🏢 {info.get('longName', ticker_input)}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Harga Saat Ini", f"Rp {curr_price:,.0f}")
            c2.metric("Market Cap", format_idr(market_cap))
            c3.metric("Sektor", info.get('sector', '-'))

            st.markdown("---")

            # --- BAB 1: OVERVIEW & POSISI ---
            st.subheader("1. OVERVIEW PERUSAHAAN")
            summary = info.get('longBusinessSummary', 'Deskripsi bisnis tidak tersedia dari server.')[:500]
            st.write(f"**Bisnis Utama:** {summary}...")
            
            # Analisa Posisi
            if market_cap > 100e12: posisi = "Market Leader (Big Cap)"
            elif market_cap > 10e12: posisi = "Challenger (Mid Cap)"
            else: posisi = "Niche Player (Small Cap)"
            st.info(f"**Posisi Industri:** {posisi}")

            # --- BAB 2: KINERJA KEUANGAN (TREND) ---
            st.subheader("2. TREND KINERJA (3-4 TAHUN)")
            
            if not financials.empty:
                # Coba ambil baris Revenue & Net Income dengan berbagai kemungkinan nama
                try:
                    rev = financials.loc['Total Revenue'] if 'Total Revenue' in financials.index else financials.iloc[0]
                    ni = financials.loc['Net Income'] if 'Net Income' in financials.index else financials.iloc[-1]
                    
                    # Tampilkan Tabel
                    df_trend = pd.DataFrame({
                        "Pendapatan": [format_idr(x) for x in rev.head(4)],
                        "Laba Bersih": [format_idr(x) for x in ni.head(4)],
                        "Net Margin": [f"{(n/r)*100:.1f}%" if r!=0 else "-" for n, r in zip(ni.head(4), rev.head(4))]
                    }, index=rev.head(4).index.year)
                    st.table(df_trend)

                    # Hitung Growth manual jika tidak ada di info
                    rev_now = rev.iloc[0]; rev_prev = rev.iloc[1]
                    growth = ((rev_now - rev_prev)/rev_prev)*100
                    st.write(f"📈 **Revenue Growth (YoY):** {growth:+.2f}%")
                except:
                    st.warning("Struktur data keuangan saham ini unik/berbeda, tabel trend dilewati.")
            else:
                st.warning("Laporan keuangan detail tidak tersedia di database.")

            # --- BAB 3: VALUASI & HARGA WAJAR ---
            st.subheader("3. VALUASI & HARGA WAJAR")
            
            # Ambil Data Valuasi (Dengan Fallback Manual)
            eps = info.get('trailingEps', 0)
            if eps == 0 and shares > 0 and not financials.empty: 
                # Hitung EPS Manual: Laba Bersih / Jumlah Saham
                try:
                    eps = financials.loc['Net Income'].iloc[0] / shares
                except: pass

            bvps = info.get('bookValue', 0)
            
            # Hitung PER & PBV Manual jika info kosong
            pe = info.get('trailingPE', curr_price/eps if eps > 0 else 0)
            pbv = info.get('priceToBook', curr_price/bvps if bvps > 0 else 0)

            # Benchmark
            pe_wajar = 15.0
            pbv_wajar = 1.5
            
            # Tampilkan Tabel Valuasi
            val_data = {
                "Metode": ["PER", "PBV"],
                "Saham Ini": [f"{pe:.2f}x", f"{pbv:.2f}x"],
                "Wajar (Industri)": ["15.00x", "1.50x"],
                "Status": ["MURAH" if pe<15 else "MAHAL", "MURAH" if pbv<1.5 else "MAHAL"]
            }
            st.table(pd.DataFrame(val_data).set_index("Metode"))

            # Kalkulasi Harga Wajar
            if eps > 0 and bvps > 0:
                fair_price = ((eps * pe_wajar) + (bvps * pbv_wajar)) / 2
                mos = ((fair_price - curr_price) / fair_price) * 100
                
                st.success(f"💰 **Harga Wajar (Est): Rp {fair_price:,.0f}**")
                st.metric("Margin of Safety (MoS)", f"{mos:.1f}%")
                
                # REKOMENDASI OTOMATIS
                st.subheader("4. REKOMENDASI")
                if mos > 20:
                    rec = "STRONG BUY"; color="green"; reason="Sangat Murah (MoS > 20%)"
                elif mos > 0:
                    rec = "BUY"; color="blue"; reason="Murah (Undervalued)"
                elif mos > -10:
                    rec = "HOLD"; color="orange"; reason="Harga Wajar"
                else:
                    rec = "SELL"; color="red"; reason="Mahal (Overvalued)"
                
                st.markdown(f"<h3 style='color:{color}'>{rec}</h3>", unsafe_allow_html=True)
                st.write(f"**Alasan:** {reason}")
                
                # Target Price
                c_tp1, c_tp2 = st.columns(2)
                c_tp1.info(f"**TP Pendek (6 Bln):** Rp {curr_price*1.1:,.0f}")
                c_tp2.success(f"**TP Panjang (Fair):** Rp {fair_price:,.0f}")

            else:
                st.warning("Perusahaan Rugi (EPS Negatif) atau Data Ekuitas Kosong. Valuasi Harga Wajar tidak valid.")
                st.error("REKOMENDASI: HINDARI / WAIT AND SEE")
