"""
admin_panel.py
==============
Panel admin untuk proses enrichment data saham.

Alur kerja (tanpa Google Drive):
  Step 1 → Preview pre_liquid_stocks.csv
  Step 2 → Jalankan enrichment profil Trading → download liquid_stocks.csv
  Step 3 → Jalankan enrichment profil Dividen → download liquid_dividend_stocks.csv
  Step 4 → Upload kedua file ke /data di GitHub

Dua file output terpisah:
  liquid_stocks.csv          → universe screening Day Trade & Swing Trade
  liquid_dividend_stocks.csv → universe analisa Dividen (kolom HDY lengkap)
"""

import datetime
import os

import pandas as pd
import streamlit as st

from utils.data_loader import (
    LIQUID_PATH,
    LIQUID_DIVIDEND_PATH,
    PRE_LIQUID_PATH,
    clear_liquid_stocks_cache,
    clear_liquid_dividend_stocks_cache,
    enrich_and_filter,
)

# Import lazy — hindari circular import karena screening.py juga import data_loader
def _clear_universe_cache() -> None:
    """Clear cache load_universe() di screening.py secara lazy."""
    try:
        from modules.screening import clear_load_universe_cache
        clear_load_universe_cache()
    except Exception:
        pass  # Modul belum dimuat — tidak masalah, cache belum ada

# Konfigurasi per profil
_PROFIL_CONFIG = {
    "trading": {
        "label":         "📈 Trading",
        "file_name":     "liquid_stocks.csv",
        "liquid_path":   LIQUID_PATH,
        "clear_cache":   clear_liquid_stocks_cache,
        "min_value_ma20": 2_000_000_000,
        "min_roe":        10.0,
        "deskripsi":     (
            "Universe untuk modul Screening (Day Trade & Swing Trade). "
            "Threshold ketat, tanpa kolom HDY."
        ),
        "kolom_hdy": False,
    },
    "dividen": {
        "label":         "💰 Dividen",
        "file_name":     "liquid_dividend_stocks.csv",
        "liquid_path":   LIQUID_DIVIDEND_PATH,
        "clear_cache":   clear_liquid_dividend_stocks_cache,
        "min_value_ma20": 500_000_000,
        "min_roe":         5.0,
        "deskripsi":     (
            "Universe untuk modul Analisa Dividen (HDY). "
            "Threshold lebih longgar + kolom EPS_5Y, DPS_5Y, FCF_5Y, PR_5Y, DY_5Y, ICR, DebtEBITDA."
        ),
        "kolom_hdy": True,
    },
}


def _render_enrichment_panel(profil: str, df_pre: pd.DataFrame) -> None:
    """Render panel enrichment untuk satu profil (trading atau dividen)."""
    cfg      = _PROFIL_CONFIG[profil]
    state_key_result = f"enrichment_result_{profil}"
    state_key_done   = f"enrichment_done_{profil}"

    with st.expander(
        f"{cfg['label']} — {cfg['file_name']}",
        expanded=not st.session_state.get(state_key_done, False),
    ):
        st.caption(cfg["deskripsi"])

        col1, col2 = st.columns(2)
        with col1:
            min_value_ma20 = st.number_input(
                "Value MA20 minimum (Rp)",
                value=cfg["min_value_ma20"],
                step=500_000_000,
                format="%d",
                key=f"val_ma20_{profil}",
                help="Saham dengan rata-rata nilai transaksi 20 hari di bawah angka ini akan dibuang.",
            )
            min_roe = st.number_input(
                "ROE minimum (%)",
                value=cfg["min_roe"],
                step=1.0,
                format="%.1f",
                key=f"min_roe_{profil}",
            )
        with col2:
            st.info(
                "**ROA** selalu difilter > 0% (tidak bisa diubah).\n\n"
                "**CAR & NPL** hanya diisi untuk saham sektor Bank."
                + (
                    "\n\n**Kolom HDY** (EPS_5Y, DPS_5Y, FCF_5Y, PR_5Y, DY_5Y, ICR, DebtEBITDA) "
                    "akan dihitung untuk profil ini."
                    if cfg["kolom_hdy"] else ""
                )
            )

        st.warning(
            "⏳ Proses enrichment bisa memakan waktu beberapa menit. "
            "Jangan tutup halaman ini."
        )

        if st.button(
            f"▶️ Mulai Enrichment {cfg['label']}",
            type="primary",
            key=f"btn_enrich_{profil}",
        ):
            progress_bar = st.progress(0, text="Memulai...")
            status_text  = st.empty()

            def on_progress(i: int, total: int, ticker: str) -> None:
                pct = int((i / total) * 100)
                progress_bar.progress(pct, text=f"Fetching ({i}/{total}): {ticker}")
                status_text.caption(f"Sedang memproses: `{ticker}`")

            try:
                df_result, total_before, total_after = enrich_and_filter(
                    df_input          = df_pre,
                    min_value_ma20    = min_value_ma20,
                    min_roe           = min_roe,
                    profil            = profil,
                    progress_callback = on_progress,
                )

                progress_bar.progress(100, text="Selesai!")
                status_text.empty()

                m1, m2, m3 = st.columns(3)
                m1.metric("Total Awal",   f"{total_before} saham")
                m2.metric("Lolos Filter", f"{total_after} saham")
                m3.metric("Dibuang",      f"{total_before - total_after} saham")

                # Preview hasil
                st.subheader(f"📊 Preview {cfg['file_name']}")
                df_display = df_result.copy()
                if "Value_MA20" in df_display.columns:
                    df_display["Value_MA20"] = df_display["Value_MA20"].apply(
                        lambda x: f"Rp {x:,.0f}" if pd.notna(x) else "-"
                    )
                for col in ["ROE", "ROA", "CAR", "NPL",
                            "Median_PER_3Y", "Median_PBV_3Y", "ICR", "DebtEBITDA"]:
                    if col in df_display.columns:
                        df_display[col] = df_display[col].apply(
                            lambda x: f"{x:.2f}" if pd.notna(x) else "-"
                        )
                for col in ["EPS_5Y", "DPS_5Y", "FCF_5Y", "PR_5Y", "DY_5Y"]:
                    if col in df_display.columns:
                        df_display[col] = df_display[col].apply(
                            lambda x: (str(x)[:40] + "…") if pd.notna(x) and x else "-"
                        )
                st.dataframe(df_display, use_container_width=True)

                st.session_state[state_key_result] = df_result
                st.session_state[state_key_done]   = True

            except ValueError as ve:
                st.error(f"❌ Error pada file CSV: {ve}")
            except Exception as e:
                st.error(f"❌ Terjadi kesalahan tidak terduga: {e}")

        # Tombol download — muncul jika enrichment sudah selesai
        if st.session_state.get(state_key_done, False):
            df_result = st.session_state[state_key_result]
            csv_bytes = df_result.to_csv(index=False).encode("utf-8")
            st.success(f"✅ Enrichment selesai — siap di-download.")
            st.download_button(
                label     = f"⬇️ Download {cfg['file_name']}",
                data      = csv_bytes,
                file_name = cfg["file_name"],
                mime      = "text/csv",
                type      = "primary",
                key       = f"dl_{profil}",
            )

        # Status file aktif di server
        st.divider()
        st.caption("**Status file saat ini di server:**")
        if os.path.exists(cfg["liquid_path"]):
            mtime = os.path.getmtime(cfg["liquid_path"])
            tgl   = datetime.datetime.fromtimestamp(mtime).strftime("%d %b %Y %H:%M")
            st.success(f"✅ `{cfg['file_name']}` ditemukan — terakhir diupdate: {tgl}")
            if st.button(
                "🔄 Clear cache (paksa baca ulang file terbaru)",
                key=f"clear_cache_{profil}",
            ):
                cfg["clear_cache"]()
                st.success("Cache dikosongkan. Data terbaru akan dimuat pada request berikutnya.")
        else:
            st.warning(
                f"⚠️ `{cfg['file_name']}` belum ada di folder `/data`. "
                f"Modul terkait akan fallback ke `pre_liquid_stocks.csv`."
            )


def render_admin_panel() -> None:
    st.header("⚙️ Panel Admin — Enrichment Data Saham")
    st.caption(
        "Proses ini membaca `pre_liquid_stocks.csv`, fetch data tiap saham, "
        "lalu menghasilkan dua file terpisah yang bisa kamu download dan upload ke GitHub."
    )

    # ── Step 1: Preview pre_liquid_stocks.csv ────────────────────────────────
    st.subheader("📋 Step 1 — Daftar Saham (pre_liquid_stocks.csv)")
    try:
        df_pre = pd.read_csv(PRE_LIQUID_PATH, sep=None, engine="python")
        st.dataframe(df_pre, use_container_width=True)
        st.caption(f"Total: {len(df_pre)} saham")
    except FileNotFoundError:
        st.error(
            "`data/pre_liquid_stocks.csv` tidak ditemukan. "
            "Pastikan file ada di folder `/data` di root repo."
        )
        return

    st.divider()

    # ── Step 2 & 3: Enrichment per profil ────────────────────────────────────
    st.subheader("🔧 Step 2 — Enrichment & Download")
    st.info(
        "Jalankan **kedua profil** agar modul Screening dan modul Dividen "
        "masing-masing punya universe yang sesuai. "
        "Urutan bebas — keduanya independen."
    )

    _render_enrichment_panel("trading", df_pre)
    _render_enrichment_panel("dividen", df_pre)

    st.divider()

    # ── Step 4: Instruksi Upload ke GitHub ────────────────────────────────────
    st.subheader("☁️ Step 3 — Upload ke GitHub")
    st.markdown("""
**Setelah download kedua file, ikuti langkah berikut:**

1. Buka repo GitHub kamu di browser
2. Masuk ke folder **`data/`**
3. Klik **"Add file"** → **"Upload files"**
4. Upload **kedua file** sekaligus:
   - `liquid_stocks.csv` ← universe Screening
   - `liquid_dividend_stocks.csv` ← universe Dividen
5. Klik **"Commit changes"** → Streamlit Cloud akan otomatis restart

> ⚠️ Pastikan nama file **tidak berubah** (huruf kecil semua) agar path di kode cocok.
> Tidak perlu upload ulang file yang tidak berubah sejak enrichment terakhir.
    """)


if __name__ == "__main__":
    st.set_page_config(page_title="Admin Panel", layout="wide")
    render_admin_panel()
