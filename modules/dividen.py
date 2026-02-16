import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Import dari data_loader & universe
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal
from modules.universe import is_syariah

def run_dividen():
    st.title("💰 Analisa Dividen Pro (Passive Income Investing)")
    st.markdown("---")

    # --- INPUT SECTION ---
    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Dividend Check):", value="ITMG").upper()
    
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"
    kode_bersih = ticker_input.replace(".JK", "").upper()

    if st.button(f"Analisa Dividen {ticker_input}"):
        with st.spinner("Mengevaluasi fundamental & kelayakan dividen..."):
            data = get_full_stock_data(ticker)
            info = data['info']
            divs = data['dividends']
            history = data['history']
            
            if not info or divs.empty:
                st.error("Data dividen tidak ditemukan atau emiten tidak membagikan dividen.")
                return

            # Ambil Data Dasar
            curr_price = info.get('currentPrice', 0)
            sector = info.get('sector', 'Sektor Tidak Diketahui')
            company_name = info.get('longName', ticker_input)
            
            # --- HEADER: IDENTITAS SAHAM ---
            st.subheader(f"{ticker_input} - {company_name}")
            status_syr = "✅ Ya (Daftar Efek Syariah)" if is_syariah(kode_bersih) else "❌ Tidak / Non-Syariah"
            st.write(f"**Sektor:** {sector} | **Kategori Syariah:** {status_syr}")
            st.markdown("---")

            # --- 1. HISTORY DAN PERTUMBUHAN DIVIDEN ---
            st.header("1. History & Pertumbuhan Dividen")
            df_div = divs.to_frame(name='Dividends')
            df_div.index = pd.to_datetime(df_div.index).tz_localize(None)
            df_div_annual = df_div.resample('YE').sum().tail(5)
            df_div_annual.index = df_div_annual.index.year
            
            # Grafik Bar
            st.bar_chart(df_div_annual['Dividends'])
            
            # Kalkulasi CAGR & Yield
            cagr = 0
            if len(df_div_annual) >= 2:
                awal, akhir = df_div_annual['Dividends'].iloc[0], df_div_annual['Dividends'].iloc[-1]
                if awal > 0:
                    cagr = ((akhir / awal) ** (1 / (len(df_div_annual)-1))) - 1
            
            yield_val = hitung_div_yield_normal(info)
            payout = info.get('payoutRatio', 0) * 100
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Dividend Yield", f"{yield_val:.2f}%")
            m2.metric("Payout Ratio", f"{payout:.1f}%")
            m3.metric("Konsistensi", f"{len(df_div_annual)}/5 Thn")
            m4.metric("Growth (CAGR)", f"{cagr*100:.1f}%")

            # --- 2. KINERJA BISNIS ---
            st.header("2. Kinerja Bisnis")
            eps_growth = info.get('earningsGrowth', 0) * 100
            roe = info.get('returnOnEquity', 0) * 100
            
            col_biz1, col_biz2 = st.columns(2)
            with col_biz1:
                st.write("**EPS Growth (YoY):**")
                if eps_growth > 0:
                    st.success(f"📈 {eps_growth:.1f}% (Laba Bertumbuh)")
                else:
                    st.error(f"📉 {eps_growth:.1f}% (Laba Menurun)")
            with col_biz2:
                st.write("**Return on Equity (ROE):**")
                if roe > 15:
                    st.success(f"💎 {roe:.1f}% (Sangat Efisien)")
                elif roe > 8:
                    st.info(f"👍 {roe:.1f}% (Efisien)")
                else:
                    st.warning(f"⚠️ {roe:.1f}% (Kurang Efisien)")

            # --- 3. KESEHATAN FINANSIAL ---
            st.header("3. Kesehatan Finansial")
            fcf = info.get('freeCashflow', 0)
            der = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
            
            col_fin1, col_fin2 = st.columns(2)
            with col_fin1:
                st.write("**Kualitas Kas (FCF):**")
                if fcf > 0:
                    st.success(f"✅ Positif (Rp {fcf:,.0f})")
                else:
                    st.error("❌ Negatif (Waspada Kas)")
            with col_fin2:
                st.write("**Debt to Equity Ratio (DER):**")
                if der < 1.0:
                    st.success(f"✅ {der:.2f}x (Utang Rendah)")
                else:
                    st.warning(f"⚠️ {der:.2f}x (Utang Tinggi)")

            # --- 4. PROYEKSI DAN PROTEKSI ---
            st.header("4. Proyeksi & Proteksi")
            est_dps = info.get('trailingEps', 0) * (payout / 100)
            atr = (history['High'] - history['Low']).tail(14).mean()
            sl_final = max(curr_price - (1.5 * atr), curr_price * 0.92)
            
            p1, p2 = st.columns(2)
            p1.info(f"**Estimasi DPS:** Rp {est_dps:,.0f}\n\n**Potential Yield:** {(est_dps/curr_price)*100:.2f}%")
            p2.error(f"**Stop Loss (Lock 8%):**\n\nRp {sl_final:,.0f}")

            # --- INTEGRASI SCORING (Summary) ---
            st.markdown("---")
            total_score = 0
            if yield_val > 6: total_score += 25
            if 30 <= payout <= 70: total_score += 25
            if fcf > 0: total_score += 25
            if cagr > 0 and roe > 10: total_score += 25
            
            st.write(f"### Skor Kelayakan: {total_score}/100")
            st.progress(total_score / 100)

            # --- 5. REKOMENDASI ---
            st.header("5. Rekomendasi")
            deposito_rate = 5.0
            entry_price = est_dps / (deposito_rate/100) if est_dps > 0 else 0
            
            if curr_price < entry_price and total_score >= 75:
                status = "SANGAT LAYAK (Underpriced & Fundamental Kuat)"
                saran = "✅ Harga saat ini di bawah nilai wajar yield. Pertimbangkan untuk akumulasi."
            elif curr_price < entry_price:
                status = "LAYAK (Harga Murah)"
                saran = "✅ Harga menarik, namun perhatikan catatan fundamental di atas."
            else:
                status = "TUNGGU KOREKSI (Overpriced)"
                saran = f"⏳ Harga saat ini premium. Disarankan menunggu di area Rp {entry_price:,.0f}."
            
            st.subheader(f"Status: {status}")
            st.write(f"**Target Entry:** Rp {entry_price:,.0f} | **Harga Saat Ini:** Rp {curr_price:,.0f}")
            st.info(saran)

            # --- DISCLAIMER ---
            st.markdown("---")
            st.caption("""
            **DISCLAIMER:** Data ini bersifat edukasi. Keputusan investasi sepenuhnya ada di tangan Anda. 
            Perhatikan risiko penurunan harga saham (*Capital Loss*) meskipun emiten membagikan dividen tinggi.
            """)
