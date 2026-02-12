import streamlit as st
import pandas as pd
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_perbandingan():
    st.title("⚖️ Perbandingan 2 Saham")
    st.markdown("---")

    c_inp1, c_inp2 = st.columns(2)
    with c_inp1:
        tk1 = st.text_input("Saham A:", value="BBCA").upper()
    with c_inp2:
        tk2 = st.text_input("Saham B:", value="BBRI").upper()

    if st.button("Bandingkan Sekarang"):
        t1 = tk1 if tk1.endswith(".JK") else f"{tk1}.JK"
        t2 = tk2 if tk2.endswith(".JK") else f"{tk2}.JK"

        with st.spinner(f"Mengadu {tk1} vs {tk2}..."):
            d1 = get_full_stock_data(t1)
            d2 = get_full_stock_data(t2)

            if not d1['info'] or not d2['info']:
                st.error("Gagal mengambil data salah satu saham.")
                return

            i1, i2 = d1['info'], d2['info']

            # --- TABEL PERBANDINGAN ---
            comp_data = {
                "Metrik": ["Harga", "PER", "PBV", "ROE", "NPM", "Div. Yield", "Market Cap (T)"],
                tk1: [
                    f"Rp {i1.get('currentPrice', 0):,.0f}",
                    f"{i1.get('trailingPE', 0):.2f}x",
                    f"{i1.get('priceToBook', 0):.2f}x",
                    f"{i1.get('returnOnEquity', 0)*100:.1f}%",
                    f"{i1.get('profitMargins', 0)*100:.1f}%",
                    f"{hitung_div_yield_normal(i1):.2f}%",
                    f"{i1.get('marketCap', 0)/1e12:.1f}"
                ],
                tk2: [
                    f"Rp {i2.get('currentPrice', 0):,.0f}",
                    f"{i2.get('trailingPE', 0):.2f}x",
                    f"{i2.get('priceToBook', 0):.2f}x",
                    f"{i2.get('returnOnEquity', 0)*100:.1f}%",
                    f"{i2.get('profitMargins', 0)*100:.1f}%",
                    f"{hitung_div_yield_normal(i2):.2f}%",
                    f"{i2.get('marketCap', 0)/1e12:.1f}"
                ]
            }
            
            st.table(pd.DataFrame(comp_data).set_index("Metrik"))

            # --- ANALISA SINGKAT ---
            st.subheader("💡 Kesimpulan Cepat")
            # Logika perbandingan sederhana
            if i1.get('trailingPE', 99) < i2.get('trailingPE', 99):
                st.write(f"- **Valuasi:** {tk1} secara relatif lebih murah (PER rendah).")
            else:
                st.write(f"- **Valuasi:** {tk2} secara relatif lebih murah (PER rendah).")

            if i1.get('returnOnEquity', 0) > i2.get('returnOnEquity', 0):
                st.write(f"- **Profitabilitas:** {tk1} lebih efisien mencetak laba (ROE tinggi).")
            else:
                st.write(f"- **Profitabilitas:** {tk2} lebih efisien mencetak laba (ROE tinggi).")
