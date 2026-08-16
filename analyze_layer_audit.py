"""
analyze_layer_audit.py
========================
Gabungkan hasil beberapa batch backtest_layer_audit.py, lalu untuk TIAP
indikator individual (bukan skor total), hitung:
  1. Korelasi poin indikator vs forward return (Pearson & Spearman, + p-value
     kalau scipy tersedia)
  2. Efek praktis: rata-rata return saat indikator kasih poin positif vs
     nol/negatif (lebih mudah dibaca daripada korelasi untuk indikator
     bertingkat/diskrit)
  3. Ranking indikator dari yang paling "menjelaskan" return sampai yang
     paling tidak berguna/merugikan

CARA PAKAI
----------
    python analyze_layer_audit.py --input-dir outputs --pattern "layer_audit_*.csv"

Output: outputs/layer_audit_analysis_<timestamp>/
    gabungan.csv                 -> semua batch digabung
    ranking_indikator.csv        -> ranking korelasi per indikator per horizon
    efek_praktis.csv             -> avg return per kondisi poin (positif/nol/negatif)
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
    "EMA_Stack_poin", "Supertrend_poin", "BB_Mid_poin", "SAR_poin",
    "MACD_poin", "RSI_poin", "Stochastic_poin",
    "VolSpike_poin", "Fibonacci_poin", "BollingerBands_poin", "Candlestick_poin",
]
_RAW_COLS = ["ADX_val", "VolRatio_val", "RSI_val", "MACD_Hist_val", "ATR_pct_val"]


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
            row[f"p_{h}D"]       = round(p, 3) if pd.notna(p) else np.nan
            row[f"Spearman_{h}D"] = round(rs, 3) if pd.notna(rs) else np.nan
        rows.append(row)

    out = pd.DataFrame(rows)
    if "Pearson_20D" in out.columns:
        out["_abs20D"] = out["Pearson_20D"].abs()
        out = out.sort_values("_abs20D", ascending=False).drop(columns="_abs20D")
    return out.reset_index(drop=True)


def efek_praktis(df: pd.DataFrame, holding_days: list[int]) -> pd.DataFrame:
    """Untuk tiap indikator poin (diskrit/tier), bandingkan avg return saat
    poin > 0 vs poin == 0 vs poin < 0. Effect size yang lebih mudah dibaca
    daripada korelasi untuk indikator bertingkat."""
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
            })
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description="Gabung & analisis hasil backtest_layer_audit.py")
    parser.add_argument("--input-dir", type=str, default="outputs")
    parser.add_argument("--pattern", type=str, default="layer_audit_*.csv")
    parser.add_argument("--output-dir", type=str, default=None)
    args = parser.parse_args()

    if not _HAS_SCIPY:
        print("ℹ️ scipy tidak terpasang — p-value tidak dihitung (pip install scipy untuk uji signifikansi).")

    combined = load_and_concat(args.input_dir, args.pattern)
    holding_days = sorted(
        int(c.split("_")[1].replace("D", ""))
        for c in combined.columns if c.startswith("Return_") and c.endswith("D_pct")
    )
    print(f"\n📊 Total gabungan: {len(combined)} sinyal, {combined['Ticker'].nunique()} ticker")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.output_dir or os.path.join(args.input_dir, f"layer_audit_analysis_{ts}")
    os.makedirs(out_dir, exist_ok=True)

    combined.to_csv(os.path.join(out_dir, "gabungan.csv"), index=False)

    df_rank = ranking_indikator(combined, holding_days)
    df_rank.to_csv(os.path.join(out_dir, "ranking_indikator.csv"), index=False)

    df_efek = efek_praktis(combined, holding_days)
    df_efek.to_csv(os.path.join(out_dir, "efek_praktis.csv"), index=False)

    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)

    lines = []
    lines.append("=" * 90)
    lines.append("RANKING INDIKATOR — diurutkan dari |korelasi 20D| tertinggi")
    lines.append("=" * 90)
    lines.append(df_rank.to_string(index=False))
    lines.append("")
    lines.append("=" * 90)
    lines.append("EFEK PRAKTIS — avg return saat indikator kasih poin positif vs nol vs negatif")
    lines.append("=" * 90)
    lines.append(df_efek.to_string(index=False))
    lines.append("")

    lines.append("CARA BACA:")
    lines.append(
        "  - Kolom Pearson_20D/p_20D: kalau p >= 0.05, jangan percaya angka korelasinya —\n"
        "    anggap indikator itu TIDAK terbukti berkorelasi dengan return.\n"
        "  - Kolom 'Selisih_Positif_vs_Negatif' di efek_praktis.csv: kalau angkanya kecil\n"
        "    (mendekati 0) atau NEGATIF, indikator itu tidak membantu atau malah\n"
        "    menyesatkan — kandidat kuat untuk diturunkan bobotnya atau dibuang.\n"
        "  - Indikator dengan Selisih besar & positif & p<0.05 di >=2 horizon adalah\n"
        "    kandidat kuat untuk DINAIKKAN bobotnya di compute_score()."
    )

    report = "\n".join(lines)
    with open(os.path.join(out_dir, "laporan.txt"), "w", encoding="utf-8") as f:
        f.write(report)

    print("\n" + report)
    print(f"\n📁 Hasil tersimpan di: {out_dir}/")


if __name__ == "__main__":
    main()
