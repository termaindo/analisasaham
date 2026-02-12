import streamlit as st
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_fundamental():
    st.title("🏛️ Analisa Fundamental Pro")
    ticker_input = st.text_input("Kode Saham:", value="ASII").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button("Bedah Fundamental"):
        data = get_full_stock_data(ticker)
        info, financials = data["info"], data["financials"]
        
        # 1. OVERVIEW
        st.subheader("1. Overview Perusahaan")
        st.write(info.get('longBusinessSummary', 'N/A')[:400] + "...")

        # 2. KINERJA (TREN 4 TAHUN)
        st.subheader("2. Tren Kinerja (Laba Bersih)")
        if not financials.empty:
            st.bar_chart(financials.loc['Net Income'].head(4))

        # 3. VALUASI GRAHAM
        st.subheader("3. Valuasi & Harga Wajar")
        curr = info.get('currentPrice', 0)
        eps = info.get('trailingEps', 0)
        bvps = info.get('bookValue', 0)
        fair_price = ((eps * 15) + (bvps * 1.5)) / 2 if (eps > 0 and bvps > 0) else curr
        
        # --- LOCK RISK 8% UNTUK TRADING PLAN ---
        sl_final = curr * 0.92
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Harga Wajar", f"Rp {fair_price:,.0f}")
        c2.metric("Margin of Safety", f"{((fair_price-curr)/fair_price)*100:.1f}%")
        c3.error(f"Stop Loss (Max 8%): Rp {sl_final:,.0f}")

        # 4 & 5. PROSPEK & REKOMENDASI
        st.subheader("4. Prospek & 5. Rekomendasi")
        rec = "STRONG BUY" if fair_price > curr * 1.2 else "HOLD"
        st.success(f"Rekomendasi Final: **{rec}**")
