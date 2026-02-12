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
        with st.spinner("Menganalisa riwayat & keberlanjutan..."):
            data = get_full_stock_data(ticker)
            info = data["info"]
            raw_div = data["dividends"]
            cashflow = data["cashflow"]
            
            if not info or raw_div.empty:
                st.error("Data dividen tidak ditemukan. Server Yahoo mungkin sedang sibuk, mohon tunggu sejenak.")
                return

            curr_price = info.get('currentPrice', 0)
            div_yield = hitung_div_yield_normal(info)

            # --- 1. RIWAYAT 5 TAHUN ---
            st.header("1. RIWAYAT DIVIDEN (5 TAHUN)")
            # Pastikan index adalah datetime
            raw_div.index = pd.to_datetime(raw_div.index).tz_localize(None)
            df_div = raw_div.groupby(raw_div.index.year).sum().tail(5)
            
            fig = go.Figure(go.Bar(x=df_div.index, y=df_div.values, marker_color='gold', name='DPS'))
            fig.update_layout(title="Dividen Per Lembar (DPS) Tahunan", template="plotly_dark", height=300)
            st.plotly_chart(fig, use_container_width=True)

            # --- 2. KESEHATAN KEUANGAN ---
            st.header("2. KESEHATAN & SUSTAINABILITY")
            c1, c2 = st.columns(2)
            c1.metric("Dividend Yield", f"{div_yield:.2f}%")
            c2.metric("Payout Ratio", f"{info.get('payoutRatio', 0)*100:.1f}%")

            # Sustainability check
            if not cashflow.empty:
                fcf = info.get('freeCashflow', 0)
                if fcf > 0: st.success("✅ Dividen berkelanjutan (Dibayar dari Free Cash Flow).")
                else: st.warning("⚠️ Perhatikan: Free Cash Flow negatif, dividen mungkin kurang stabil.")

            # --- 3. PROYEKSI & 4. REKOMENDASI ---
            st.header("3. PROYEKSI & STRATEGI")
            avg_div = df_div.mean()
            st.info(f"**Rata-rata Dividen Tahunan:** Rp {avg_div:,.0f} | **Potensi Yield ke Depan:** {div_yield:.2f}%")
            
            # Rekomendasi vs Deposito (Asumsi Deposito 4.5%)
            if div_yield > 4.5:
                st.success(f"🏆 **Rekomendasi:** Sangat Layak (Yield di atas bunga deposito).")
            else:
                st.warning(f"⚖️ **Rekomendasi:** Kurang Menarik (Yield di bawah bunga deposito).")
