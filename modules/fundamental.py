import streamlit as st
import pandas as pd
from modules.data_loader import get_full_stock_data, hitung_div_yield

def run_fundamental():
    st.title("📊 Analisa Fundamental: Deep Value")
    st.markdown("---")

    ticker_input = st.text_input("Kode Saham:", value="ASII").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah Fundamental {ticker_input}"):
        with st.spinner("Menganalisa data sektor & keuangan..."):
            data = get_full_stock_data(ticker)
            info = data["info"]
            df_hist = data["history"]
            financials = data["financials"]

            if not info and df_hist.empty:
                st.error("Koneksi ke Yahoo Finance sibuk. Mohon tunggu 1 menit lalu coba lagi.")
                return

            curr_price = info.get('currentPrice', df_hist['Close'].iloc[-1] if not df_hist.empty else 0)
            div_yield = hitung_div_yield(info)

            # --- 1. OVERVIEW PERUSAHAAN ---
            st.subheader("1. OVERVIEW PERUSAHAAN")
            st.write(f"**Bisnis Utama:** {info.get('longBusinessSummary', 'N/A')[:500]}...")
            mkt_cap = info.get('marketCap', 0)
            posisi = "Market Leader" if mkt_cap > 100e12 else "Challenger" if mkt_cap > 10e12 else "Niche Player"
            st.info(f"**Posisi Industri:** {posisi} | **Kapitalisasi:** Rp {mkt_cap/1e12:,.1f} T")

            # --- 2. ANALISA KEUANGAN (3-5 TAHUN) ---
            st.subheader("2. ANALISA KEUANGAN (Trend)")
            if not financials.empty:
                try:
                    rev = financials.loc['Total Revenue'].head(4)
                    ni = financials.loc['Net Income'].head(4)
                    df_fin = pd.DataFrame({"Revenue (T)": rev/1e12, "Laba Bersih (T)": ni/1e12}, index=rev.index.year)
                    st.table(df_fin.style.format("{:.2f}"))
                except: st.write("Detail trend keuangan terbatas.")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("ROE", f"{info.get('returnOnEquity', 0)*100:.2f}%")
            c2.metric("DER", f"{info.get('debtToEquity', 0):.2f}x")
            c3.metric("Current Ratio", f"{info.get('currentRatio', 0):.2f}x")

            # --- 3. VALUASI & HARGA WAJAR ---
            st.subheader("3. VALUASI")
            pe = info.get('trailingPE', 0)
            pbv = info.get('priceToBook', 0)
            eps = info.get('trailingEps', 0)
            bvps = info.get('bookValue', 0)
            
            # Harga Wajar Graham-Style
            fair_price = ((eps * 15) + (bvps * 1.5)) / 2 if (eps > 0 and bvps > 0) else curr_price
            mos = ((fair_price - curr_price) / fair_price) * 100
            
            v1, v2, v3 = st.columns(3)
            v1.metric("PER", f"{pe:.2f}x")
            v2.metric("PBV", f"{pbv:.2f}x")
            v3.metric("Div. Yield", f"{div_yield:.2f}%")
            
            st.success(f"🎯 **Harga Wajar Estimasi: Rp {fair_price:,.0f}** (MoS: {mos:.1f}%)")

            # --- 4. PROSPEK & 5. REKOMENDASI ---
            st.subheader("4. PROSPEK & RISIKO")
            st.write("✅ **Catalyst:** Efisiensi operasional & Dominasi pasar domestik.")
            st.write("⚠️ **Risk:** Fluktuasi kurs & daya beli masyarakat.")

            st.subheader("5. REKOMENDASI")
            rec = "BUY" if mos > 15 else "HOLD" if mos > -5 else "SELL"
            st.markdown(f"""
            <div style="background-color:#1e2b3e; padding:20px; border-radius:10px; border-left:10px solid #ff0000;">
                <h3>Rating: {rec}</h3>
                <p>Target Price (1 Thn): <b>Rp {fair_price:,.0f}</b> | Stop Loss: <b>Rp {curr_price*0.9:,.0f}</b></p>
            </div>
            """, unsafe_allow_html=True)
