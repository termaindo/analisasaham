import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_dividen():
    st.title("💰 Analisa Dividen Pro (Passive Income Investing)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Dividend Check):", value="ITMG").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Analisa Dividen {ticker_input}"):
        with st.spinner("Mengevaluasi histori & kesehatan kas..."):
            # --- STANDAR ANTI-ERROR ---
            data = get_full_stock_data(ticker)
            info = data['info']
            divs = data['dividends']
            cashflow = data['cashflow']
            history = data['history']
            
            if not info or divs.empty:
                st.error("Data dividen tidak ditemukan atau emiten tidak membagikan dividen.")
                return

            curr_price = info.get('currentPrice', 0)
            
            # --- 1. DIVIDEND HISTORY (5 TAHUN) ---
            st.header("1. DIVIDEND HISTORY (5 TAHUN)")
            df_div = divs.to_frame()
            df_div.index = pd.to_datetime(df_div.index).tz_localize(None)
            df_div_annual = df_div.resample('YE').sum().tail(5)
            df_div_annual.index = df_div_annual.index.year
            
            st.bar_chart(df_div_annual)
            
            c1, c2, c3 = st.columns(3)
            yield_val = hitung_div_yield_normal(info)
            payout = info.get('payoutRatio', 0) * 100
            
            c1.metric("Dividend Yield", f"{yield_val:.2f}%")
            c2.metric("Payout Ratio", f"{payout:.1f}%")
            c3.metric("Konsistensi", f"{len(df_div_annual)}/5 Thn")

            # --- 2. KESEHATAN KEUANGAN ---
            st.header("2. KESEHATAN KEUANGAN")
            fcf = info.get('freeCashflow', 0)
            der = info.get('debtToEquity', 0)
            
            col_health1, col_health2 = st.columns(2)
            with col_health1:
                if fcf > 0:
                    st.success("✅ **Sustainable:** Dividen dibayar dari Arus Kas Bebas (FCF) positif.")
                else:
                    st.warning("⚠️ **Waspada:** FCF negatif, dividen mungkin diambil dari utang/cadangan kas.")
            with col_health2:
                st.write(f"**Debt level (DER):** {der:.2f}x")
                st.write("**Current Ratio:** " + f"{info.get('currentRatio', 0):.2f}x")

            # --- 3. PROYEKSI & ATR STOP LOSS (LOCK 8%) ---
            st.header("3. PROYEKSI & PROTEKSI")
            est_dps = info.get('trailingEps', 0) * (payout / 100)
            
            # Kalkulasi SL ATR Lock 8%
            atr = (history['High'] - history['Low']).tail(14).mean()
            sl_raw = curr_price - (1.5 * atr)
            sl_final = max(sl_raw, curr_price * 0.92) # LOCK 8%
            
            st.info(f"**Estimasi DPS Mendatang:** Rp {est_dps:,.0f} / lembar\n\n**Potential Yield:** {(est_dps/curr_price)*100:.2f}%")
            st.error(f"**Stop Loss Level (Max 8%):** Rp {sl_final:,.0f}")

            # --- 4. REKOMENDASI ---
            st.header("4. REKOMENDASI")
            deposito_rate = 5.0
            
            if yield_val > deposito_rate * 1.5:
                status = "SANGAT LAYAK (Yield jauh di atas Deposito)"
            elif yield_val > deposito_rate:
                status = "LAYAK (Yield di atas Deposito)"
            else:
                status = "KURANG MENARIK (Yield di bawah Deposito)"
            
            st.subheader(f"Status: {status}")
            st.write(f"**Entry Price (untuk Mencapai Yield setara Deposito {deposito_rate}%):** Rp {est_dps / (deposito_rate/100):,.0f} ")
            
            # INFO TAMBAHAN SESUAI PERMINTAAN
            st.write(f"**Harga Saham Saat Ini:** Rp {curr_price:,.0f}")
