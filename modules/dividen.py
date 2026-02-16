import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Import dari data_loader
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal
# Import fungsi is_syariah dari universe (Single Source of Truth)
from modules.universe import is_syariah

def run_dividen():
    st.title("💰 Analisa Dividen Pro (Passive Income Investing)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Dividend Check):", value="ITMG").upper()
    
    # Format ticker untuk Yahoo Finance (.JK)
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"
    # Format kode bersih untuk pengecekan di universe.py (tanpa .JK)
    kode_bersih = ticker_input.replace(".JK", "").upper()

    if st.button(f"Analisa Dividen {ticker_input}"):
        with st.spinner("Mengevaluasi histori, kesehatan kas, dan kelayakan scoring..."):
            data = get_full_stock_data(ticker)
            info = data['info']
            divs = data['dividends']
            history = data['history']
            
            if not info or divs.empty:
                st.error("Data dividen tidak ditemukan atau emiten tidak membagikan dividen.")
                return

            curr_price = info.get('currentPrice', 0)
            sector = info.get('sector', 'Sektor Tidak Diketahui')
            company_name = info.get('longName', ticker_input)
            
            # Cek status syariah menggunakan Single Source of Truth dari universe.py
            if is_syariah(kode_bersih):
                status_syariah = "✅ Ya (Masuk Daftar Efek Syariah ISSI)"
            else:
                status_syariah = "❌ Tidak / Perlu Konfirmasi OJK"
            
            # --- HEADER INFO ---
            st.subheader(f"{company_name} ({ticker_input})")
            st.write(f"**Sektor:** {sector} | **Kategori Syariah:** {status_syariah}")
            st.markdown("---")
            
            # --- 1. DIVIDEND HISTORY & GROWTH ---
            st.header("1. HISTORY & PERTUMBUHAN DIVIDEN")
            df_div = divs.to_frame(name='Dividends')
            df_div.index = pd.to_datetime(df_div.index).tz_localize(None)
            df_div_annual = df_div.resample('YE').sum().tail(5)
            df_div_annual.index = df_div_annual.index.year
            
            st.bar_chart(df_div_annual['Dividends'])
            
            # Kalkulasi CAGR Dividen
            cagr = 0
            if len(df_div_annual) >= 2:
                awal = df_div_annual['Dividends'].iloc[0]
                akhir = df_div_annual['Dividends'].iloc[-1]
                if awal > 0:
                    tahun = len(df_div_annual) - 1
                    cagr = ((akhir / awal) ** (1 / tahun)) - 1
            cagr_pct = cagr * 100

            yield_val = hitung_div_yield_normal(info)
            payout = info.get('payoutRatio', 0) * 100
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Dividend Yield", f"{yield_val:.2f}%")
            c2.metric("Payout Ratio", f"{payout:.1f}%")
            c3.metric("Konsistensi", f"{len(df_div_annual)}/5 Thn")
            c4.metric("Div. Growth (CAGR)", f"{cagr_pct:.1f}%")

            # --- 2. KESEHATAN KEUANGAN ---
            st.header("2. KESEHATAN FINANSIAL & PROFITABILITAS")
            fcf = info.get('freeCashflow', 0)
            der = info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else 0
            roe = info.get('returnOnEquity', 0) * 100
            eps_growth = info.get('earningsGrowth', 0) * 100
            
            col_health1, col_health2 = st.columns(2)
            with col_health1:
                if fcf > 0:
                    st.success(f"✅ **FCF Positif:** Rp {fcf:,.0f} (Aman)")
                else:
                    st.warning("⚠️ **FCF Negatif:** Waspada dividen dari utang/kas ditahan.")
                
                if roe > 15:
                    st.success(f"✅ **ROE Tinggi:** {roe:.1f}% (Efisien)")
                else:
                    st.info(f"ℹ️ **ROE:** {roe:.1f}%")

            with col_health2:
                if der < 1.0:
                    st.success(f"✅ **Utang Terkendali:** DER {der:.2f}x")
                else:
                    st.warning(f"⚠️ **Utang Tinggi:** DER {der:.2f}x")
                
                st.write(f"**EPS Growth (YoY):** {eps_growth:.1f}%")

            # --- 3. SCORING KELAYAKAN (SKALA 100) ---
            st.header("3. SKOR KELAYAKAN DIVIDEN (High Yield)")
            total_score = 0
            
            # Aspek 1: Yield (Max 20)
            if yield_val > 8: total_score += 20
            elif yield_val >= 6: total_score += 15
            elif yield_val >= 4: total_score += 10
            
            # Aspek 2: DPR (Max 15)
            if 30 <= payout <= 60: total_score += 15
            elif 61 <= payout <= 80: total_score += 10
            elif 81 <= payout <= 95: total_score += 5
            
            # Aspek 3: Growth & Konsistensi (Max 15)
            if cagr_pct > 10: total_score += 15
            elif cagr_pct >= 5: total_score += 10
            elif cagr_pct > 0: total_score += 5
            
            # Aspek 4: Kas & Utang (Max 20)
            if fcf > 0 and der < 1.0: total_score += 20
            elif fcf > 0 and der <= 2.0: total_score += 10
            
            # Aspek 5: Kinerja / Profitabilitas (Max 20)
            if eps_growth > 10 and roe > 15: total_score += 20
            elif eps_growth > 0 and roe >= 8: total_score += 10
            
            # Aspek 6: Proteksi Dividend Trap (Max 10) - Simulasi Sederhana
            if cagr_pct > 0 and fcf > 0 and payout < 80:
                total_score += 10 # Cenderung aman dari trap
            else:
                total_score += 5 # Risiko menengah
                
            # Evaluasi Skor
            st.progress(total_score / 100)
            if total_score >= 85:
                st.success(f"🏆 **Skor: {total_score}/100 (SANGAT LAYAK DIKOLEKSI)** - Fundamental prima & aman dari jebakan dividen.")
            elif total_score >= 65:
                st.info(f"📊 **Skor: {total_score}/100 (LAYAK DENGAN PANTAUAN)** - Bagus, namun perhatikan siklus utang atau fluktuasi laba.")
            else:
                st.error(f"🚫 **Skor: {total_score}/100 (RESIKO TINGGI / HINDARI)** - Rawan *dividend trap*, fundamental kurang mendukung tingginya *yield*.")

            # --- 4. PROYEKSI & PROTEKSI ---
            st.header("4. PROYEKSI & PROTEKSI")
            est_dps = info.get('trailingEps', 0) * (payout / 100)
            
            atr = (history['High'] - history['Low']).tail(14).mean()
            sl_raw = curr_price - (1.5 * atr)
            sl_final = max(sl_raw, curr_price * 0.92) # LOCK 8%
            
            st.info(f"**Estimasi DPS Mendatang:** Rp {est_dps:,.0f} / lembar\n\n**Potential Yield:** {(est_dps/curr_price)*100:.2f}%")
            st.error(f"**Stop Loss Level (Max 8%):** Rp {sl_final:,.0f}")

            # --- 5. REKOMENDASI VALUASI ---
            st.header("5. REKOMENDASI")
            deposito_rate = 5.0
            entry_price = est_dps / (deposito_rate/100) if est_dps > 0 else 0
            
            st.write(f"**Target Entry Price (Mengejar Yield {deposito_rate}%):** Rp {entry_price:,.0f}")
            st.write(f"**Harga Saham Saat Ini:** Rp {curr_price:,.0f}")
            
            if curr_price < entry_price and entry_price >
