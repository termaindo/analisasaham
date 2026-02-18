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

    if st.button(f"Jalankan Analisa Lengkap {ticker_input}"):
        with st.spinner("Mengevaluasi fundamental & kelayakan dividen..."):
            data = get_full_stock_data(ticker)
            info = data['info']
            divs = data['dividends']
            history = data['history']
            
            if not info or divs.empty:
                st.error("Data dividen tidak ditemukan atau emiten tidak membagikan dividen.")
                return

            # --- 1. PRE-CALCULATION UNTUK SCORING ---
            curr_price = info.get('currentPrice', 0)
            yield_val = hitung_div_yield_normal(info)
            payout = info.get('payoutRatio', 0) * 100
            fcf = info.get('freeCashflow', 0)
            roe = info.get('returnOnEquity', 0) * 100
            der = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
            eps_growth = info.get('earningsGrowth', 0) * 100
            
            # Hitung CAGR & Konsistensi Dividen
            df_div = divs.to_frame(name='Dividends')
            df_div.index = pd.to_datetime(df_div.index).tz_localize(None)
            df_div_annual = df_div.resample('YE').sum().tail(5)
            
            konsistensi = len(df_div_annual)
            cagr = 0
            if konsistensi >= 2:
                awal, akhir = df_div_annual['Dividends'].iloc[0], df_div_annual['Dividends'].iloc[-1]
                if awal > 0:
                    cagr = ((akhir / awal) ** (1 / (konsistensi - 1))) - 1
            
            # --- 2. LOGIKA SCORING AKURAT (100 POIN) ---
            total_score = 0
            
            # A. Kualitas Kas (Max 20)
            if fcf > 0: total_score += 20
            
            # B. Konsistensi & Pertumbuhan (Max 20)
            if konsistensi == 5 and cagr > 0.05: total_score += 20
            elif konsistensi == 5 and cagr > 0: total_score += 15
            elif konsistensi >= 3: total_score += 10
            
            # C. Dividend Yield (Max 20)
            if yield_val >= 8: total_score += 20
            elif yield_val >= 6: total_score += 15
            elif yield_val >= 4: total_score += 10
            
            # D. Kesehatan Utang (Max 15)
            if der < 1.0: total_score += 15
            elif der <= 2.0: total_score += 10
            
            # E. Payout Ratio (Max 15)
            if 30 <= payout <= 70: total_score += 15
            elif 70 < payout <= 90: total_score += 10
            elif payout > 0: total_score += 5
            
            # F. Kinerja Bisnis (Max 10)
            if roe > 15 and eps_growth > 0: total_score += 10
            elif roe > 8: total_score += 5

            # Teks Status Skor
            if total_score >= 80:
                score_status = "Luar Biasa (Sangat Layak Dikoleksi)"
            elif total_score >= 60:
                score_status = "Cukup (Layak dengan Pantauan)"
            else:
                score_status = "Kurang (Resiko Tinggi / Watchlist)"

            # --- 3. LOGIKA KONFIDENSI DATA ---
            metrik_kunci = ['payoutRatio', 'returnOnEquity', 'freeCashflow', 'debtToEquity', 'earningsGrowth', 'trailingEps']
            tersedia = sum(1 for m in metrik_kunci if info.get(m) is not None)
            konfidensi_persen = (tersedia / len(metrik_kunci)) * 100
            conf_color = "🟢" if konfidensi_persen >= 100 else "🟡" if konfidensi_persen >= 70 else "🔴"
            conf_label = "Tinggi" if konfidensi_persen >= 100 else "Sedang" if konfidensi_persen >= 70 else "Rendah"

            # --- 4. HEADER: IDENTITAS & SKOR (Style Match: Fundamental Pro) ---
            company_name = info.get('longName', ticker_input)
            status_syr_icon = "✅" if is_syariah(kode_bersih) else "❌"
            status_syr_text = "Syariah" if is_syariah(kode_bersih) else "Non-Syariah"
            sector = info.get('sector', 'Sektor Tidak Diketahui')

            st.markdown(f"""
                <div style="text-align: center; padding: 20px; background-color: #1E1E1E; border-radius: 10px; border: 1px solid #333;">
                    <h1 style="color: #2ECC71; margin-bottom: 5px; font-size: 2.5em;">🏢 {ticker_input} - {company_name}</h1>
                    <p style="color: #A0A0A0; font-size: 1.2em; margin-bottom: 15px;">
                        Sektor: {sector} | <span style="color: white;">{status_syr_icon} {status_syr_text}</span>
                    </p>
                    <h3 style="color: white; margin-bottom: 5px;">🏆 SKOR KELAYAKAN DIVIDEN</h3>
                    <div style="background-color: #333; border-radius: 5px; height: 10px; margin-bottom: 10px;">
                        <div style="background-color: #2ECC71; width: {total_score}%; height: 10px; border-radius: 5px;"></div>
                    </div>
                    <div style="background-color: #2E3317; padding: 10px; border-radius: 5px; border-left: 5px solid #2ECC71; margin-bottom: 10px;">
                        <p style="color: #D4E157; margin: 0; font-weight: bold; font-size: 1.1em;">
                            Skor: {total_score}/100 — {score_status}
                        </p>
                    </div>
                    <p style="color: #A0A0A0; font-size: 0.9em; margin: 0;">
                        Tingkat Kepercayaan Data: {conf_color} {conf_label} ({konfidensi_persen:.0f}% metrik tersedia)
                    </p>
                </div>
            """, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

            # --- SEKSI 1: HISTORY ---
            st.header("1. History & Pertumbuhan Dividen")
            df_div_annual.index = df_div_annual.index.year
            st.bar_chart(df_div_annual['Dividends'])
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Dividend Yield", f"{yield_val:.2f}%")
            m2.metric("Payout Ratio", f"{payout:.1f}%")
            m3.metric("Konsistensi", f"{konsistensi}/5 Thn")
            m4.metric("Growth (CAGR)", f"{cagr*100:.1f}%")

            # --- SEKSI 2: KINERJA BISNIS ---
            st.header("2. Kinerja Bisnis")
            col_biz1, col_biz2 = st.columns(2)
            with col_biz1:
                st.write("**EPS Growth (YoY):**")
                st.success(f"📈 {eps_growth:.1f}%") if eps_growth > 0 else st.error(f"📉 {eps_growth:.1f}%")
            with col_biz2:
                st.write("**Return on Equity (ROE):**")
                st.success(f"💎 {roe:.1f}%") if roe > 15 else st.info(f"👍 {roe:.1f}%") if roe > 8 else st.warning(f"⚠️ {roe:.1f}%")

            # --- SEKSI 3: KESEHATAN FINANSIAL ---
            st.header("3. Kesehatan Finansial")
            col_fin1, col_fin2 = st.columns(2)
            with col_fin1:
                st.write("**Kualitas Kas (FCF):**")
                st.success("✅ Positif (Dana Aman)") if fcf > 0 else st.error("❌ Negatif (Risiko Kas)")
            with col_fin2:
                st.write("**Debt to Equity Ratio (DER):**")
                st.success(f"✅ {der:.2f}x") if der < 1.0 else st.warning(f"⚠️ {der:.2f}x")

            # --- SEKSI 4: PROYEKSI & PROTEKSI ---
            st.header("4. Proyeksi & Proteksi")
            est_dps = info.get('trailingEps', 0) * (payout / 100)
            atr = (history['High'] - history['Low']).tail(14).mean()
            sl_final = max(curr_price - (1.5 * atr), curr_price * 0.92)
            
            p1, p2 = st.columns(2)
            with p1:
                st.info(f"**Estimasi DPS Mendatang:**\n\nRp {est_dps:,.0f} / Lembar")
                st.write(f"**Potential Yield:** {(est_dps/curr_price)*100:.2f}%")
            with p2:
                st.error(f"**Stop Loss Level (Lock 8%):**\n\nRp {sl_final:,.0f}")

            # --- SEKSI 5: REKOMENDASI ---
            st.header("5. Rekomendasi")
            deposito_rate = 5.0
            entry_price = est_dps / (deposito_rate/100) if est_dps > 0 else 0
            
            status_final = "SANGAT LAYAK (Top Pick)" if (curr_price < entry_price and total_score >= 80) else "LAYAK" if curr_price < entry_price else "TUNGGU KOREKSI"
            st.subheader(f"Status: {status_final}")
            st.write(f"**Harga wajar bila dividen setara dengan deposito dengan bagi hasil 5%:** Rp {entry_price:,.0f}")
            st.write(f"**Harga Saham Saat Ini:** Rp {curr_price:,.0f}")
            
            # --- DISCLAIMER ---
            st.markdown("---")
            st.caption("**DISCLAIMER:** Data dan analisa ini dihasilkan secara otomatis untuk tujuan edukasi. Keputusan investasi sepenuhnya adalah tanggung jawab investor.")
