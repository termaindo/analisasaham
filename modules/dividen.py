import streamlit as st
import pandas as pd
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_dividen():
    st.title("💰 Analisa Dividen Pro (Passive Income Investing)")
    ticker_input = st.text_input("Kode Saham:", value="ITMG").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button("Cek Dividen"):
        data = get_full_stock_data(ticker)
        info, divs = data["info"], data["dividends"]
        
        st.subheader("1. Riwayat Dividen (5 Tahun)")
        if not divs.empty:
            df_div = divs.groupby(divs.index.year).sum().tail(5)
            st.bar_chart(df_div)

        st.subheader("2. Sustainability (Arus Kas)")
        payout = info.get('payoutRatio', 0) * 100
        yield_val = hitung_div_yield_normal(info)
        
        c1, c2 = st.columns(2)
        c1.metric("Dividend Yield", f"{yield_val:.2f}%")
        c2.metric("Payout Ratio", f"{payout:.1f}%")

        st.subheader("3. Trading Plan vs Dividen")
        curr = info.get('currentPrice', 0)
        sl_final = curr * 0.92
        st.warning(f"Proteksi Modal: Jangan biarkan harga turun > 8% (SL: Rp {sl_final:,.0f}) meski mengejar dividen.")
