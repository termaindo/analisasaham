import streamlit as st
import yfinance as yf
import pandas as pd

# --- FUNGSI CACHE (ANTI-ERROR & ANTI-LIMIT) ---
@st.cache_data(ttl=3600, show_spinner=False)
def ambil_data_fundamental_lengkap(ticker):
    """
    Mengambil seluruh data yang dibutuhkan untuk analisa 5 Bab.
    Disimpan di memori selama 1 jam.
    """
    stock = yf.Ticker(ticker)
    
    # 1. Info Utama
    try:
        info = stock.info
    except:
        info = {}
        
    # 2. Laporan Keuangan (Untuk Trend 3-4 Tahun)
    try:
        financials = stock.financials
        balance_sheet = stock.balance_sheet
    except:
        financials = pd.DataFrame()
        balance_sheet = pd.DataFrame()
        
    # 3. History Harga (Untuk Fallback jika info kosong)
    try:
        history = stock.history(period="1mo")
    except:
        history = pd.DataFrame()
        
    return info, financials, balance_sheet, history

def run_fundamental():
    st.title("📊 Analisa Fundamental: Deep Value")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="ASII").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Jalankan Analisa {ticker_input}"):
        try:
            with st.spinner(f"Menggali data fundamental {ticker_input}..."):
                # AMBIL DATA DARI CACHE
                info, financials, balance, history = ambil_data_fundamental_lengkap(ticker)
                
                # VALIDASI DATA
                if (not info or 'currentPrice' not in info) and history.empty:
                    st.error("Data tidak ditemukan. Coba kode saham lain atau tunggu sebentar.")
                    return

                # Siapkan Variabel Utama (Handle jika data kosong)
                curr_price = info.get('currentPrice', history['Close'].iloc[-1] if not history.empty else 0)
                market_cap = info.get('marketCap', 0)
                sector = info.get('sector', 'N/A')
                
                # Header
                st.subheader(f"🏢 {info.get('longName', ticker_input)}")
                st.caption(f"Sektor: {sector} | Industri: {info.get('industry', 'N/A')}")
                
                # --- BAB 1: OVERVIEW PERUSAHAAN ---
                st.markdown("### 1. OVERVIEW PERUSAHAAN")
                
                # Posisi Industri
                if market_cap > 100e12: posisi = "Market Leader (Big Cap)"
                elif market_cap > 10e12: posisi = "Challenger (Mid Cap)"
                else: posisi = "Niche Player (Small Cap)"
                
                st.write(f"**Bisnis Utama:** {info.get('longBusinessSummary', 'Deskripsi tidak tersedia.')[:400]}...")
                st.write(f"**Posisi Industri:** {posisi} (Kapitalisasi Rp {market_cap/1e12:,.1f} T)")
                st.write(f"**Competitive Advantage:** {info.get('recommendationKey', 'N/A').upper()} dari analis global. Memiliki brand equity dan jaringan yang luas.")

                # --- BAB 2: ANALISA KEUANGAN (3-5 Tahun) ---
                st.markdown("### 2. ANALISA KEUANGAN (Trend)")
                
                if not financials.empty:
                    try:
                        # Data Revenue & Profit
                        rev = financials.loc['Total Revenue']
                        ni = financials.loc['Net Income']
                        
                        # Menghitung Pertumbuhan (CAGR Simpel / YoY Terakhir)
                        rev_growth = ((rev.iloc[0] - rev.iloc[1]) / rev.iloc[1]) * 100 if len(rev) > 1 else 0
                        eps_growth = info.get('earningsGrowth', 0) * 100
                        
                        # Tampilkan Tabel
                        df_fin = pd.DataFrame({
                            "Revenue (T)": (rev.values / 1e12).round(2),
                            "Net Profit (T)": (ni.values / 1e12).round(2),
                            "Net Margin (%)": ((ni.values / rev.values) * 100).round(1)
                        }, index=rev.index.year).head(4)
                        st.table(df_fin)
                        
                        # Poin-poin Kunci
                        c_k1, c_k2 = st.columns(2)
                        with c_k1:
                            st.write(f"- **Revenue Growth (YoY):** {rev_growth:+.2f}%")
                            st.write(f"- **EPS Growth:** {eps_growth:+.2f}%")
                            st.write(f"- **ROE:** {info.get('returnOnEquity', 0)*100:.2f}%")
                        with c_k2:
                            st.write(f"- **Debt to Equity:** {info.get('debtToEquity', 0):.2f}")
                            st.write(f"- **Current Ratio:** {info.get('currentRatio', 0):.2f}")
                            st.write(f"- **Profit Margin Trend:** {'Stabil/Naik' if df_fin['Net Margin (%)'].iloc[0] >= df_fin['Net Margin (%)'].iloc[-1] else 'Menurun'}")
                    except:
                        st.warning("Struktur laporan keuangan tidak standar, tabel detail dilewati.")
                else:
                    st.warning("Data historis keuangan tidak tersedia di server.")

                # --- BAB 3: VALUASI ---
                st.markdown("### 3. VALUASI & HARGA WAJAR")
                
                # Variabel Valuasi
                pe_now = info.get('trailingPE', 0)
                pbv_now = info.get('priceToBook', 0)
                dps = info.get('dividendRate', 0)
                div_yield = (dps / curr_price * 100) if curr_price > 0 else 0
                
                # Benchmark (Rata-rata Industri/Historis - Estimasi)
                # Karena API Gratis tidak menyediakan data historis 5 tahun spesifik, kita pakai benchmark wajar
                pe_wajar = 15.0  # Rata-rata IHSG/Big Caps
                pbv_wajar = 1.5 if info.get('returnOnEquity', 0) > 0.1 else 1.0
                
                st.write("**Perbandingan Rasio:**")
                val_data = {
                    "Rasio": ["PER", "PBV", "Dividend Yield"],
                    "Saham Ini": [f"{pe_now:.2f}x", f"{pbv_now:.2f}x", f"{div_yield:.2f}%"],
                    "Benchmark Wajar": [f"{pe_wajar:.2f}x", f"{pbv_wajar:.2f}x", "> 4.0%"]
                }
                st.table(pd.DataFrame(val_data).set_index("Rasio"))

                # Perhitungan Harga Wajar (Graham Number Modified)
                eps = info.get('trailingEps', 0)
                bvps = info.get('bookValue', 0)
                
                if eps > 0 and bvps > 0:
                    fair_value_pe = eps * pe_wajar
                    fair_value_pbv = bvps * pbv_wajar
                    fair_price = (fair_value_pe + fair_value_pbv) / 2
                    
                    mos = ((fair_price - curr_price) / fair_price) * 100
                    status_val = "UNDERVALUED (Murah)" if mos > 0 else "OVERVALUED (Mahal)"
                    
                    st.info(f"💰 **Harga Wajar (Estimasi): Rp {fair_price:,.0f}**")
                    st.write(f"**Status:** {status_val}")
                    st.metric("Margin of Safety (MoS)", f"{mos:.1f}%")
                else:
                    st.warning("Perusahaan merugi (EPS Negatif), metode valuasi standar tidak berlaku.")
                    fair_price = curr_price # Fallback
                    mos = 0

                # --- BAB 4: PROSPEK BISNIS ---
                st.markdown("### 4. PROSPEK & RISIKO")
                st.write("**Outlook Industri:**")
                st.write("Sektor ini diperkirakan akan bergerak seiring dengan pertumbuhan ekonomi makro Indonesia (GDP Growth).")
                
                st.write("**Growth Catalyst:**")
                st.write("1. Ekspansi pasar dan efisiensi digitalisasi.")
                st.write("2. Potensi kenaikan permintaan domestik.")
                
                st.write("**Risk Factors:**")
                st.write("1. Ketidakstabilan nilai tukar Rupiah.")
                st.write("2. Kenaikan suku bunga yang dapat membebani biaya utang.")

                # --- BAB 5: REKOMENDASI ---
                st.markdown("### 5. REKOMENDASI FINAL")
                
                # Logika Rekomendasi Sederhana
                if mos > 15 and info.get('returnOnEquity', 0) > 0.08:
                    rec = "BUY"
                    color = "green"
                    reason = "Valuasi murah (MoS > 15%) dan Perusahaan Profit (ROE Sehat)."
                elif mos > -5:
                    rec = "HOLD"
                    color = "orange"
                    reason = "Harga wajar. Hold untuk dividen atau tunggu breakout."
                else:
                    rec = "SELL / WAIT"
                    color = "red"
                    reason = "Harga sudah terlalu mahal dibanding fundamentalnya."
                
                # Target Price
                tp_short = curr_price * 1.10 # +10%
                tp_long = fair_price if fair_price > curr_price else curr_price * 1.2
                sl = curr_price * 0.92 # -8%
                
                st.markdown(f"""
                <div style='background-color: #f0f2f6; border-left: 10px solid {color}; padding: 20px; border-radius: 5px;'>
                    <h2 style='color: {color}; margin:0;'>{rec}</h2>
                    <p><b>Alasan:</b> {reason}</p>
                    <hr>
                    <div style='display: flex; justify-content: space-between;'>
                        <div>🎯 <b>TP Pendek (3-6 Bln):</b><br>Rp {tp_short:,.0f}</div>
                        <div>🏆 <b>TP Panjang (1-2 Thn):</b><br>Rp {tp_long:,.0f}</div>
                        <div>🛑 <b>Stop Loss:</b><br>Rp {sl:,.0f}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Terjadi kesalahan saat analisa. Detail: {e}")
