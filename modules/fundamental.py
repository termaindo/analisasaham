import streamlit as st
import pandas as pd
import numpy as np
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_fundamental():
    st.title("🏛️ Analisa Fundamental Pro (Deep Value Analysis)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="ASII").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah Fundamental {ticker_input}"):
        with st.spinner("Mengevaluasi laporan keuangan & model bisnis..."):
            # --- STANDAR ANTI-ERROR ---
            data = get_full_stock_data(ticker)
            info = data['info']
            financials = data['financials']
            history = data['history']
            
            if not info or financials.empty:
                st.error("Data fundamental tidak lengkap atau server sibuk. Mohon coba lagi nanti.")
                return

            curr_price = info.get('current_price', info.get('currentPrice', 0))
            
            # --- 1. OVERVIEW PERUSAHAAN ---
            st.header("1. OVERVIEW PERUSAHAAN")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.write(f"**Bisnis & Model:** {info.get('longBusinessSummary', 'N/A')[:600]}...")
            with c2:
                mkt_cap = info.get('marketCap', 0)
                posisi = "Market Leader" if mkt_cap > 100e12 else "Challenger" if mkt_cap > 10e12 else "Niche Player"
                st.info(f"**Sektor:** {info.get('sector', 'N/A')}\n\n**Posisi:** {posisi}\n\n**Moat:** Competitive Advantage melalui skala ekonomi & jaringan distribusi.")

            # --- 2. ANALISA KEUANGAN (3-5 TAHUN) ---
            st.header("2. ANALISA KEUANGAN (Tren Jangka Panjang)")
            try:
                # Mengolah data 4 tahun terakhir
                df_fin = financials.T.head(4).sort_index()
                df_fin['Net Profit Margin (%)'] = (df_fin['Net Income'] / df_fin['Total Revenue']) * 100
                
                # Plot Revenue & Profit Trend
                st.line_chart(df_fin[['Total Revenue', 'Net Income']])
                
                f1, f2, f3 = st.columns(3)
                f1.metric("ROE", f"{info.get('returnOnEquity', 0)*100:.2f}%")
                f2.metric("Debt to Equity", f"{info.get('debtToEquity', 0):.2f}x")
                f3.metric("Current Ratio", f"{info.get('currentRatio', 0):.2f}x")
                
                st.write("**Pertumbuhan EPS:** Tahunan rata-rata berkisar " + f"{info.get('earningsGrowth', 0)*100:.1f}%")
            except:
                st.warning("Beberapa data tren keuangan tidak dapat ditampilkan.")

            # --- 3. VALUASI ---
            st.header("3. VALUASI & HARGA WAJAR")
            pe = info.get('trailingPE', 0)
            pbv = info.get('priceToBook', 0)
            div_yield = hitung_div_yield_normal(info)
            
            # Kalkulasi Graham Number sebagai benchmark Harga Wajar
            eps = info.get('trailingEps', 0)
            bvps = info.get('bookValue', 0)
            fair_price = np.sqrt(22.5 * eps * bvps) if (eps > 0 and bvps > 0) else curr_price
            
            status_val = "UNDERVALUED" if curr_price < fair_price else "OVERVALUED"
            
            v1, v2, v3 = st.columns(3)
            v1.metric("PER (TTM)", f"{pe:.2f}x", "vs Ind: ~15x")
            v2.metric("PBV", f"{pbv:.2f}x", "vs Ind: ~1.5x")
            v3.metric("Dividend Yield", f"{div_yield:.2f}%")
            
            st.success(f"🎯 **Harga Wajar Saat Ini: Rp {fair_price:,.0f}** ({status_val})")

            # --- 4. PROSPEK BISNIS ---
            st.header("4. PROSPEK & RISIKO")
            st.write("• **Outlook:** Sektor ini diproyeksikan tumbuh seiring pemulihan daya beli domestik.")
            st.write("• **Catalyst:** Ekspansi digital dan efisiensi operasional berkelanjutan.")
            st.write("• **Risk Factors:** Kenaikan suku bunga, fluktuasi harga komoditas, dan risiko regulasi.")

            # --- 5. REKOMENDASI (TRADING PLAN & TARGET) ---
            st.header("5. REKOMENDASI & TARGET HARGA")
            
            # Kalkulasi SL Berbasis ATR (LOCK 8%)
            atr = (history['High'] - history['Low']).tail(14).mean()
            sl_atr = curr_price - (1.5 * atr)
            sl_final = max(sl_atr, curr_price * 0.92) # LOCK MAX 8%
            
            target_short = fair_price if fair_price > curr_price else curr_price * 1.1
            target_long = target_short * 1.2
            
            rec_signal = "BUY" if curr_price < fair_price * 0.9 else "HOLD" if curr_price < fair_price * 1.1 else "SELL"
            
            st.subheader(f"Rating Akhir: **{rec_signal}**")
            
            r1, r2, r3 = st.columns(3)
            with r1:
                st.write("**Target Pendek (3-6 bln):**")
                st.markdown(f"### Rp {target_short:,.0f}")
            with r2:
                st.write("**Target Panjang (1-2 thn):**")
                st.markdown(f"### Rp {target_long:,.0f}")
            with r3:
                st.write("**Stop Loss (Max 8%):**")
                st.error(f"Rp {sl_final:,.0f}")

            st.caption(f"Dasar SL: {'ATR 1.5x' if sl_final == sl_atr else 'Hard Cap 8%'}")
