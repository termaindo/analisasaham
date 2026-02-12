import streamlit as st
import pandas as pd
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_perbandingan():
    st.title("⚖️ Perbandingan Saham Pro")
    c1, c2 = st.columns(2)
    t1 = c1.text_input("Saham A:", value="BBCA").upper()
    t2 = c2.text_input("Saham B:", value="BBRI").upper()

    if st.button("Bandingkan"):
        d1 = get_full_stock_data(t1 if t1.endswith(".JK") else f"{t1}.JK")
        d2 = get_full_stock_data(t2 if t2.endswith(".JK") else f"{t2}.JK")

        i1, i2 = d1['info'], d2['info']
        
        comp_df = pd.DataFrame({
            "Metrik": ["Harga", "PER", "PBV", "ROE", "Div. Yield", "Stop Loss (Max 8%)"],
            t1: [i1.get('currentPrice'), i1.get('trailingPE'), i1.get('priceToBook'), i1.get('returnOnEquity'), hitung_div_yield_normal(i1), i1.get('currentPrice', 0) * 0.92],
            t2: [i2.get('currentPrice'), i2.get('trailingPE'), i2.get('priceToBook'), i2.get('returnOnEquity'), hitung_div_yield_normal(i2), i2.get('currentPrice', 0) * 0.92]
        })
        st.table(comp_df.set_index("Metrik"))
