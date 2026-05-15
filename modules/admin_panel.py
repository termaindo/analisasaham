"""
admin_panel.py
==============
Panel admin untuk proses enrichment data saham.

Alur kerja baru (tanpa Google Drive):
  Step 1 → Preview pre_liquid_stocks.csv
  Step 2 → Jalankan enrichment & filter → tampilkan hasil + tombol download CSV
  Step 3 → Instruksi manual: simpan CSV → upload ke /data di GitHub → app otomatis pakai
"""

import streamlit as st
import pandas as pd
import os

from data_loader import enrich_and_filter, clear_liquid_stocks_cache, LIQUID_PATH


def render_admin_panel() -> None:
    st.header("⚙️ Panel Admin — Enrichment Data Saham")
    st.caption(
        "Proses ini membaca `pre_liquid_stocks.csv`, fetch data tiap saham, "
        "lalu menghasilkan `liquid_stocks.csv` yang bisa kamu download dan upload ke GitHub."
    )

    # ── Step 1: Preview pre_liquid_stocks.csv ────────────────────────────────
    st.subheader("📋 Step 1 — Daftar Saham (pre_liquid_stocks.csv)")
    try:
        df_pre = pd.read_csv("data/pre_liquid_stocks.csv")
        st.dataframe(df_pre, use_container_width=True)
        st.caption(f"Total: {len(df_pre)} saham")
    except FileNotFoundError:
        st.error(
            "`data/pre_liquid_stocks.csv` tidak ditemukan. "
            "Pastikan file ada di folder `/data` di root repo."
        )
        return

    st.divider()

    # ── Step 2: Parameter Filter & Jalankan Enrichment ───────────────────────
    st.subheader("🔧 Step 2 — Parameter Filter & Enrichment")
    col1, col2 = st.columns(2)
    with col1:
        min_value_ma20 = st.number_input(
            "Value MA20 minimum (Rp)",
            value=2_000_000_000,
            step=500_000_000,
            format="%d",
            help="Saham dengan rata-rata nilai transaksi 20 hari di bawah angka ini akan dibuang.",
        )
        min_roe = st.number_input(
            "ROE minimum (%)",
            value=10.0,
            step=1.0,
            format="%.1f",
        )
    with col2:
        st.info(
            "**ROA** selalu difilter > 0% (tidak bisa diubah).\n\n"
            "**CAR & NPL** hanya diisi untuk saham sektor Bank."
        )

    st.warning(
        "⏳ Proses enrichment bisa memakan waktu beberapa menit "
        "tergantung jumlah saham. Jangan tutup halaman ini."
    )

    if st.button("▶️ Mulai Enrichment & Filter", type="primary"):
        progress_bar  = st.progress(0, text="Memulai...")
        status_text   = st.empty()

        def on_progress(i: int, total: int, ticker: str) -> None:
            pct = int((i / total) * 100)
            progress_bar.progress(pct, text=f"Fetching ({i}/{total}): {ticker}")
            status_text.caption(f"Sedang memproses: `{ticker}`")

        try:
            df_result, total_before, total_after = enrich_and_filter(
                df_input=df_pre,
                min_value_ma20=min_value_ma20,
                min_roe=min_roe,
                progress_callback=on_progress,
            )

            progress_bar.progress(100, text="Selesai!")
            status_text.empty()

            # Ringkasan
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Awal",  f"{total_before} saham")
            m2.metric("Lolos Filter", f"{total_after} saham")
            m3.metric("Dibuang",     f"{total_before - total_after} saham")

            # Preview hasil
            st.subheader("📊 Preview liquid_stocks.csv")
            df_display = df_result.copy()
            if "Value_MA20" in df_display.columns:
                df_display["Value_MA20"] = df_display["Value_MA20"].apply(
                    lambda x: f"Rp {x:,.0f}" if pd.notna(x) else "-"
                )
            for col in ["ROE", "ROA", "CAR", "NPL", "Median_PER_3Y", "Median_PBV_3Y"]:
                if col in df_display.columns:
                    df_display[col] = df_display[col].apply(
                        lambda x: f"{x:.2f}" if pd.notna(x) else "-"
                    )
            st.dataframe(df_display, use_container_width=True)

            # Simpan ke session_state supaya tombol download di Step 3 bisa akses
            st.session_state["enrichment_result"] = df_result

        except ValueError as ve:
            st.error(f"❌ Error pada file CSV: {ve}")
        except Exception as e:
            st.error(f"❌ Terjadi kesalahan tidak terduga: {e}")

    st.divider()

    # ── Step 3: Download & Instruksi Upload ke GitHub ─────────────────────────
    st.subheader("⬇️ Step 3 — Download & Upload ke GitHub")

    if "enrichment_result" not in st.session_state:
        st.info("Jalankan enrichment di Step 2 terlebih dahulu untuk mengaktifkan tombol download.")
    else:
        df_result = st.session_state["enrichment_result"]
        csv_bytes = df_result.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="⬇️ Download liquid_stocks.csv",
            data=csv_bytes,
            file_name="liquid_stocks.csv",
            mime="text/csv",
            type="primary",
        )

        st.markdown("""
**Setelah download, ikuti langkah berikut:**

1. Buka repo GitHub kamu di browser
2. Masuk ke folder **`data/`**
3. Klik **"Add file"** → **"Upload files"**
4. Upload file `liquid_stocks.csv` yang baru saja kamu download
5. Klik **"Commit changes"** → Streamlit Cloud akan otomatis restart dan pakai data terbaru

> ⚠️ Pastikan nama file tetap `liquid_stocks.csv` (huruf kecil semua) agar path di kode cocok.
        """)

        # Status file yang saat ini aktif di server
        st.divider()
        st.caption("**Status file saat ini di server:**")
        if os.path.exists(LIQUID_PATH):
            mtime = os.path.getmtime(LIQUID_PATH)
            import datetime
            tgl = datetime.datetime.fromtimestamp(mtime).strftime("%d %b %Y %H:%M")
            st.success(f"✅ `liquid_stocks.csv` ditemukan — terakhir diupdate: {tgl}")
            if st.button("🔄 Clear cache (paksa baca ulang file terbaru)"):
                clear_liquid_stocks_cache()
                st.success("Cache dikosongkan. Data terbaru akan dimuat pada request berikutnya.")
        else:
            st.warning(
                "⚠️ `liquid_stocks.csv` belum ada di folder `/data`. "
                "Semua modul akan fallback ke `pre_liquid_stocks.csv`."
            )


if __name__ == "__main__":
    st.set_page_config(page_title="Admin Panel", layout="wide")
    render_admin_panel()
