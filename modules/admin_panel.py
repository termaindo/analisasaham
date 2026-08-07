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

import concurrent.futures
import datetime
import os
import time

import pandas as pd
import streamlit as st

from utils.data_loader import (
    LIQUID_PATH,
    LIQUID_DIVIDEND_PATH,
    PRE_LIQUID_PATH,
    clear_liquid_stocks_cache,
    clear_liquid_dividend_stocks_cache,
    enrich_and_filter,
    get_liquid_stocks,
)

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


def _render_backtest_panel() -> None:
    """
    Panel Backtest & Kalibrasi Skor Teknikal — jalankan walk-forward backtest
    dari compute_score() di modules/teknikal.py langsung dari admin panel,
    tanpa perlu buka terminal lokal.

    CATATAN PENTING: ini operasi berat (fetch histori bertahun-tahun untuk
    banyak saham via yfinance). Untuk kalibrasi penuh (semua saham universe,
    histori panjang), lebih aman dijalankan via CLI lokal
    (`python backtest_teknikal.py --from-liquid --years 5`) karena Streamlit
    Cloud punya keterbatasan resource/timeout dan risiko rate-limit Yahoo
    lebih tinggi saat banyak request beruntun dalam satu proses. Panel ini
    dirancang untuk cek cepat / iterasi kalibrasi skala kecil-menengah.

    Sesuai STANDAR_KODING.md, tidak ada file yang ditulis ke disk di sini —
    hasil disimpan di st.session_state dan diunduh via st.download_button,
    karena filesystem Streamlit Cloud bersifat sementara (reset saat restart).
    """
    st.subheader("🧪 Backtest & Kalibrasi Skor Teknikal")
    st.caption(
        "Menjalankan walk-forward backtest atas `compute_score()` di "
        "`modules/teknikal.py` untuk mengecek apakah threshold skor "
        "(65/35/10/-9/-34/-64) benar-benar berkorelasi dengan win rate historis."
    )

    try:
        import backtest_teknikal as bt
    except ImportError as e:
        st.error(
            f"❌ Tidak bisa memuat `backtest_teknikal.py`. Pastikan file ada di "
            f"root repo (sejajar `app.py`).\n\nDetail: {e}"
        )
        return

    st.warning(
        "⚠️ **Operasi ini berat** — mengambil histori bertahun-tahun untuk banyak "
        "saham sekaligus lewat yfinance. Bisa lambat, kena rate-limit Yahoo, atau "
        "timeout di Streamlit Cloud. Untuk kalibrasi **penuh** (semua saham, 5 tahun), "
        "jalankan `python backtest_teknikal.py --from-liquid --years 5` dari terminal "
        "lokal. Gunakan panel ini untuk cek cepat atau iterasi kalibrasi skala kecil."
    )

    col1, col2 = st.columns(2)
    with col1:
        sumber = st.radio(
            "Sumber ticker",
            ["Manual (aman, cepat)", "Semua dari liquid_stocks.csv (berat)"],
            key="bt_sumber",
        )
        tickers_input = None
        if sumber.startswith("Manual"):
            tickers_input = st.text_input(
                "Daftar ticker (pisah koma)",
                value="BBCA,BBRI,TLKM,ASII,UNVR",
                key="bt_tickers_input",
            )
    with col2:
        years = st.number_input(
            "Tahun histori", min_value=1, max_value=10, value=3, key="bt_years",
            help="Semakin panjang, semakin banyak sample tapi semakin lama & berat.",
        )
        holding_days_str = st.text_input(
            "Holding period (hari bursa, pisah koma)", value="5,10,20", key="bt_holding",
        )

    col3, col4, col5 = st.columns(3)
    with col3:
        min_warmup = st.number_input(
            "Min warmup (bar)", min_value=60, max_value=400, value=250, key="bt_warmup",
            help="Minimum bar sebelum mulai sampling, agar EMA200/ADX stabil.",
        )
    with col4:
        sample_every = st.number_input(
            "Sample tiap N hari", min_value=1, max_value=10, value=3, key="bt_sample",
            help="Naikkan untuk mempercepat run (mengorbankan jumlah sample).",
        )
    with col5:
        max_workers = st.number_input(
            "Thread paralel", min_value=1, max_value=10, value=5, key="bt_workers",
        )

    if st.button("▶️ Jalankan Backtest", type="primary", key="btn_run_backtest"):
        if sumber.startswith("Manual"):
            tickers = [
                (t.strip().upper().replace(".JK", "") + ".JK")
                for t in (tickers_input or "").split(",") if t.strip()
            ]
        else:
            df_liquid = get_liquid_stocks()
            if df_liquid.empty:
                st.error("`liquid_stocks.csv` kosong/tidak ditemukan.")
                return
            col_t = "Ticker" if "Ticker" in df_liquid.columns else df_liquid.columns[0]
            tickers = [
                (t if t.endswith(".JK") else t + ".JK")
                for t in df_liquid[col_t].astype(str).str.strip().tolist()
            ]

        if not tickers:
            st.error("Tidak ada ticker untuk diproses.")
            return

        try:
            holding_days = sorted(
                int(x.strip()) for x in holding_days_str.split(",") if x.strip()
            )
        except ValueError:
            st.error("Format holding period tidak valid. Contoh yang benar: 5,10,20")
            return

        progress_bar = st.progress(0, text="Memulai backtest...")
        status_text  = st.empty()
        all_rows: list[dict] = []
        gagal: list[str] = []
        total = len(tickers)

        t0 = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=int(max_workers)) as executor:
            futures = {
                executor.submit(
                    bt.walk_forward_single, t, int(years), holding_days,
                    int(min_warmup), int(sample_every),
                ): t
                for t in tickers
            }
            done = 0
            for future in concurrent.futures.as_completed(futures):
                t = futures[future]
                done += 1
                progress_bar.progress(done / total, text=f"Memproses ({done}/{total}): {t}")
                try:
                    rows = future.result()
                    if rows:
                        all_rows.extend(rows)
                        status_text.caption(f"✅ {t}: {len(rows)} titik sinyal")
                    else:
                        gagal.append(t)
                        status_text.caption(f"⚠️ {t}: data tidak cukup, dilewati")
                except Exception as e:
                    gagal.append(t)
                    status_text.caption(f"❌ {t}: error — {e}")

        elapsed = time.time() - t0
        progress_bar.progress(1.0, text="Selesai!")
        status_text.empty()

        if not all_rows:
            st.error("Tidak ada titik sinyal yang berhasil dihitung. Cek ticker/parameter.")
            return

        df_sinyal = pd.DataFrame(all_rows)
        df_label  = bt.summarize(df_sinyal, holding_days, "Label", bt._LABEL_ORDER)
        df_decile = bt.summarize(df_sinyal, holding_days, "Decile", None)

        st.session_state["backtest_detail"] = df_sinyal
        st.session_state["backtest_label"]  = df_label
        st.session_state["backtest_decile"] = df_decile
        st.session_state["backtest_done"]   = True
        st.session_state["backtest_meta"]   = {
            "elapsed": elapsed, "total": total, "gagal": gagal, "n_sinyal": len(all_rows),
        }

    # ── Tampilkan hasil dari session_state (survive re-run saat download) ──
    if st.session_state.get("backtest_done", False):
        meta = st.session_state["backtest_meta"]
        st.success(
            f"✅ Selesai dalam {meta['elapsed']:.0f} detik | "
            f"{meta['n_sinyal']} titik sinyal dari {meta['total']} ticker "
            f"({len(meta['gagal'])} dilewati/gagal)"
        )
        if meta["gagal"]:
            st.caption(
                f"Dilewati: {', '.join(meta['gagal'][:15])}"
                f"{' ...' if len(meta['gagal']) > 15 else ''}"
            )

        st.markdown("**Ringkasan per Label (threshold saat ini)**")
        st.dataframe(st.session_state["backtest_label"], use_container_width=True, hide_index=True)

        st.markdown("**Ringkasan per Decile Skor**")
        st.dataframe(st.session_state["backtest_decile"], use_container_width=True, hide_index=True)

        st.caption(
            "💡 Cek kolom WinRate_*D_%: kalau bucket 'BELI (35-64)' win rate-nya "
            "di bawah 50%, threshold 35 kemungkinan terlalu longgar. Kalau bucket "
            "'MASUK PANTAUAN (10-34)' win rate-nya sudah setara/lebih baik dari "
            "'BELI', threshold BELI mungkin terlalu ketat."
        )

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dl1, dl2, dl3 = st.columns(3)
        with dl1:
            st.download_button(
                "⬇️ Detail Sinyal (CSV)",
                data=st.session_state["backtest_detail"].to_csv(index=False).encode("utf-8"),
                file_name=f"backtest_sinyal_{ts}.csv", mime="text/csv", key="dl_bt_detail",
            )
        with dl2:
            st.download_button(
                "⬇️ Ringkasan Label (CSV)",
                data=st.session_state["backtest_label"].to_csv(index=False).encode("utf-8"),
                file_name=f"backtest_ringkasan_label_{ts}.csv", mime="text/csv", key="dl_bt_label",
            )
        with dl3:
            st.download_button(
                "⬇️ Ringkasan Decile (CSV)",
                data=st.session_state["backtest_decile"].to_csv(index=False).encode("utf-8"),
                file_name=f"backtest_ringkasan_decile_{ts}.csv", mime="text/csv", key="dl_bt_decile",
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

    # ── Backtest & Kalibrasi Skor Teknikal (opsional, sejajar dgn enrichment) ─
    _render_backtest_panel()

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
