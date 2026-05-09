import streamlit as st
import pandas as pd
from data_loader import enrich_and_filter

def render_admin_panel():
    st.header("⚙️ Panel Admin — Enrichment Data Saham")
    st.caption("Proses ini membaca `pre_liquid_stocks.csv`, fetch data tiap saham, lalu menyimpan hasilnya ke `liquid_stocks.csv`.")

    # ── Preview pre_liquid_stocks.csv ────────────────────────────────────
    st.subheader("📋 Daftar Saham (pre_liquid_stocks.csv)")
    try:
        df_pre = pd.read_csv('pre_liquid_stocks.csv')
        st.dataframe(df_pre, use_container_width=True)
        st.caption(f"Total: {len(df_pre)} saham")
    except FileNotFoundError:
        st.error("`pre_liquid_stocks.csv` tidak ditemukan. Pastikan file ada di direktori yang sama.")
        return

    st.divider()

    # ── Parameter Filter ─────────────────────────────────────────────────
    st.subheader("🔧 Parameter Filter")
    col1, col2 = st.columns(2)
    with col1:
        min_value_ma20 = st.number_input(
            "Value MA20 minimum (Rp)",
            value=2_000_000_000,
            step=500_000_000,
            format="%d",
            help="Saham dengan rata-rata nilai transaksi 20 hari di bawah angka ini akan dibuang."
        )
        min_roe = st.number_input(
            "ROE minimum (%)",
            value=10.0,
            step=1.0,
            format="%.1f"
        )
    with col2:
        st.info("**ROA** selalu difilter > 0% (tidak bisa diubah).\n\n**CAR & NPL** hanya diisi untuk saham sektor Bank.")

    st.divider()

    # ── Tombol Jalankan ──────────────────────────────────────────────────
    st.subheader("🚀 Jalankan Enrichment")
    st.warning("⏳ Proses ini bisa memakan waktu beberapa menit tergantung jumlah saham. Jangan tutup halaman ini.")

    if st.button("▶️ Mulai Enrichment & Filter", type="primary"):
        progress_bar  = st.progress(0, text="Memulai...")
        status_text   = st.empty()
        result_holder = st.empty()

        def on_progress(i, total, ticker):
            pct = int((i / total) * 100)
            progress_bar.progress(pct, text=f"Fetching ({i}/{total}): {ticker}")
            status_text.caption(f"Sedang memproses: `{ticker}`")

        try:
            df_result, total_before, total_after = enrich_and_filter(
                pre_csv_path='pre_liquid_stocks.csv',
                out_csv_path='liquid_stocks.csv',
                min_value_ma20=min_value_ma20,
                min_roe=min_roe,
                progress_callback=on_progress
            )

            progress_bar.progress(100, text="Selesai!")
            status_text.empty()

            # ── Ringkasan Hasil ──────────────────────────────────────────
            st.success(f"✅ Enrichment selesai! `liquid_stocks.csv` berhasil disimpan.")

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Awal", f"{total_before} saham")
            m2.metric("Lolos Filter", f"{total_after} saham")
            m3.metric("Dibuang", f"{total_before - total_after} saham")

            st.subheader("📊 Hasil liquid_stocks.csv")

            # Format kolom uang agar lebih mudah dibaca
            df_display = df_result.copy()
            if 'Value_MA20' in df_display.columns:
                df_display['Value_MA20'] = df_display['Value_MA20'].apply(
                    lambda x: f"Rp {x:,.0f}" if pd.notna(x) else "-"
                )
            for col in ['ROE', 'ROA', 'CAR', 'NPL', 'Median_PER_3Y', 'Median_PBV_3Y']:
                if col in df_display.columns:
                    df_display[col] = df_display[col].apply(
                        lambda x: f"{x:.2f}" if pd.notna(x) else "-"
                    )

            st.dataframe(df_display, use_container_width=True)

            # Tombol download manual (opsional)
            csv_bytes = df_result.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Download liquid_stocks.csv",
                data=csv_bytes,
                file_name="liquid_stocks.csv",
                mime="text/csv"
            )

        except ValueError as ve:
            st.error(f"❌ Error pada file CSV: {ve}")
        except Exception as e:
            st.error(f"❌ Terjadi kesalahan: {e}")


# Jika dijalankan langsung sebagai halaman Streamlit
if __name__ == "__main__":
    st.set_page_config(page_title="Admin Panel", layout="wide")
    render_admin_panel()
