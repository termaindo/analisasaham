import streamlit as st
import yfinance as yf
import pandas as pd

# --- FUNGSI CACHE TANGGUH ---
@st.cache_data(ttl=3600, show_spinner=False)
def ambil_data_fundamental(ticker):
    """
    Mengambil data Info, Financials, dan Balance Sheet.
    Jika Info gagal (Rate Limit), mencoba ambil harga dari History sebagai cadangan.
    """
    stock = yf.Ticker(ticker)
    
    # 1. Coba Ambil Info Fundamental
    try:
        info = stock.info
    except Exception:
        info = {}

    # 2. Coba Ambil History (Cadangan Harga) & Laporan Keuangan
    try:
        # Ambil data 1 bulan untuk jaga-jaga
        history = stock.history(period="1mo")
        financials = stock.financials
        balance_sheet = stock.balance_sheet
    except Exception:
        history = pd.DataFrame()
        financials = pd.DataFrame()
        balance_sheet = pd.DataFrame()
        
    # 3. PERBAIKAN: Jika Info kosong tapi History ada, buat Info darurat
    if (not info or 'currentPrice' not in info) and not history.empty:
        last_price = history['Close'].iloc[-1]
        info = {
            'currentPrice': last_price,
            'longName': ticker,
            'industry': 'N/A (Limit)',
            'sector': 'N/A',
            'longBusinessSummary': 'Data fundamental sedang dibatasi oleh Yahoo Finance. Coba lagi nanti.',
            'marketCap': 0,
            'trailingPE': 0,
            'priceToBook': 0,
            'returnOnEquity': 0,
            'dividendRate': 0,
            'debtToEquity': 0,
            'currentRatio': 0
        }
        
    return info, financials, balance_sheet

def run_fundamental():
    st.title("📊 Analisa Fundamental Pro")
    st.markdown("---")

    # 1. INPUT
    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="ASII").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah Fundamental {ticker_input}"):
        try:
            with st.spinner(f"Sedang membedah laporan keuangan {ticker_input}..."):
                # --- AMBIL DATA ---
                info, financials, balance = ambil_data_fundamental(ticker)
                
                # Cek apakah data benar-benar kosong
                if not info or 'currentPrice' not in info:
                    st.warning("⚠️ Data tidak ditemukan. Kemungkinan Yahoo Finance sedang sibuk/limit. Coba 'Clear Cache' dan tunggu 1 menit.")
                    return

                # DATA DASAR
                curr_price = info.get('currentPrice', 0)
                market_cap = info.get('marketCap', 0)
                pe = info.get('trailingPE', 0)
                pbv = info.get('priceToBook', 0)
                roe = info.get('returnOnEquity', 0)
                dps = info.get('dividendRate', 0)
                div_yield = (dps / curr_price) * 100 if curr_price > 0 else 0

                # HEADER METRICS
                st.subheader(f"🏢 {info.get('longName', ticker_input)}")
                
                # Tampilkan Metric (Gunakan N/A jika 0 akibat Limit)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Harga", f"Rp {curr_price:,.0f}")
                c2.metric("Market Cap", f"Rp {market_cap/1e12:,.1f} T" if market_cap else "N/A")
                c3.metric("ROE", f"{roe*100:.1f}%" if roe else "N/A")
                c4.metric("Div. Yield", f"{div_yield:.2f}%" if dps else "N/A")

                st.markdown("---")

                # Jika data fundamental kena Limit, tampilkan peringatan
                if info.get('industry') == 'N/A (Limit)':
                    st.error("⚠️ **Peringatan:** Data fundamental detail tidak dapat diambil (Limit Yahoo Finance). Hanya harga terkini yang tersedia.")
                else:
                    # --- BAB 1: OVERVIEW ---
                    st.subheader("1. OVERVIEW & MODEL BISNIS")
                    st.write(f"**Sektor:** {info.get('sector', '-')} | **Industri:** {info.get('industry', '-')}")
                    st.info(f"**Bisnis Utama:** {info.get('longBusinessSummary', '-')[:400]}...")

                    # --- BAB 2: KINERJA KEUANGAN ---
                    st.subheader("2. TREND KINERJA KEUANGAN")
                    if not financials.empty:
                        try:
                            rev = financials.loc['Total Revenue']
                            ni = financials.loc['Net Income']
                            df_trend = pd.DataFrame({
                                "Revenue (T)": (rev.values / 1e12).round(2),
                                "Net Income (T)": (ni.values / 1e12).round(2),
                                "Margin (%)": ((ni.values / rev.values) * 100).round(1)
                            }, index=rev.index.year)
                            st.table(df_trend.head(4))
                        except:
                            st.warning("Format laporan keuangan tidak standar.")
                    else:
                        st.caption("Data laporan keuangan historis belum tersedia.")

                    # --- BAB 3: VALUASI WAJAR ---
                    st.subheader("3. VALUASI WAJAR (FAIR VALUE)")
                    
                    eps = info.get('trailingEps', 0)
                    bvps = info.get('bookValue', 0)
                    
                    if eps and bvps:
                        fair_pe = eps * 12.0
                        fair_pbv = bvps * 1.5
                        fair_price = (fair_pe + fair_pbv) / 2
                        mos = ((fair_price - curr_price) / fair_price) * 100
                        
                        col_v1, col_v2 = st.columns(2)
                        with col_v1:
                            st.write(f"**PER:** {pe:.2f}x")
                            st.write(f"**PBV:** {pbv:.2f}x")
                        with col_v2:
                            st.info(f"**Harga Wajar (Est):** Rp {fair_price:,.0f}")
                            st.metric("Margin of Safety (MoS)", f"{mos:.1f}%")
                            
                        # REKOMENDASI WARNA-WARNI
                        st.subheader("4. REKOMENDASI OTOMATIS")
                        if mos > 20 and roe > 0.1:
                            rec, color, rsn = "STRONG BUY", "green", "Undervalued & Profitable"
                        elif mos > 0:
                            rec, color, rsn = "BUY", "blue", "Harga di bawah Wajar"
                        elif mos > -10:
                            rec, color, rsn = "HOLD", "orange", "Harga Wajar (Fair)"
                        else:
                            rec, color, rsn = "SELL/WAIT", "red", "Harga Mahal (Overvalued)"

                        st.markdown(f"""<div style='background-color:#f0f2f6; padding:15px; border-left:10px solid {color};'>
                            <h3 style='color:{color}; margin:0;'>{rec}</h3>
                            <p><b>Alasan:</b> {rsn}</p></div>""", unsafe_allow_html=True)
                    else:
                        st.warning("Data EPS/BVPS tidak cukup untuk menghitung valuasi wajar.")

        except Exception as e:
            st.error(f"Terjadi kesalahan sistem: {e}")
