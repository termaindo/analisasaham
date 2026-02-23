import streamlit as st
import pandas as pd
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_perbandingan():
    st.title("⚖️ Perbandingan Saham Pro (Head-to-Head)")
    st.markdown("---")

    c_input1, c_input2 = st.columns(2)
    with c_input1:
        tk1 = st.text_input("Kode Saham 1:", value="BBCA").upper()
    with c_input2:
        tk2 = st.text_input("Kode Saham 2:", value="BBRI").upper()

    if st.button(f"Bandingkan {tk1} vs {tk2}"):
        with st.spinner(f"Mengadu data {tk1} dan {tk2}..."):
            # --- STANDAR ANTI-ERROR ---
            t1 = tk1 if tk1.endswith(".JK") else f"{tk1}.JK"
            t2 = tk2 if tk2.endswith(".JK") else f"{tk2}.JK"
            
            data1 = get_full_stock_data(t1)
            data2 = get_full_stock_data(t2)
            
            if not data1['info'] or not data2['info']:
                st.error("Gagal mengambil data salah satu saham. Cek koneksi atau kode ticker.")
                return

            i1, i2 = data1['info'], data2['info']
            h1, h2 = data1['history'], data2['history']

            # --- KALKULASI TEKNIKAL & SL 8% ---
            def get_tech_status(df):
                curr = df['Close'].iloc[-1]
                ma200 = df['Close'].rolling(200).mean().iloc[-1]
                return "Bullish 🐂" if curr > ma200 else "Bearish 🐻"

            def get_sl_cap(df):
                curr = df['Close'].iloc[-1]
                atr = (df['High'] - df['Low']).tail(14).mean()
                sl_atr = curr - (1.5 * atr)
                return max(sl_atr, curr * 0.92) # LOCK 8%

            # --- KONSTRUKSI TABEL PERBANDINGAN ---
            comparison_data = {
                "Kriteria": [
                    "Market Cap", "PER", "PBV", "ROE", "Debt/Equity", 
                    "Revenue Growth", "Profit Margin", "Dividend Yield", "Technical Trend", "Stop Loss (Max 8%)"
                ],
                tk1: [
                    f"Rp {i1.get('marketCap', 0)/1e12:,.1f} T",
                    f"{i1.get('trailingPE', 0):.2f}x",
                    f"{i1.get('priceToBook', 0):.2f}x",
                    f"{i1.get('returnOnEquity', 0)*100:.1f}%",
                    f"{i1.get('debtToEquity', 0):.2f}x",
                    f"{i1.get('revenueGrowth', 0)*100:.1f}%",
                    f"{i1.get('profitMargins', 0)*100:.1f}%",
                    f"{hitung_div_yield_normal(i1):.2f}%",
                    get_tech_status(h1),
                    f"Rp {get_sl_cap(h1):,.0f}"
                ],
                tk2: [
                    f"Rp {i2.get('marketCap', 0)/1e12:,.1f} T",
                    f"{i2.get('trailingPE', 0):.2f}x",
                    f"{i2.get('priceToBook', 0):.2f}x",
                    f"{i2.get('returnOnEquity', 0)*100:.1f}%",
                    f"{i2.get('debtToEquity', 0):.2f}x",
                    f"{i2.get('revenueGrowth', 0)*100:.1f}%",
                    f"{i2.get('profitMargins', 0)*100:.1f}%",
                    f"{hitung_div_yield_normal(i2):.2f}%",
                    get_tech_status(h2),
                    f"Rp {get_sl_cap(h2):,.0f}"
                ]
            }

            st.table(pd.DataFrame(comparison_data).set_index("Kriteria"))

            # --- KESIMPULAN & REKOMENDASI ---
            st.markdown("---")
            st.header("💡 KESIMPULAN")
            
            # Logika penentuan Pilihan #1
            if i1.get('returnOnEquity', 0) > i2.get('returnOnEquity', 0):
                p1, p2 = tk1, tk2
                r1 = "Efisiensi mencetak laba (ROE) lebih tinggi."
                r2 = "Valuasi mungkin lebih murah namun efisiensi di bawah Pilihan #1."
            else:
                p1, p2 = tk2, tk1
                r1 = "Efisiensi mencetak laba (ROE) lebih unggul."
                r2 = "Posisi sebagai penantang dengan valuasi berbeda."

            st.write(f"**Pilihan #1: {p1}** - {r1}")
            st.write(f"**Pilihan #2: {p2}** - {r2}")

            st.markdown("---")
            st.subheader(f"Saham mana yang paling worth it untuk dibeli SEKARANG?")
            
            # Logika "Worth It" (Valuasi + Trend)
            if get_tech_status(h1) == "Bullish 🐂" and i1.get('trailingPE', 99) < 20:
                best = tk1
                reason = f"{tk1} sedang dalam fase Bullish dengan valuasi PER yang masih masuk akal."
            elif get_tech_status(h2) == "Bullish 🐂" and i2.get('trailingPE', 99) < 20:
                best = tk2
                reason = f"{tk2} memiliki momentum teknikal kuat didukung fundamental solid."
            else:
                best = p1
                reason = f"{p1} secara keseluruhan memiliki skor kualitas (ROE & Margin) terbaik."

            st.success(f"**JAWABAN:** {best}. **ALASAN:** {reason}")

            # --- TRADING PLAN (DAY TRADE) ---
            def render_trading_plan(ticker, df):
                curr = df['Close'].iloc[-1]
                # Proksi VWAP harian sederhana menggunakan Typical Price
                vwap = (df['High'].iloc[-1] + df['Low'].iloc[-1] + df['Close'].iloc[-1]) / 3
                
                # Kalkulasi Entry Bawah (Maksimal turun 1.5% atau VWAP, ambil yang tertinggi)
                batas_bawah = curr * 0.985
                entry_bawah = max(batas_bawah, vwap)
                
                st.info(f"""
                **🎯 Trading Plan {ticker}**
                * **Harga Saat Ini:** Rp {curr:,.0f}
                * **Rentang Entry (Support Dinamis):** dengan Entry Bawah di kisaran **Rp {entry_bawah:,.0f}** *(Maksimal turun 1.5% dari harga saat ini atau di garis VWAP, ambil mana yang lebih tinggi agar tidak menawar terlalu bawah).*
                * **SL:** Maksimal turun **3%** dari harga beli.
                * **Target (TP):** RRR 1:1.5 (Profit sekitar **4.5% - 5%**).
                """)

            # Menentukan data history untuk saham rekomendasi dan alternatif
            best_history = h1 if best == tk1 else h2
            second_ticker = tk2 if best == tk1 else tk1
            second_history = h2 if best == tk1 else h1

            st.markdown("<br>", unsafe_allow_html=True)
            st.write(f"Untuk saham **{best}** yang disarankan di atas, berikut adalah Trading Plan untuk mode Day Trade:")
            render_trading_plan(best, best_history)

            st.write(f"Bila Anda juga tetap mempertimbangkan saham yang kedua (**{second_ticker}**), maka berikut trading plan untuk mode Day Trading:")
            render_trading_plan(second_ticker, second_history)

            # --- PERNYATAAN DISCLAIMER ---
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.divider()
            st.caption(f"⚠️ **Sanggahan (Disclaimer):** Analisis perbandingan antara {tk1} dan {tk2} ini dihasilkan secara otomatis untuk tujuan edukasi dan informasi semata. "
                       "Ini bukan merupakan perintah beli atau jual. Keputusan investasi sepenuhnya berada di tangan Anda. "
                       "Kinerja masa lalu tidak menjamin hasil di masa depan. Selalu lakukan analisis fundamental dan teknikal mandiri (DYOR) "
                       "sebelum menempatkan modal pada instrumen saham.")
