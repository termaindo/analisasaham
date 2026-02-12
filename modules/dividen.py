import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_dividen():
    st.title("💰 Analisa Dividen (Income Investing)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="ITMG").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah Dividen {ticker_input}"):
        with st.spinner("Menganalisa cash flow & histori..."):
            data = get_full_stock_data(ticker)
            info = data["info"]
            raw_div = data.get("dividends", pd.Series())
            cashflow = data["cashflow"]
            
            if not info or raw_div.empty:
                st.warning("Data dividen tidak ditemukan atau perusahaan tidak bagi dividen.")
                return

            curr_price = info.get('currentPrice', 0)
            div_yield = hitung_div_yield_normal(info)

            # --- 1. HISTORI 5 TAHUN ---
            st.header("1. RIWAYAT DIVIDEN (5 TAHUN)")
            raw_div.index = pd.to_datetime(raw_div.index).tz_localize(None)
            df_div = raw_div.groupby(raw_div.index.year).sum().tail(5)
            
            fig = go.Figure(go.Bar(x=df_div.index, y=df_div.values, marker_color='gold', name='DPS'))
            fig.update_layout(title="Dividen Per Share (Nominal) Tahunan", height=300, template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

            # --- 2. KESEHATAN KEUANGAN ---
            st.header("2. KESEHATAN & SUSTAINABILITY")
            payout = info.get('payoutRatio', 0) * 100
            
            c1, c2 = st.columns(2)
            c1.metric("Dividend Yield", f"{div_yield:.2f}%")
            c2.metric("Payout Ratio", f"{payout:.1f}%")

            if not cashflow.empty:
                try:
                    fcf = info.get('freeCashflow', 0)
                    if fcf > 0:
                        st.success("✅ **Sustainable:** Dividen dibayar dari Arus Kas Bebas (FCF) yang positif.")
                    else:
                        st.warning("⚠️ **Waspada:** Free Cash Flow negatif, dividen mungkin diambil dari utang/cadangan.")
                except: pass

            # --- 3. PROYEKSI & 4. REKOMENDASI ---
            st.header("3. PROYEKSI & REKOMENDASI")
            est_dps = info.get('trailingEps', 0) * (payout/100)
            
            st.info(f"**Estimasi Dividen Berikutnya:** Rp {est_dps:,.0f} / lembar")
            
            # Rekomendasi vs Deposito
            if div_yield > 6:
                rec = "SANGAT LAYAK (Yield > Bunga Deposito)"
                color = "green"
            elif div_yield > 4:
                rec = "LAYAK (Setara Deposito)"
                color = "blue"
            else:
                rec = "KURANG MENARIK (Yield Kecil)"
                color = "orange"
                
            st.markdown(f"<div style='padding:15px; border-radius:10px; border:2px solid {color}; color:{color}; font-weight:bold; text-align:center;'>{rec}</div>", unsafe_allow_html=True)
