"""
analyze_layer_audit_screening.py
==================================
Gabungkan hasil beberapa batch backtest_layer_audit_screening.py, lalu untuk
TIAP indikator scoring Swing Trading screening.py (bukan skor total), hitung:
  1. Korelasi poin indikator vs forward return (Pearson & Spearman, + p-value
     kalau scipy tersedia)
  2. Efek praktis: rata-rata return saat indikator kasih poin positif vs
     nol/negatif
  3. Efek flag diagnostik (OBV_ok, CMF_ok, MTF_ok): rata-rata return saat
     True vs False — untuk cek apakah pre-filter/MTF gate di screening.py
     benar-benar menyaring ke arah yang benar, atau malah membuang sinyal
     yang justru profitable
  4. Ranking dari yang paling "menjelaskan" return sampai paling tidak
     berguna/merugikan

CARA PAKAI
----------
    python analyze_layer_audit_screening.py --input-dir outputs \
        --pattern "layer_audit_screening_*.csv"

Output: outputs/layer_audit_screening_analysis_<timestamp>/
    gabungan.csv
    ranking_indikator.csv
    efek_praktis.csv
    efek_flag_diagnostik.csv
    laporan.txt
"""

import argparse
import glob
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

try:
    from scipy import stats
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

_POIN_COLS = [
    "Supertrend_poin", "MAStructure_poin", "MACD_GC_poin", "MACD_Hist_poin",
    "RVOL_poin", "RSIMomentum_poin", "RSITrend_poin", "PSAR_poin",
    "VPT_poin", "MACDRecovery_poin", "RSIOB_penalty",
]
_RAW_COLS = ["RVOL_val", "RSI_val", "ATR_val"]
_FLAG_COLS = ["OBV_ok", "CMF_ok", "MTF_ok"]


def load_and_concat(input_dir: str, pattern: str) -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(input_dir, pattern)))
    if not files:
        print(f"❌ Tidak ada file cocok pola '{pattern}' di '{input_dir}'.")
        sys.exit(1)
    print(f"📂 {len(files)} file ditemukan:")
    dfs = []
    for f in files:
        d = pd.read_csv(f)
        d["_SourceFile"] = os.path.basename(f)
        dfs.append(d)
        print(f"   - {os.path.basename(f)}: {len(d)} baris, {d['Ticker'].nunique()} ticker")
    combined = pd.concat(dfs, ignore_index=True)

    if "NonOverlapping" in combined.columns and combined["NonOverlapping"].nunique() > 1:
        print("⚠️ Campuran mode overlapping/non-overlapping antar batch — pisahkan sebelum analisis.")
    return combined


def _corr_with_p(x: pd.Series, y: pd.Series) -> tuple:
    mask = x.notna() & y.notna()
    x, y = x[mask], y[mask]
    if len(x) < 5 or x.nunique() < 2:
        return np.nan, np.nan, np.nan, np.nan
    if _HAS_SCIPY:
        r, p = stats.pearsonr(x, y)
        rs, ps = stats.spearmanr(x, y)
    else:
        r = x.corr(y)
        rs = x.corr(y, method="spearman")
        p, ps = np.nan, np.nan
    return r, p, rs, ps


def ranking_indikator(df: pd.DataFrame, holding_days: list[int]) -> pd.DataFrame:
    rows = []
    all_cols = _POIN_COLS + _RAW_COLS + ["Skor"]
    for col in all_cols:
        if col not in df.columns:
            continue
        row = {"Indikator": col, "N_nonNaN": int(df[col].notna().sum())}
        for h in holding_days:
            ret_col = f"Return_{h}D_pct"
            if ret_col not in df.columns:
                continue
            r, p, rs, ps = _corr_with_p(df[col], df[ret_col])
            row[f"Pearson_{h}D"] = round(r, 3) if pd.notna(r) else np.nan
            row[f"p_{h}D"] = round(p, 3) if pd.notna(p) else np.nan
            row[f"Spearman_{h}D"] = round(rs, 3) if pd.notna(rs) else np.nan
        rows.append(row)

    out = pd.DataFrame(rows)
    sort_col = "Pearson_20D" if "Pearson_20D" in out.columns else None
    if sort_col:
        out["_abs"] = out[sort_col].abs()
        out = out.sort_values("_abs", ascending=False).drop(columns="_abs")
    return out.reset_index(drop=True)


def efek_praktis(df: pd.DataFrame, holding_days: list[int]) -> pd.DataFrame:
    """Untuk tiap indikator poin (diskrit/tier), bandingkan avg return saat
    poin > 0 vs poin == 0 vs poin < 0."""
    rows = []
    for col in _POIN_COLS:
        if col not in df.columns:
            continue
        for h in holding_days:
            ret_col = f"Return_{h}D_pct"
            if ret_col not in df.columns:
                continue
            pos = df.loc[df[col] > 0, ret_col]
            zero = df.loc[df[col] == 0, ret_col]
            neg = df.loc[df[col] < 0, ret_col]
            rows.append({
                "Indikator": col, "Horizon": f"{h}D",
                "N_Positif": len(pos), "AvgReturn_Positif": round(pos.mean(), 2) if len(pos) else np.nan,
                "N_Nol": len(zero), "AvgReturn_Nol": round(zero.mean(), 2) if len(zero) else np.nan,
                "N_Negatif": len(neg), "AvgReturn_Negatif": round(neg.mean(), 2) if len(neg) else np.nan,
                "Selisih_Positif_vs_Negatif": (
                    round(pos.mean() - neg.mean(), 2) if len(pos) and len(neg) else np.nan
                ),
                "Selisih_Positif_vs_Nol": (
                    round(pos.mean() - zero.mean(), 2) if len(pos) and len(zero) else np.nan
                ),
            })
    return pd.DataFrame(rows)


def efek_flag_diagnostik(df: pd.DataFrame, holding_days: list[int]) -> pd.DataFrame:
    """
    Untuk tiap flag pre-filter/MTF (OBV_ok, CMF_ok, MTF_ok): bandingkan avg
    return saat flag True (lolos, sesuai perilaku live app) vs False (di
    aplikasi live akan digugurkan/dibuang dari hasil).

    Cara baca: kalau AvgReturn_False > AvgReturn_True, filter tersebut
    justru MEMBUANG sinyal yang lebih profitable — kandidat untuk dilonggarkan
    atau dihapus.
    """
    rows = []
    for col in _FLAG_COLS:
        if col not in df.columns:
            continue
        for h in holding_days:
            ret_col = f"Return_{h}D_pct"
            if ret_col not in df.columns:
                continue
            true_vals = df.loc[df[col] == True, ret_col]
            false_vals = df.loc[df[col] == False, ret_col]
            rows.append({
                "Flag": col, "Horizon": f"{h}D",
                "N_True_Lolos": len(true_vals),
                "AvgReturn_True": round(true_vals.mean(), 2) if len(true_vals) else np.nan,
                "N_False_Gugur": len(false_vals),
                "AvgReturn_False": round(false_vals.mean(), 2) if len(false_vals) else np.nan,
                "Selisih_True_vs_False": (
                    round(true_vals.mean() - false_vals.mean(), 2)
                    if len(true_vals) and len(false_vals) else np.nan
                ),
            })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Gabung & analisis hasil backtest_layer_audit_screening.py")
    parser.add_argument("--input-dir", type=str, default="outputs")
    parser.add_argument("--pattern", type=str, default="layer_audit_screening_*.csv")
    parser.add_argument("--output-dir", type=str, default=None)
    args = parser.parse_args()

    if not _HAS_SCIPY:
        print("ℹ️ scipy tidak terpasang — p-value tidak dihitung (pip install scipy).")

    combined = load_and_concat(args.input_dir, args.pattern)
    holding_days = sorted(
        int(c.split("_")[1].replace("D", ""))
        for c in combined.columns if c.startswith("Return_") and c.endswith("D_pct")
    )
    print(f"\n📊 Total gabungan: {len(combined)} sinyal, {combined['Ticker'].nunique()} ticker")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.output_dir or os.path.join(args.input_dir, f"layer_audit_screening_analysis_{ts}")
    os.makedirs(out_dir, exist_ok=True)

    combined.to_csv(os.path.join(out_dir, "gabungan.csv"), index=False)

    df_rank = ranking_indikator(combined, holding_days)
    df_rank.to_csv(os.path.join(out_dir, "ranking_indikator.csv"), index=False)

    df_efek = efek_praktis(combined, holding_days)
    df_efek.to_csv(os.path.join(out_dir, "efek_praktis.csv"), index=False)

    df_flag = efek_flag_diagnostik(combined, holding_days)
    df_flag.to_csv(os.path.join(out_dir, "efek_flag_diagnostik.csv"), index=False)

    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)

    lines = []
    lines.append("=" * 90)
    lines.append("RANKING INDIKATOR SCORING SWING TRADING (screening.py) — |korelasi 20D| tertinggi")
    lines.append("=" * 90)
    lines.append(df_rank.to_string(index=False))
    lines.append("")
    lines.append("=" * 90)
    lines.append("EFEK PRAKTIS — avg return saat indikator kasih poin positif vs nol vs negatif")
    lines.append("=" * 90)
    lines.append(df_efek.to_string(index=False))
    lines.append("")
    lines.append("=" * 90)
    lines.append("EFEK FLAG DIAGNOSTIK — avg return saat lolos (True) vs digugurkan (False) di app live")
    lines.append("=" * 90)
    lines.append(df_flag.to_string(index=False))
    lines.append("")

    lines.append("CARA BACA:")
    lines.append(
        "  - Kolom Pearson_20D/p_20D: kalau p >= 0.05, jangan percaya angka korelasinya —\n"
        "    anggap indikator itu TIDAK terbukti berkorelasi dengan return.\n"
        "  - efek_praktis.csv, kolom 'Selisih_Positif_vs_Negatif': kecil/negatif berarti\n"
        "    indikator tidak membantu atau menyesatkan — kandidat diturunkan bobot/dibuang.\n"
        "  - efek_flag_diagnostik.csv, kolom 'Selisih_True_vs_False': kalau NEGATIF, filter\n"
        "    tersebut (OBV/CMF/MTF) justru membuang sinyal yang return-nya lebih baik dari\n"
        "    yang diloloskan — pertimbangkan melonggarkan threshold-nya.\n"
        "  - Ingat keterbatasan: Sector Hot bonus dan filter eligibility (Value_MA20,\n"
        "    MarketCap, ROE/ROA) TIDAK tercermin di sini sama sekali."
    )

    report = "\n".join(lines)
    with open(os.path.join(out_dir, "laporan.txt"), "w", encoding="utf-8") as f:
        f.write(report)

    print("\n" + report)
    print(f"\n📁 Hasil tersimpan di: {out_dir}/")


if __name__ == "__main__":
    main()
