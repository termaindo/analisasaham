import streamlit as st
import yfinance as yf
import pandas as pd

def run_perbandingan():
    st.title("⚖️ Perbandingan 2 Saham")
    st.markdown("---")

    # 1. INPUT 2 KODE SAHAM
    c_in1, c_in2 = st.columns(2)
    with c_in1:
        saham1 = st.text_input("Kode Saham 1 (Contoh: BBRI):", value="BBRI").upper()
    with c_in2:
        saham2 = st.text_input("Kode Saham 2 (Contoh: BMRI):", value="BMRI").upper()

    t_1 = saham1 if saham1.endswith(".JK") else f"{saham1}.JK"
    t_2 = saham2 if saham2.endswith(".JK") else f"{saham2}.JK"

    if st.button(f"Bandingkan {saham1} vs {saham2}"):
        try:
            with st.spinner("Sedang mengadu data kedua saham..."):
                # 2. AMBIL DATA
                data1 = yf.Ticker(t_1)
                data2 = yf.Ticker(t_2)
                
                info1 = data1.info
                info2 = data2.info
                
                # Data Harga Historis untuk Trend & Plan
                hist1 = data1.history(period="6mo")
                hist2 = data2.history(period="6mo")

                if hist1.empty or hist2.empty:
                    st.error("Data tidak ditemukan. Pastikan kode saham benar.")
                    return

                # --- 3. EKSTRAKSI KRITERIA ---
                def get_metrics(info, hist):
                    curr = info.get('currentPrice', 0)
                    ma20 = hist['Close'].rolling(20).mean().iloc[-1]
                    dps = info.get('dividendRate', 0)
                    
                    return {
                        "MC": f"Rp {info.get('marketCap', 0)/1e12:,.1f}T",
                        "PER": f"{info.get('trailingPE', 0):.2f}x",
                        "PBV": f"{info.get('priceToBook', 0):.2f}x",
                        "ROE": f"{info.get('returnOnEquity', 0)*100:.1f}%",
                        "DE": f"{info.get('debtToEquity', 0):.2f}",
                        "RG": f"{info.get('revenueGrowth', 0)*100:.1f}%",
                        "PM": f"{info.get('profitMargins', 0)*100:.1f}%",
                        "DY": f"{(dps/curr)*100:.2f}%" if curr > 0 else "0%",
                        "Trend": "📈 Bullish" if curr > ma20 else "📉 Bearish"
                    }

                m1 = get_metrics(info1, hist1)
                m2 = get_metrics(info2, hist2)

                # --- 4. TAMPILKAN TABEL PERBANDINGAN ---
                df_comp = pd.DataFrame({
                    "Kriteria": ["Market Cap", "PER", "PBV", "ROE", "Debt/Equity", "Revenue Growth", "Profit Margin", "Dividend Yield", "Technical Trend"],
                    saham1: [m1["MC"], m1["PER"], m1["PBV"], m1["ROE"], m1["DE"], m1["RG"], m1["PM"], m1["DY"], m1["Trend"]],
                    saham2: [m2["MC"], m2["PER"], m2["PBV"], m2["ROE"], m2["DE"], m2["RG"], m2["PM"], m2["DY"], m2["Trend"]]
                })
                
                st.table(df_comp.set_index("Kriteria"))

                # --- 5. LOGIKA KESIMPULAN & REKOMENDASI ---
                st.markdown("---")
                st.subheader("💡 Kesimpulan Ahli")
                
                # Penentuan sederhana: Bandingkan ROE dan PBV
                score1 = (1 if info1.get('returnOnEquity', 0) > info2.get('returnOnEquity', 0) else 0) + \
                         (1 if info1.get('priceToBook', 10) < info2.get('priceToBook', 10) else 0)
                
                pilihan_utama = saham1 if score1 >= 1 else saham2
                info_pilihan = info1 if pilihan_utama == saham1 else info2
                hist_pilihan = hist1 if pilihan_utama == saham1 else hist2
                
                st.write(f"- **Pilihan #1: {saham1}** - {'Profitabilitas tinggi (ROE)' if info1.get('returnOnEquity', 0) > info2.get('returnOnEquity', 0) else 'Valuasi lebih menarik'}.")
                st.write(f"- **Pilihan #2: {saham2}** - {'Fundamental solid' if info2.get('returnOnEquity', 0) > info1.get('returnOnEquity', 0) else 'Trend teknikal terpantau'}.")

                # --- 6. REKOMENDASI FINAL ---
                st.success(f"### 🏆 Saham paling Worth It SEKARANG: {pilihan_utama}")
                st.write(f"**Kenapa?** Karena memiliki perpaduan {'ROE yang lebih kuat' if info_pilihan.get('returnOnEquity', 0) > 0.15 else 'valuasi yang lebih masuk akal'} dan {m1['Trend'] if pilihan_utama == saham1 else m2['Trend']} di kondisi pasar saat ini.")

                # Trading Plan untuk Rekomendasi
                curr_rec = info_pilihan.get('currentPrice', 0)
                supp = hist_pilihan['Low'].tail(20).min()
                res = hist_pilihan['High'].tail(20).max()
                
                st.markdown("#### 🎯 Trading Plan (Acuan Masuk)")
                c1, c2, c3 = st.columns(3)
                c1.metric("Entry Buy", f"Rp {curr_rec:,.0f}")
                c2.metric("Target Profit", f"Rp {res:,.0f}")
                c3.metric("Stop Loss", f"Rp {supp:,.0f}")

        except Exception as e:
            st.error(f"Gagal membandingkan. Error: {e}")
