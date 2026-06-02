"""
dividen.py — Analisa Dividen Pro
Modul analisa dividen dengan scoring HDY 100 poin, klasifikasi gabungan,
proyeksi forward yield, dan export PDF.
"""

import json
import os
import base64
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF

from utils.data_loader import (
    get_full_stock_data,
    get_liquid_dividend_stocks,
    is_ticker_liquid,
    get_ticker_row,
    PRE_LIQUID_PATH,
)

# ─────────────────────────────────────────────────────────────────────────────
# KONSTANTA
# ─────────────────────────────────────────────────────────────────────────────

YIELD_TARGET        = 0.10   # 10% — target minimum dividend investing
YIELD_ANOMALY       = 0.15   # 15% — threshold warning yield terlalu tinggi
PAYOUT_RATIO_MAX    = 0.90   # 90% — batas atas payout ratio aman
DER_MAX_GENERAL     = 3.0    # batas knockout DER sektor umum
CAR_MIN_BANK        = 8.0    # batas knockout CAR sektor Bank (%)
NPL_MAX_BANK        = 5.0    # batas knockout NPL sektor Bank (%)
DEBT_EBITDA_MAX_INF = 5.0    # batas knockout Debt/EBITDA sektor Infrastruktur

SEKTOR_BANK   = {"Bank", "Finansial", "Keuangan", "Perbankan"}
SEKTOR_INFRA  = {"Infrastruktur", "Utilitas"}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — DATA
# ─────────────────────────────────────────────────────────────────────────────

def _safe_latin1(text: str) -> str:
    """Transliterasi karakter non-latin1 agar aman untuk FPDF."""
    _MAP = {
        "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2022": "*", "\u2026": "...",
        "\u00e9": "e", "\u00e8": "e", "\u00ea": "e", "\u00e0": "a",
        "\u00e2": "a", "\u00f4": "o", "\u00fb": "u", "\u00ee": "i",
        "\u00e7": "c", "\u00fc": "u", "\u00f6": "o", "\u00e4": "a",
    }
    if not isinstance(text, str):
        text = str(text)
    result = []
    for ch in text:
        if ch in _MAP:
            result.append(_MAP[ch])
        else:
            try:
                ch.encode("latin-1")
                result.append(ch)
            except UnicodeEncodeError:
                result.append("?")
    return "".join(result)


def _parse_json_col(val) -> list:
    """Parse kolom JSON array dari liquid_stocks.csv; kembalikan list atau []."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return []
    if isinstance(val, list):
        return val
    try:
        parsed = json.loads(str(val))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _get_identitas(ticker_bersih: str, liquid_df: pd.DataFrame) -> dict:
    """Ambil Sektor dan Syariah via fallback chain: liquid → pre_liquid → default."""
    result = {"sektor": "Tidak Diketahui", "syariah": "Tidak Diketahui"}

    if is_ticker_liquid(ticker_bersih, liquid_df):
        row = get_ticker_row(ticker_bersih, liquid_df)
        if row is not None:
            result["sektor"]  = str(row.get("Sektor", "Tidak Diketahui"))
            result["syariah"] = str(row.get("Syariah", "Tidak Diketahui"))
            return result

    try:
        df_pre  = pd.read_csv(PRE_LIQUID_PATH)
        row_pre = get_ticker_row(ticker_bersih, df_pre)
        if row_pre is not None:
            result["sektor"]  = str(row_pre.get("Sektor", "Tidak Diketahui"))
            result["syariah"] = str(row_pre.get("Syariah", "Tidak Diketahui"))
    except Exception:
        pass

    return result


def _build_hdy_arrays_from_liquid(ticker_row: dict) -> dict:
    """
    Ambil array HDY dari liquid_stocks.csv (sudah di-enrich admin).
    Kembalikan dict dengan key: eps_5y, dps_5y, fcf_5y, pr_5y, dy_5y, icr, debt_ebitda.
    """
    return {
        "eps_5y":       _parse_json_col(ticker_row.get("EPS_5Y")),
        "dps_5y":       _parse_json_col(ticker_row.get("DPS_5Y")),
        "fcf_5y":       _parse_json_col(ticker_row.get("FCF_5Y")),
        "pr_5y":        _parse_json_col(ticker_row.get("PR_5Y")),
        "dy_5y":        _parse_json_col(ticker_row.get("DY_5Y")),
        "icr":          ticker_row.get("ICR"),
        "debt_ebitda":  ticker_row.get("DebtEBITDA"),
    }


def _build_hdy_arrays_from_yfinance(stock_data: dict, curr_price: float,
                                    divs: pd.Series) -> dict:
    """
    Fallback: bangun array HDY 5 tahun dari yfinance financials & cashflow.
    Akurasi tidak dijamin untuk semua ticker IDX.
    """
    info      = stock_data.get("info", {})
    fin       = stock_data.get("financials", pd.DataFrame())   # income stmt, kolom = tahun
    cashflow  = stock_data.get("cashflow", pd.DataFrame())

    def _tail5_annual(df: pd.DataFrame, row_key: str) -> list:
        """Ambil 5 nilai terakhir dari baris tertentu di DataFrame finansial yfinance."""
        if df is None or df.empty or row_key not in df.index:
            return [None] * 5
        series = df.loc[row_key].sort_index(ascending=True)
        vals   = list(series.values[-5:])
        # pad kiri dengan None bila < 5
        while len(vals) < 5:
            vals.insert(0, None)
        return [None if (v is None or (isinstance(v, float) and np.isnan(v)))
                else float(v) for v in vals]

    # EPS: Net Income / Shares Outstanding (per tahun)
    net_income_arr = _tail5_annual(fin, "Net Income")
    shares         = info.get("sharesOutstanding") or 0
    eps_5y = [
        round(ni / shares, 4) if (ni is not None and shares > 0) else None
        for ni in net_income_arr
    ]

    # FCF: dari cashflow statement
    fcf_5y = _tail5_annual(cashflow, "Free Cash Flow")
    if all(v is None for v in fcf_5y):
        # fallback ke Operating CF - CapEx
        ocf  = _tail5_annual(cashflow, "Operating Cash Flow")
        capx = _tail5_annual(cashflow, "Capital Expenditure")
        fcf_5y = [
            (o + c) if (o is not None and c is not None) else None
            for o, c in zip(ocf, capx)
        ]

    # DPS: dari dividen historis, agregasi per tahun kalender
    dps_5y = [None] * 5
    if divs is not None and len(divs) > 0:
        df_d         = divs.to_frame(name="DPS")
        df_d.index   = pd.to_datetime(df_d.index).tz_localize(None)
        df_d["year"] = df_d.index.year
        annual_dps   = df_d.groupby("year")["DPS"].sum().sort_index()
        last5        = annual_dps.tail(5).values
        while len(last5) < 5:
            last5 = np.insert(last5, 0, np.nan)
        dps_5y = [None if np.isnan(v) else float(v) for v in last5]

    # PR: DPS / EPS per tahun
    pr_5y = []
    for d, e in zip(dps_5y, eps_5y):
        if d is not None and e is not None and e > 0:
            pr_5y.append(round(d / e, 4))
        else:
            pr_5y.append(None)

    # DY: DPS / harga penutupan akhir tahun (simplifikasi: pakai harga sekarang untuk semua)
    # Ini adalah fallback kasar — liquid_stocks lebih akurat
    dy_5y = [
        round(d / curr_price, 4) if (d is not None and curr_price > 0) else None
        for d in dps_5y
    ]

    # ICR: EBIT / Interest Expense (TTM dari info)
    ebit       = info.get("ebit")
    int_exp    = info.get("interestExpense")
    icr = None
    if ebit is not None and int_exp is not None and int_exp != 0:
        icr = round(abs(ebit / int_exp), 2)

    return {
        "eps_5y":      eps_5y,
        "dps_5y":      dps_5y,
        "fcf_5y":      fcf_5y,
        "pr_5y":       pr_5y,
        "dy_5y":       dy_5y,
        "icr":         icr,
        "debt_ebitda": None,   # tidak tersedia dari yfinance untuk semua sektor
    }


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — HISTORI DIVIDEN (Bagian 1)
# ─────────────────────────────────────────────────────────────────────────────

def _hitung_konsistensi_berturut(divs: pd.Series) -> int:
    """Hitung jumlah tahun berturut-turut membagi dividen (dihitung mundur dari tahun ini)."""
    if divs is None or len(divs) == 0:
        return 0
    df_d         = divs.to_frame(name="DPS")
    df_d.index   = pd.to_datetime(df_d.index).tz_localize(None)
    df_d["year"] = df_d.index.year
    annual       = df_d.groupby("year")["DPS"].sum()
    tahun_div    = set(annual[annual > 0].index)
    tahun_ini    = datetime.now().year
    count        = 0
    for y in range(tahun_ini - 1, tahun_ini - 20, -1):
        if y in tahun_div:
            count += 1
        else:
            break
    return count


def _hitung_dy_avg(divs: pd.Series, history: pd.DataFrame,
                   n_tahun: int = 5) -> float | None:
    """
    Hitung rata-rata dividend yield selama n_tahun tahun terakhir.
    Yield per tahun = total DPS tahun itu / harga penutupan akhir tahun itu.
    """
    if divs is None or len(divs) == 0 or history is None or history.empty:
        return None
    try:
        df_d         = divs.to_frame(name="DPS")
        df_d.index   = pd.to_datetime(df_d.index).tz_localize(None)
        df_d["year"] = df_d.index.year
        annual_dps   = df_d.groupby("year")["DPS"].sum()

        hist = history.copy()
        hist.index = pd.to_datetime(hist.index).tz_localize(None)
        hist["year"] = hist.index.year
        annual_close = hist.groupby("year")["Close"].last()

        yields = []
        for y in annual_dps.index[-n_tahun:]:
            if y in annual_close.index and annual_close[y] > 0:
                yields.append(annual_dps[y] / annual_close[y])
        return float(np.mean(yields)) if yields else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SCORING HDY — HARD KNOCKOUT
# ─────────────────────────────────────────────────────────────────────────────

def _check_hard_knockout(arrays: dict, info: dict, sektor: str,
                         ticker_row, liquid_df_row) -> list[str]:
    """
    Periksa semua kondisi hard knockout.
    Kembalikan list alasan; list kosong = lolos semua knockout.
    """
    alasan = []
    fcf_5y = arrays["fcf_5y"]
    pr_5y  = arrays["pr_5y"]
    dps_5y = arrays["dps_5y"]

    # FCF negatif ≥ 2 tahun berturut-turut
    if fcf_5y:
        fcf_valid = [v for v in fcf_5y if v is not None]
        if len(fcf_valid) >= 2:
            negatif_berturut = 0
            for v in reversed(fcf_valid):
                if v < 0:
                    negatif_berturut += 1
                else:
                    break
            if negatif_berturut >= 2:
                alasan.append("FCF negatif ≥ 2 tahun berturut-turut (dividen dibayar dari utang/cadangan)")

    # Payout Ratio > 100% dalam 2 tahun terakhir
    if pr_5y:
        pr_valid = [v for v in pr_5y if v is not None]
        pr_2_terakhir = [v for v in pr_valid[-2:] if v is not None]
        if len(pr_2_terakhir) >= 2 and all(v > 1.0 for v in pr_2_terakhir):
            alasan.append("Payout Ratio > 100% dalam 2 tahun terakhir (membayar melebihi yang diperoleh)")

    # Frekuensi dividen < 3x dalam 5 tahun
    if dps_5y:
        frekuensi = sum(1 for v in dps_5y if v is not None and v > 0)
        if frekuensi < 3:
            alasan.append(f"Frekuensi dividen hanya {frekuensi}x dalam 5 tahun (minimum 3x)")

    sektor_upper = sektor.strip().title()

    if sektor_upper in SEKTOR_BANK:
        # CAR < 8%
        car = None
        if liquid_df_row is not None:
            car = liquid_df_row.get("CAR")
        if car is not None and not (isinstance(car, float) and np.isnan(car)):
            if float(car) < CAR_MIN_BANK:
                alasan.append(f"CAR {car:.1f}% di bawah minimum OJK 8%")
        # NPL > 5%
        npl = None
        if liquid_df_row is not None:
            npl = liquid_df_row.get("NPL")
        if npl is not None and not (isinstance(npl, float) and np.isnan(npl)):
            if float(npl) > NPL_MAX_BANK:
                alasan.append(f"NPL {npl:.1f}% melampaui batas kritis 5%")

    elif sektor_upper in SEKTOR_INFRA:
        # Debt/EBITDA > 5x
        de = arrays.get("debt_ebitda")
        if de is not None and not (isinstance(de, float) and np.isnan(de)):
            if float(de) > DEBT_EBITDA_MAX_INF:
                alasan.append(f"Debt/EBITDA {de:.1f}x melampaui batas aman 5x")

    else:
        # DER > 3.0 sektor umum
        der_raw = info.get("debtToEquity")
        if der_raw is not None:
            der = float(der_raw) / 100.0
            if der > DER_MAX_GENERAL:
                alasan.append(f"DER {der:.2f}x melampaui batas ekstrem 3.0x")

    return alasan


# ─────────────────────────────────────────────────────────────────────────────
# SCORING HDY — DIMENSI A, B, C, D
# ─────────────────────────────────────────────────────────────────────────────

def _score_dimensi_a(arrays: dict) -> tuple[int, dict]:
    """Dimensi A — Keberlanjutan Earnings & FCF · maks 45 poin."""
    eps_5y = arrays["eps_5y"]
    fcf_5y = arrays["fcf_5y"]
    dps_5y = arrays["dps_5y"]
    detail = {}
    total  = 0

    # ── Indikator #3: EPS Predictability R² · 15 poin ──────────────────────
    eps_positif = [(i, v) for i, v in enumerate(eps_5y)
                   if v is not None and v > 0]
    if len(eps_positif) >= 3:
        x   = np.array([i for i, _ in eps_positif], dtype=float)
        y   = np.array([v for _, v in eps_positif], dtype=float)
        try:
            coeffs   = np.polyfit(x, np.log(y), 1)
            y_hat    = np.polyval(coeffs, x)
            corr     = np.corrcoef(np.log(y), y_hat)[0, 1]
            r2       = corr ** 2
            poin_r2  = 15 if r2 >= 0.80 else 10 if r2 >= 0.60 else 5 if r2 >= 0.40 else 0
            detail["r2"]      = round(r2 * 100, 1)
            detail["poin_r2"] = poin_r2
            total += poin_r2
        except Exception:
            detail["r2"]      = None
            detail["poin_r2"] = 0
    else:
        detail["r2"]      = None
        detail["poin_r2"] = 0
        detail["r2_note"] = "Data tidak cukup (< 3 titik EPS positif)"

    # ── Indikator #1: AAGR EPS · 12 poin ───────────────────────────────────
    eps_valid = [v for v in eps_5y if v is not None]
    aagr      = None
    if len(eps_valid) >= 2:
        growths = []
        for i in range(1, len(eps_valid)):
            prev = eps_valid[i - 1]
            curr = eps_valid[i]
            if prev is not None and prev > 0 and curr is not None:
                growths.append((curr - prev) / prev)
        if growths:
            aagr = float(np.mean(growths)) * 100

    if aagr is not None:
        poin_aagr = (12 if aagr >= 10 else 9 if aagr >= 7 else
                     6  if aagr >= 5  else 3 if aagr >= 2 else 0)
    else:
        poin_aagr = 0
    detail["aagr_eps"]  = round(aagr, 2) if aagr is not None else None
    detail["poin_aagr"] = poin_aagr
    total += poin_aagr

    # ── Indikator #9: Riwayat FCF Positif · 10 poin ────────────────────────
    fcf_valid   = [v for v in fcf_5y if v is not None]
    fcf_positif = sum(1 for v in fcf_valid if v > 0)
    n_fcf       = len(fcf_valid)
    if n_fcf == 0:
        poin_fcf = 0
    elif fcf_positif == 5:
        poin_fcf = 10
    elif fcf_positif == 4:
        poin_fcf = 8
    elif fcf_positif == 3:
        poin_fcf = 4
    else:
        poin_fcf = 0
    detail["fcf_positif_tahun"] = fcf_positif
    detail["poin_fcf"]          = poin_fcf
    total += poin_fcf

    # ── Indikator T1: FCF Payout Ratio · 5 poin ────────────────────────────
    # Gunakan total dividen historis / FCF per tahun (alternatif kedua dari spec)
    fcf_pr_ratios = []
    for dps_val, fcf_val in zip(dps_5y, fcf_5y):
        if (dps_val is not None and fcf_val is not None
                and fcf_val > 0 and dps_val > 0):
            # dps_val dalam rupiah per saham; gunakan sebagai proksi
            # rasio relatif — FCF per saham tidak tersedia langsung,
            # sehingga kita gunakan DPS/FCF_per_saham jika shares ada,
            # atau skip jika tidak. Spec: pakai total dividen / FCF.
            # Karena total_div = DPS * shares dan FCF sudah dalam rupiah total,
            # rasio ini baru valid jika kita tahu shares.
            # Pendekatan: simpan DPS/FCF sebagai proxy kardinalitas relatif;
            # beri catatan di UI bahwa ini perkiraan.
            fcf_pr_ratios.append(dps_val / fcf_val)   # proxy: DPS per rupiah FCF

    # Normalisasi: jika median proxy < 0.006 → anggap ≤60%; dst.
    # Karena skala tidak sama persis, gunakan PR_5Y sebagai basis jika tersedia
    pr_valid = [v for v in arrays["pr_5y"] if v is not None]
    if pr_valid and fcf_valid:
        pr_avg    = float(np.mean(pr_valid))
        fcf_pr    = pr_avg   # gunakan PR_5Y × (EPS/FCF per saham) idealnya,
        # tapi tanpa shares kita gunakan PR saja sebagai proxy FCF_PR
        poin_fcf_pr = (5 if fcf_pr <= 0.60 else 3 if fcf_pr <= 0.80 else 0)
    else:
        fcf_pr      = None
        poin_fcf_pr = 0
    detail["fcf_pr"]      = round(fcf_pr * 100, 1) if fcf_pr is not None else None
    detail["poin_fcf_pr"] = poin_fcf_pr
    total += poin_fcf_pr

    # ── Indikator #2: Konsistensi Pertumbuhan EPS · 3 poin ─────────────────
    eps_tumbuh = 0
    if len(eps_valid) >= 2:
        for i in range(1, len(eps_valid)):
            if (eps_valid[i] is not None and eps_valid[i - 1] is not None
                    and eps_valid[i] > eps_valid[i - 1]):
                eps_tumbuh += 1
    poin_eps_tumbuh = (3 if eps_tumbuh >= 4 else 1 if eps_tumbuh == 3 else 0)
    detail["eps_tumbuh_tahun"]  = eps_tumbuh
    detail["poin_eps_tumbuh"]   = poin_eps_tumbuh
    total += poin_eps_tumbuh

    return total, detail


def _score_dimensi_b(arrays: dict, curr_dy: float | None) -> tuple[int, dict]:
    """Dimensi B — Track Record Distribusi Dividen · maks 35 poin."""
    dy_5y  = arrays["dy_5y"]
    pr_5y  = arrays["pr_5y"]
    dps_5y = arrays["dps_5y"]
    detail = {}
    total  = 0

    # ── Indikator #5: Rata-rata DY 5 tahun · 12 poin ───────────────────────
    dy_valid = [v for v in dy_5y if v is not None]
    dy_avg   = float(np.mean(dy_valid)) * 100 if dy_valid else None
    if dy_avg is not None:
        poin_dy = (12 if dy_avg >= 8 else 9 if dy_avg >= 6 else
                   6  if dy_avg >= 4 else 3 if dy_avg >= 2 else 0)
    else:
        poin_dy = 0
    detail["dy_avg"]    = round(dy_avg, 2) if dy_avg is not None else None
    detail["poin_dy"]   = poin_dy
    total += poin_dy

    # Yield Anomaly Warning
    anomali_yield = False
    if dy_avg is not None and curr_dy is not None and dy_avg > 0:
        if (curr_dy * 100) > 1.5 * dy_avg:
            anomali_yield = True
    detail["anomali_yield"] = anomali_yield

    # ── Indikator #7: Rata-rata Payout Ratio · 10 poin ─────────────────────
    pr_valid = [v for v in pr_5y if v is not None]
    pr_avg   = float(np.mean(pr_valid)) * 100 if pr_valid else None
    if pr_avg is not None:
        poin_pr = (10 if 30 <= pr_avg <= 60
                   else 7 if (20 <= pr_avg < 30 or 60 < pr_avg <= 80)
                   else 3 if 80 < pr_avg <= 100
                   else 0)
    else:
        poin_pr = 0
    detail["pr_avg"]  = round(pr_avg, 1) if pr_avg is not None else None
    detail["poin_pr"] = poin_pr
    total += poin_pr

    # ── Indikator #6: Frekuensi Dividen · 8 poin ───────────────────────────
    frekuensi  = sum(1 for v in dps_5y if v is not None and v > 0)
    poin_freq  = (8 if frekuensi >= 5 else 5 if frekuensi >= 3 else 0)
    detail["frekuensi_div"] = frekuensi
    detail["poin_freq"]     = poin_freq
    total += poin_freq

    # ── Indikator #8: AEPD · 5 poin ────────────────────────────────────────
    aepd = None
    if dy_avg is not None and pr_avg is not None and pr_avg > 0:
        aepd = (10 * (dy_avg / 100)) / (pr_avg / 100)
    if aepd is not None:
        poin_aepd = (5 if aepd >= 2.0 else 3 if aepd >= 1.0 else 0)
    else:
        poin_aepd = 0
    detail["aepd"]      = round(aepd, 2) if aepd is not None else None
    detail["poin_aepd"] = poin_aepd
    total += poin_aepd

    return total, detail


def _score_dimensi_c(arrays: dict, info: dict) -> tuple[int, dict]:
    """Dimensi C — Momentum Terkini · maks 10 poin."""
    eps_5y = arrays["eps_5y"]
    detail = {}

    eps_valid = [v for v in eps_5y if v is not None]
    eps_yoy   = None

    if len(eps_valid) >= 2:
        e_curr = eps_valid[-1]
        e_prev = eps_valid[-2]
        if e_prev is not None and e_prev > 0 and e_curr is not None:
            eps_yoy = ((e_curr - e_prev) / abs(e_prev)) * 100

    # Fallback ke yfinance earnings growth
    if eps_yoy is None:
        eg = info.get("earningsGrowth")
        if eg is not None:
            eps_yoy = float(eg) * 100

    if eps_yoy is not None:
        poin = (10 if eps_yoy >= 10 else 7 if eps_yoy >= 5
                else 4 if eps_yoy >= 0 else 0)
    else:
        poin = 0

    detail["eps_yoy"]  = round(eps_yoy, 1) if eps_yoy is not None else None
    detail["poin_c"]   = poin
    return poin, detail


def _score_dimensi_d(arrays: dict, info: dict,
                     sektor: str, liquid_df_row) -> tuple[int, dict]:
    """Dimensi D — Kesehatan Balance Sheet · maks 10 poin."""
    detail = {}
    total  = 0
    sektor_upper = sektor.strip().title()

    if sektor_upper in SEKTOR_BANK:
        # CAR
        car = None
        if liquid_df_row is not None:
            car = liquid_df_row.get("CAR")
        if car is not None and not (isinstance(car, float) and np.isnan(car)):
            car = float(car)
            poin_car = (5 if car >= 17 else 3 if car >= 14
                        else 1 if car >= 8 else 0)
        else:
            poin_car = 0
            car      = None
        detail["car"]      = car
        detail["poin_car"] = poin_car
        total += poin_car

        # NPL
        npl = None
        if liquid_df_row is not None:
            npl = liquid_df_row.get("NPL")
        if npl is not None and not (isinstance(npl, float) and np.isnan(npl)):
            npl = float(npl)
            poin_npl = (5 if npl < 2 else 3 if npl <= 5 else 0)
        else:
            poin_npl = 0
            npl      = None
        detail["npl"]      = npl
        detail["poin_npl"] = poin_npl
        total += poin_npl

    elif sektor_upper in SEKTOR_INFRA:
        # Debt/EBITDA
        de = arrays.get("debt_ebitda")
        if de is None and liquid_df_row is not None:
            de = liquid_df_row.get("DebtEBITDA")
        if de is not None and not (isinstance(de, float) and np.isnan(de)):
            de = float(de)
            poin_de = (5 if de <= 3 else 3 if de <= 5 else 0)
        else:
            poin_de = 0
            de      = None
        detail["debt_ebitda"] = de
        detail["poin_de"]     = poin_de
        total += poin_de

        # ICR
        icr = arrays.get("icr")
        if icr is None and liquid_df_row is not None:
            icr = liquid_df_row.get("ICR")
        if icr is None:
            ebit    = info.get("ebit")
            int_exp = info.get("interestExpense")
            if ebit and int_exp and int_exp != 0:
                icr = abs(ebit / int_exp)
        if icr is not None:
            icr     = float(icr)
            poin_icr = (5 if icr >= 3 else 3 if icr >= 1.5 else 0)
        else:
            poin_icr = 0
            icr      = None
        detail["icr"]      = icr
        detail["poin_icr"] = poin_icr
        total += poin_icr

    else:
        # DER
        der_raw = info.get("debtToEquity")
        der     = (float(der_raw) / 100.0) if der_raw is not None else None
        if der is not None:
            poin_der = (5 if der <= 0.5 else 3 if der <= 1.5
                        else 1 if der <= 3.0 else 0)
        else:
            poin_der = 0
        detail["der"]      = round(der, 2) if der is not None else None
        detail["poin_der"] = poin_der
        total += poin_der

        # ICR
        icr = arrays.get("icr")
        if icr is None and liquid_df_row is not None:
            icr = liquid_df_row.get("ICR")
        if icr is None:
            ebit    = info.get("ebit")
            int_exp = info.get("interestExpense")
            if ebit and int_exp and int_exp != 0:
                icr = abs(ebit / int_exp)
        if icr is not None:
            icr     = float(icr)
            poin_icr = (5 if icr >= 5 else 3 if icr >= 3
                        else 1 if icr >= 1.5 else 0)
        else:
            poin_icr = 0
            icr      = None
        detail["icr"]      = icr
        detail["poin_icr"] = poin_icr
        total += poin_icr

    return total, detail


# ─────────────────────────────────────────────────────────────────────────────
# KLASIFIKASI GABUNGAN
# ─────────────────────────────────────────────────────────────────────────────

def _klasifikasi_gabungan(skor_hdy: int | None, konsistensi: int,
                          payout: float, knockout: bool) -> dict:
    """
    Klasifikasi gabungan yang menggabungkan track record konsistensi dan skor HDY.
    Kembalikan dict: label, emoji, warna, rekomendasi.
    """
    if knockout or skor_hdy is None:
        return {
            "label": "Tidak Layak", "emoji": "🚫",
            "warna": "#D50000",
            "rekomendasi": "Tidak memenuhi syarat minimum — hindari.",
        }
    if konsistensi == 0:
        return {
            "label": "No Dividend", "emoji": "⬛",
            "warna": "#9E9E9E",
            "rekomendasi": "Tidak ada riwayat dividen.",
        }
    if konsistensi >= 10 and payout < 80 and skor_hdy >= 80:
        return {
            "label": "Dividend Aristocrat", "emoji": "🏆",
            "warna": "#FFD600",
            "rekomendasi": "Koleksi penuh — rekam jejak terbaik.",
        }
    if skor_hdy >= 80:
        return {
            "label": "Prima", "emoji": "⭐",
            "warna": "#00C853",
            "rekomendasi": "Layak koleksi penuh.",
        }
    if konsistensi >= 5 and skor_hdy >= 65:
        return {
            "label": "Reliable", "emoji": "✅",
            "warna": "#00C853",
            "rekomendasi": "Layak koleksi dengan monitoring rutin.",
        }
    if skor_hdy >= 50:
        return {
            "label": "Perhatikan", "emoji": "⚠️",
            "warna": "#FFD600",
            "rekomendasi": "Masuk posisi kecil, pantau ketat.",
        }
    return {
        "label": "Tidak Layak", "emoji": "❌",
        "warna": "#D50000",
        "rekomendasi": "Risiko dividend cut tinggi — hindari.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# FORWARD YIELD PROJECTION
# ─────────────────────────────────────────────────────────────────────────────

def _hitung_forward_yield(arrays: dict, info: dict,
                          curr_price: float) -> dict | None:
    """Proyeksi forward DY berbasis blended AAGR + YoY EPS dan PR historis."""
    eps_5y = arrays["eps_5y"]
    pr_5y  = arrays["pr_5y"]

    eps_valid = [v for v in eps_5y if v is not None and v > 0]
    pr_valid  = [v for v in pr_5y  if v is not None]

    if not eps_valid or not pr_valid or curr_price <= 0:
        return None

    eps_last = eps_valid[-1]
    pr_avg   = float(np.mean(pr_valid))

    # AAGR
    aagr = 0.0
    if len(eps_valid) >= 2:
        growths = []
        for i in range(1, len(eps_valid)):
            if eps_valid[i - 1] > 0:
                growths.append((eps_valid[i] - eps_valid[i - 1]) / eps_valid[i - 1])
        aagr = float(np.mean(growths)) if growths else 0.0

    # EPS YoY
    eps_yoy = 0.0
    if len(eps_valid) >= 2 and eps_valid[-2] > 0:
        eps_yoy = (eps_valid[-1] - eps_valid[-2]) / abs(eps_valid[-2])
    else:
        eg = info.get("earningsGrowth")
        if eg is not None:
            eps_yoy = float(eg)

    eps_fwd = (eps_last * (1 + aagr) + eps_last * (1 + eps_yoy)) / 2
    dps_fwd = eps_fwd * pr_avg
    dy_fwd  = dps_fwd / curr_price

    label = ("🟢 Sangat Layak" if dy_fwd >= 0.10
             else "🟡 Layak"    if dy_fwd >= 0.06
             else "🔴 Perlu Dipertimbangkan Ulang")

    return {
        "eps_fwd":  round(eps_fwd, 2),
        "dps_fwd":  round(dps_fwd, 2),
        "dy_fwd":   round(dy_fwd * 100, 2),
        "label":    label,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PDF EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def _generate_pdf(
    ticker: str, company: str, sector: str, syariah: str,
    curr_price: float, klasifikasi: dict, skor_hdy: int | None,
    konsistensi: int, yield_val: float, payout: float, cagr: float,
    dy_avg3: float | None, dy_avg5: float | None,
    detail_a: dict, detail_b: dict, detail_c: dict, detail_d: dict,
    dim_a: int, dim_b: int, dim_c: int, dim_d: int,
    forward: dict | None,
    knockout_alasan: list[str],
    jumlah_lot: int, harga_beli: float,
    arrays: dict | None = None,
) -> bytes:
    """Generate laporan PDF lengkap analisa dividen."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── Header ──────────────────────────────────────────────────────────────
    pdf.set_fill_color(20, 20, 20)
    pdf.rect(0, 0, 210, 25, "F")

    logo_path = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_path):
        logo_path = "../logo_expert_stock_pro.png"
    if os.path.exists(logo_path):
        pdf.set_fill_color(218, 165, 32)
        pdf.rect(10, 3, 19, 19, "F")
        pdf.image(logo_path, x=10.5, y=3.5, w=18, h=18)

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 15)
    pdf.set_xy(35, 8)
    pdf.cell(0, 10, "Expert Stock Pro - Analisa Dividen Pro", ln=True)
    pdf.set_y(28)

    pdf.set_font("Arial", "I", 10)
    pdf.set_text_color(0, 0, 255)
    pdf.cell(0, 5, "Sumber: https://s.id/pintarsaham", ln=True, align="C",
             link="https://s.id/pintarsaham")
    pdf.ln(2)

    # ── Identitas Ticker ─────────────────────────────────────────────────────
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 8, _safe_latin1(f"{ticker} - {company}"), ln=True, align="C")
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, _safe_latin1(f"Sektor: {sector} | Status: {syariah}"),
             ln=True, align="C")
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 5,
             _safe_latin1(f"Analisa: {datetime.now().strftime('%d-%m-%Y %H:%M')} "
                          f"| Harga: Rp {curr_price:,.0f}"),
             ln=True, align="R")
    pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
    pdf.ln(5)

    # ── Klasifikasi & Skor HDY ───────────────────────────────────────────────
    pdf.set_font("Arial", "B", 13)
    kls_str = (f"{klasifikasi['emoji']} {klasifikasi['label']}"
               if not knockout_alasan
               else "TIDAK LAYAK (Hard Knockout)")
    pdf.cell(0, 7, _safe_latin1(f"Klasifikasi: {kls_str}"), ln=True)

    if not knockout_alasan and skor_hdy is not None:
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 6,
                 _safe_latin1(f"Skor HDY: {skor_hdy}/100 — "
                              f"Dim A: {dim_a}/45 | B: {dim_b}/35 | "
                              f"C: {dim_c}/10 | D: {dim_d}/10"),
                 ln=True)
        pdf.cell(0, 6,
                 _safe_latin1(f"Rekomendasi: {klasifikasi['rekomendasi']}"),
                 ln=True)
    else:
        pdf.set_font("Arial", "", 11)
        for al in knockout_alasan:
            pdf.cell(0, 6, _safe_latin1(f"  - {al}"), ln=True)
    pdf.ln(3)

    # ── Bagian 1: Riwayat & Metrik ──────────────────────────────────────────
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "1. Riwayat & Metrik Dividen", ln=True)
    pdf.set_font("Arial", "", 11)
    rows_1 = [
        f"Dividend Yield saat ini: {yield_val:.2f}%",
        f"Rata-rata Yield 3 Tahun: {f'{dy_avg3:.2f}%' if dy_avg3 else 'N/A'}",
        f"Rata-rata Yield 5 Tahun: {f'{dy_avg5:.2f}%' if dy_avg5 else 'N/A'}",
        f"Payout Ratio TTM: {payout:.1f}%",
        f"CAGR DPS 5 Tahun: {cagr * 100:.1f}%",
        f"Konsistensi (berturut-turut): {konsistensi} tahun",
    ]
    for r in rows_1:
        pdf.cell(0, 6, _safe_latin1(r), ln=True)
    pdf.ln(3)

    # ── Bagian 2: Detail Skor HDY ────────────────────────────────────────────
    if not knockout_alasan and skor_hdy is not None:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, "2. Detail Skor HDY", ln=True)
        pdf.set_font("Arial", "", 10)

        def _row(label, val, poin, maks):
            line = f"  {label}: {val} -> {poin}/{maks} poin"
            pdf.cell(0, 5, _safe_latin1(line), ln=True)

        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 6, f"  Dimensi A — Earnings & FCF: {dim_a}/45", ln=True)
        pdf.set_font("Arial", "", 10)
        _row("EPS Predictability R²",
             f"{detail_a.get('r2', 'N/A')}%", detail_a.get("poin_r2", 0), 15)
        _row("AAGR EPS 5 Tahun",
             f"{detail_a.get('aagr_eps', 'N/A')}%", detail_a.get("poin_aagr", 0), 12)
        _row("FCF Positif",
             f"{detail_a.get('fcf_positif_tahun', 0)}/5 tahun",
             detail_a.get("poin_fcf", 0), 10)
        _row("FCF Payout Ratio",
             f"{detail_a.get('fcf_pr', 'N/A')}%", detail_a.get("poin_fcf_pr", 0), 5)
        _row("Konsistensi Pertumbuhan EPS",
             f"{detail_a.get('eps_tumbuh_tahun', 0)} tahun tumbuh",
             detail_a.get("poin_eps_tumbuh", 0), 3)

        pdf.ln(2)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 6, f"  Dimensi B — Track Record Dividen: {dim_b}/35", ln=True)
        pdf.set_font("Arial", "", 10)
        _row("Rata-rata DY 5 Tahun",
             f"{detail_b.get('dy_avg', 'N/A')}%", detail_b.get("poin_dy", 0), 12)
        _row("Rata-rata Payout Ratio",
             f"{detail_b.get('pr_avg', 'N/A')}%", detail_b.get("poin_pr", 0), 10)
        _row("Frekuensi Dividen",
             f"{detail_b.get('frekuensi_div', 0)}/5 tahun",
             detail_b.get("poin_freq", 0), 8)
        _row("AEPD", f"{detail_b.get('aepd', 'N/A')}",
             detail_b.get("poin_aepd", 0), 5)

        pdf.ln(2)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 6, f"  Dimensi C — Momentum Terkini: {dim_c}/10", ln=True)
        pdf.set_font("Arial", "", 10)
        _row("EPS Growth YoY",
             f"{detail_c.get('eps_yoy', 'N/A')}%", detail_c.get("poin_c", 0), 10)

        pdf.ln(2)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 6, f"  Dimensi D — Kesehatan Balance Sheet: {dim_d}/10", ln=True)
        pdf.set_font("Arial", "", 10)
        for k, v in detail_d.items():
            if not k.startswith("poin"):
                poin_key = f"poin_{k}" if f"poin_{k}" in detail_d else None
                poin_val = detail_d.get(poin_key, "-") if poin_key else "-"
                pdf.cell(0, 5,
                         _safe_latin1(f"  {k.upper()}: {v} -> {poin_val} poin"),
                         ln=True)
        pdf.ln(3)

        # Forward Yield
        if forward:
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 7, "3. Proyeksi Forward Dividend Yield", ln=True)
            pdf.set_font("Arial", "", 11)
            pdf.cell(0, 6,
                     _safe_latin1(f"  EPS Forward: Rp {forward['eps_fwd']:,.2f}"),
                     ln=True)
            pdf.cell(0, 6,
                     _safe_latin1(f"  DPS Forward: Rp {forward['dps_fwd']:,.2f}"),
                     ln=True)
            pdf.cell(0, 6,
                     _safe_latin1(f"  Forward DY: {forward['dy_fwd']:.2f}% "
                                  f"— {forward['label']}"),
                     ln=True)
            pdf.set_font("Arial", "I", 9)
            pdf.cell(0, 5,
                     _safe_latin1("  *Proyeksi berbasis asumsi mekanis "
                                  "dari data historis — bukan jaminan."),
                     ln=True)
            pdf.ln(3)

    # ── Proyeksi Pendapatan (jika ada input lot) ─────────────────────────────
    if jumlah_lot > 0:
        n_bagian = 4 if (knockout_alasan or skor_hdy is None) else 4
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, f"{n_bagian}. Proyeksi Pendapatan Dividen", ln=True)
        pdf.set_font("Arial", "", 11)
        dps_terakhir = 0.0
        # ambil dari DPS_5Y jika ada
        dps_arr = [v for v in (arrays or {}).get("dps_5y", []) if v is not None and v > 0]
        if dps_arr:
            dps_terakhir = dps_arr[-1]
        lembar        = jumlah_lot * 100
        est_div_tahun = dps_terakhir * lembar
        pdf.cell(0, 6,
                 _safe_latin1(f"  Jumlah Lot: {jumlah_lot:,} lot "
                              f"({lembar:,} lembar)"),
                 ln=True)
        pdf.cell(0, 6,
                 _safe_latin1(f"  DPS Terakhir: Rp {dps_terakhir:,.2f}"),
                 ln=True)
        pdf.cell(0, 6,
                 _safe_latin1(f"  Estimasi Dividen/Tahun: "
                              f"Rp {est_div_tahun:,.0f}"),
                 ln=True)
        if harga_beli > 0 and dps_terakhir > 0:
            yoc = dps_terakhir / harga_beli * 100
            pdf.cell(0, 6,
                     _safe_latin1(f"  Yield-on-Cost: {yoc:.2f}% "
                                  f"(harga beli Rp {harga_beli:,.0f})"),
                     ln=True)
        pdf.ln(3)

    # ── Disclaimer ───────────────────────────────────────────────────────────
    pdf.ln(3)
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5, _safe_latin1(
        "DISCLAIMER: Laporan ini dihasilkan secara otomatis menggunakan algoritma "
        "analisis fundamental. Bukan merupakan ajakan atau rekomendasi pasti untuk "
        "membeli/menjual saham. Keputusan investasi sepenuhnya tanggung jawab pribadi. "
        "Selalu terapkan manajemen risiko dan lakukan DYOR sebelum berinvestasi."
    ))

    try:
        out = pdf.output(dest="S")
        return out.encode("latin-1") if isinstance(out, str) else bytes(out)
    except Exception:
        return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def run_dividen():
    """Entry point modul Analisa Dividen Pro."""
    # ── Logo ─────────────────────────────────────────────────────────────────
    logo_file = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_file):
        logo_file = "../logo_expert_stock_pro.png"
    if os.path.exists(logo_file):
        with open(logo_file, "rb") as f:
            enc = base64.b64encode(f.read()).decode()
        st.markdown(
            f'<div style="display:flex;justify-content:center;margin-bottom:10px;">'
            f'<img src="data:image/png;base64,{enc}" width="150"></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<h1 style='text-align:center;'>💰 Analisa Dividen Pro</h1>",
                unsafe_allow_html=True)
    st.markdown("---")

    # ── Input — di halaman utama, bukan sidebar ───────────────────────────────
    col_inp1, col_inp2, col_inp3 = st.columns([2, 2, 2])
    with col_inp1:
        ticker_input = st.text_input("Kode Saham (contoh: BBCA):", value="BBCA").upper()
    with col_inp2:
        jumlah_lot = st.number_input(
            "Jumlah Lot yang Dimiliki (opsional):",
            min_value=0, value=0, step=1,
        )
    with col_inp3:
        harga_beli = st.number_input(
            "Harga Beli Rata-rata (opsional, Rp):",
            min_value=0.0, value=0.0, step=100.0, format="%.0f",
        )

    jalankan = st.button(
        "🔍 Jalankan Analisa Dividen",
        use_container_width=True,
    )
    st.markdown("---")

    if not jalankan:
        st.info("Masukkan kode saham di atas, lalu klik **Jalankan Analisa Dividen**.")
        return

    ticker_bersih = ticker_input.strip().upper().replace(".JK", "")
    ticker_jk     = ticker_bersih + ".JK"

    # ── Fetch data ────────────────────────────────────────────────────────────
    with st.spinner(f"Mengambil data untuk {ticker_jk}..."):
        liquid_df  = get_liquid_stocks()
        is_liquid  = is_ticker_liquid(ticker_bersih, liquid_df)
        ticker_row = get_ticker_row(ticker_bersih, liquid_df)

        if not is_liquid:
            st.info("ℹ️ Ticker tidak ada dalam daftar saham pilihan. "
                    "Analisa menggunakan data langsung dari yfinance.")
            try:
                df_pre     = pd.read_csv(PRE_LIQUID_PATH)
                ticker_row = get_ticker_row(ticker_bersih, df_pre)
            except Exception:
                ticker_row = None

        identitas = _get_identitas(ticker_bersih, liquid_df)
        sektor    = identitas["sektor"]
        syariah   = identitas["syariah"]

        stock_data = get_full_stock_data(ticker_jk)

    info    = stock_data.get("info", {})
    divs    = stock_data.get("dividends")
    history = stock_data.get("history", pd.DataFrame())

    if history.empty:
        st.warning("⚠️ Data tidak tersedia untuk ticker ini. Coba ticker lain.")
        st.stop()

    # ── Harga sekarang ────────────────────────────────────────────────────────
    curr_price = float(info.get("currentPrice") or history["Close"].iloc[-1] or 0)

    if divs is None or len(divs) == 0:
        st.error("❌ Data dividen tidak ditemukan atau emiten tidak pernah membagi dividen.")

        # Klasifikasi No Dividend tetap ditampilkan
        kls = _klasifikasi_gabungan(None, 0, 0.0, False)
        st.markdown(
            f'<div style="padding:12px;background:#1E1E1E;border-radius:8px;'
            f'border-left:5px solid {kls["warna"]};">'
            f'<b style="color:{kls["warna"]};">{kls["emoji"]} {kls["label"]}</b>'
            f'</div>',
            unsafe_allow_html=True,
        )
        return

    # ── Metrik fundamental dasar ──────────────────────────────────────────────
    yield_val    = float(info.get("dividendYield") or 0) * 100
    payout       = float(info.get("payoutRatio")   or 0) * 100
    company_name = info.get("longName") or ticker_bersih

    # ── Histori dividen ───────────────────────────────────────────────────────
    df_div       = divs.to_frame(name="Dividends")
    df_div.index = pd.to_datetime(df_div.index).tz_localize(None)
    df_div["year"] = df_div.index.year

    df_div_annual = (df_div.groupby("year")["Dividends"].sum()
                     .reset_index()
                     .rename(columns={"year": "Tahun", "Dividends": "DPS"}))

    konsistensi = _hitung_konsistensi_berturut(divs)
    dy_avg3     = _hitung_dy_avg(divs, history, n_tahun=3)
    dy_avg5     = _hitung_dy_avg(divs, history, n_tahun=5)

    # CAGR DPS 5 tahun
    last5   = df_div_annual.tail(5)
    cagr    = 0.0
    if len(last5) >= 2:
        awal  = last5["DPS"].iloc[0]
        akhir = last5["DPS"].iloc[-1]
        n     = len(last5) - 1
        if awal > 0:
            cagr = (akhir / awal) ** (1 / n) - 1

    # Ex-dividend date berikutnya
    ex_date = info.get("exDividendDate")
    if ex_date:
        try:
            ex_date_str = pd.Timestamp(ex_date, unit="s").strftime("%d %b %Y")
        except Exception:
            ex_date_str = str(ex_date)
    else:
        ex_date_str = "Tidak tersedia"

    # ── Build arrays HDY ──────────────────────────────────────────────────────
    if is_liquid and ticker_row is not None:
        arrays = _build_hdy_arrays_from_liquid(ticker_row)
    else:
        arrays = _build_hdy_arrays_from_yfinance(stock_data, curr_price, divs)

    liquid_df_row = ticker_row if is_liquid else None

    # ── Hard knockout ─────────────────────────────────────────────────────────
    knockout_alasan = _check_hard_knockout(arrays, info, sektor,
                                           ticker_row, liquid_df_row)

    # ── Scoring HDY ───────────────────────────────────────────────────────────
    skor_hdy  = None
    dim_a = dim_b = dim_c = dim_d = 0
    detail_a = detail_b = detail_c = detail_d = {}
    forward   = None

    if not knockout_alasan:
        dim_a, detail_a = _score_dimensi_a(arrays)
        dim_b, detail_b = _score_dimensi_b(arrays, yield_val / 100)
        dim_c, detail_c = _score_dimensi_c(arrays, info)
        dim_d, detail_d = _score_dimensi_d(arrays, info, sektor, liquid_df_row)
        skor_hdy        = min(100, max(0, dim_a + dim_b + dim_c + dim_d))
        forward         = _hitung_forward_yield(arrays, info, curr_price)

    # ── Klasifikasi gabungan ──────────────────────────────────────────────────
    klasifikasi = _klasifikasi_gabungan(
        skor_hdy, konsistensi, payout, bool(knockout_alasan)
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # UI — HEADER SUMMARY
    # ═══════════════════════════════════════════════════════════════════════════
    syariah_label = (
        "✅ Syariah"     if syariah == "Ya"
        else "❌ Non-Syariah" if syariah == "Tidak"
        else "❓ Status tidak diketahui"
    )

    st.markdown(f"""
        <div style="padding:20px;background:#1E1E1E;border-radius:10px;
                    border:1px solid #333;text-align:center;">
            <h2 style="color:#2ECC71;margin-bottom:4px;">
                🏢 {ticker_bersih} — {company_name}
            </h2>
            <p style="color:#A0A0A0;margin-bottom:12px;">
                Sektor: {sektor} &nbsp;|&nbsp;
                <span style="color:white;">{syariah_label}</span>
            </p>
            <p style="color:white;font-size:1.1em;margin-bottom:6px;">
                Harga: <b>Rp {curr_price:,.0f}</b>
                &nbsp;|&nbsp; Ex-Div berikutnya: <b>{ex_date_str}</b>
            </p>
            <div style="background:{klasifikasi['warna']};display:inline-block;
                        padding:6px 20px;border-radius:20px;margin-top:4px;">
                <b style="color:{'#000' if klasifikasi['warna'] == '#FFD600' else '#fff'};
                           font-size:1.2em;">
                    {klasifikasi['emoji']} {klasifikasi['label']}
                </b>
            </div>
            {"" if not skor_hdy else
             f'<p style="color:#A0A0A0;margin-top:8px;font-size:0.95em;">'
             f'Skor HDY: <b style="color:white;">{skor_hdy}/100</b></p>'}
        </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════════
    # UI — BAGIAN 1: RIWAYAT DIVIDEN
    # ═══════════════════════════════════════════════════════════════════════════
    st.header("1. Riwayat & Metrik Dividen")

    # Bar chart DPS tahunan
    fig_bar = go.Figure(go.Bar(
        x=df_div_annual["Tahun"].astype(str),
        y=df_div_annual["DPS"],
        marker_color="#2ECC71",
        text=df_div_annual["DPS"].apply(lambda v: f"Rp {v:,.1f}"),
        textposition="outside",
    ))
    fig_bar.update_layout(
        title="Riwayat DPS Tahunan",
        xaxis_title="Tahun", yaxis_title="DPS (Rp)",
        plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
        font_color="white", height=320,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # Tabel riwayat dividen tahunan
    tabel_div = df_div_annual.copy()
    tabel_div["Yield Saat Itu"] = tabel_div.apply(
        lambda r: f"{r['DPS'] / float(history[history.index.year == r['Tahun']]['Close'].iloc[-1]) * 100:.2f}%"
        if not history[history.index.year == r["Tahun"]].empty else "N/A",
        axis=1,
    )
    tabel_div["DPS"] = tabel_div["DPS"].apply(lambda v: f"Rp {v:,.2f}")
    st.dataframe(
        tabel_div.rename(columns={"Tahun": "Tahun", "DPS": "DPS",
                                  "Yield Saat Itu": "Yield Saat Itu"}),
        use_container_width=True, hide_index=True,
    )

    # Metrik utama
    c1, c2, c3 = st.columns(3)
    c1.metric("Dividend Yield", f"{yield_val:.2f}%")
    c2.metric("Rata-rata Yield 3 Tahun",
              f"{dy_avg3 * 100:.2f}%" if dy_avg3 else "N/A")
    c3.metric("Rata-rata Yield 5 Tahun",
              f"{dy_avg5 * 100:.2f}%" if dy_avg5 else "N/A")

    c4, c5, c6 = st.columns(3)
    c4.metric("Payout Ratio TTM", f"{payout:.1f}%")
    c5.metric("CAGR DPS 5 Tahun", f"{cagr * 100:.1f}%")
    c6.metric("Konsistensi Berturut-turut", f"{konsistensi} tahun")

    # Peringatan otomatis
    if payout > 90:
        st.warning("⚠️ Payout Ratio > 90% — dividen berpotensi tidak berkelanjutan.")
    if yield_val > 15:
        st.warning("⚠️ Yield sangat tinggi (> 15%) — verifikasi apakah ini anomali "
                   "atau penurunan harga tajam.")
    if 0 < yield_val < 10:
        st.info("ℹ️ Yield < 10% — belum memenuhi target dividend investing aplikasi ini.")

    # Proyeksi pendapatan dividen
    if jumlah_lot > 0:
        st.subheader("📊 Proyeksi Pendapatan Dividen")
        dps_arr     = [v for v in arrays.get("dps_5y", []) if v is not None and v > 0]
        dps_display = dps_arr[-1] if dps_arr else 0.0
        lembar      = jumlah_lot * 100
        est_tahunan = dps_display * lembar
        pr1, pr2    = st.columns(2)
        pr1.metric("Estimasi Dividen/Tahun",
                   f"Rp {est_tahunan:,.0f}",
                   help=f"Berbasis DPS terakhir Rp {dps_display:,.2f} × {lembar:,} lembar")
        if harga_beli > 0 and dps_display > 0:
            yoc = dps_display / harga_beli * 100
            pr2.metric("Yield-on-Cost",
                       f"{yoc:.2f}%",
                       help=f"DPS / harga beli rata-rata Rp {harga_beli:,.0f}")

    # ═══════════════════════════════════════════════════════════════════════════
    # UI — BAGIAN 2: SKOR KELAYAKAN HDY
    # ═══════════════════════════════════════════════════════════════════════════
    with st.expander("📊 Skor Kelayakan High Dividend Yield (HDY)", expanded=True):

        if not is_liquid:
            st.warning(
                "⚠️ Ticker tidak ada di daftar saham pilihan. Skor HDY dihitung "
                "dari data yfinance — akurasi tidak dijamin. "
                "Hasil sebaiknya diverifikasi secara manual."
            )

        if knockout_alasan:
            st.error("🚫 **TIDAK LAYAK — Hard Knockout**")
            for al in knockout_alasan:
                st.markdown(f"- {al}")
            st.stop()

        # ── Progress bar skor ──────────────────────────────────────────────
        warna_skor = ("#00C853" if skor_hdy >= 80
                      else "#FFD600" if skor_hdy >= 65
                      else "#FF9800" if skor_hdy >= 50
                      else "#D50000")
        st.markdown(f"""
            <div style="margin-bottom:12px;">
                <div style="display:flex;justify-content:space-between;">
                    <b style="color:white;">Skor HDY Total</b>
                    <b style="color:{warna_skor};">{skor_hdy}/100</b>
                </div>
                <div style="background:#333;border-radius:6px;height:14px;margin-top:4px;">
                    <div style="background:{warna_skor};width:{skor_hdy}%;
                                height:14px;border-radius:6px;"></div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Label kelayakan
        label_map = {
            (80, 101): ("⭐ Prima", "Layak koleksi penuh"),
            (65,  80): ("✅ Layak", "Layak koleksi dengan monitoring rutin"),
            (50,  65): ("⚠️ Perhatikan", "Posisi kecil, pantau ketat"),
            ( 0,  50): ("❌ Tidak Layak", "Hindari; risiko dividend cut tinggi"),
        }
        for (lo, hi), (lbl, rek) in label_map.items():
            if lo <= skor_hdy < hi:
                st.markdown(
                    f'<div style="padding:10px;background:#1E1E1E;border-radius:8px;'
                    f'border-left:5px solid {warna_skor};margin-bottom:12px;">'
                    f'<b style="color:{warna_skor};">{lbl}</b> — {rek}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                break

        # ── Detail per dimensi ─────────────────────────────────────────────
        st.markdown("---")
        tab_a, tab_b, tab_c, tab_d = st.tabs([
            f"A: Earnings & FCF ({dim_a}/45)",
            f"B: Track Record ({dim_b}/35)",
            f"C: Momentum ({dim_c}/10)",
            f"D: Balance Sheet ({dim_d}/10)",
        ])

        with tab_a:
            rows_a = [
                ("EPS Predictability (R²)",
                 f"{detail_a.get('r2', 'N/A')}%",
                 detail_a.get("poin_r2", 0), 15,
                 detail_a.get("r2_note", "")),
                ("AAGR EPS 5 Tahun",
                 f"{detail_a.get('aagr_eps', 'N/A')}%",
                 detail_a.get("poin_aagr", 0), 12, ""),
                ("FCF Positif",
                 f"{detail_a.get('fcf_positif_tahun', 0)}/5 tahun",
                 detail_a.get("poin_fcf", 0), 10, ""),
                ("FCF Payout Ratio (proxy)",
                 f"{detail_a.get('fcf_pr', 'N/A')}%",
                 detail_a.get("poin_fcf_pr", 0), 5, ""),
                ("Konsistensi Tumbuh EPS",
                 f"{detail_a.get('eps_tumbuh_tahun', 0)} tahun",
                 detail_a.get("poin_eps_tumbuh", 0), 3, ""),
            ]
            df_a = pd.DataFrame(rows_a,
                                columns=["Indikator", "Nilai", "Poin", "Maks", "Catatan"])
            st.dataframe(
                df_a.drop(columns="Catatan"),
                column_config={
                    "Poin": st.column_config.ProgressColumn(
                        min_value=0, max_value=15, format="%d"),
                },
                use_container_width=True, hide_index=True,
            )
            for row in rows_a:
                if row[4]:
                    st.caption(f"ℹ️ {row[0]}: {row[4]}")

        with tab_b:
            rows_b = [
                ("Rata-rata DY 5 Tahun",
                 f"{detail_b.get('dy_avg', 'N/A')}%",
                 detail_b.get("poin_dy", 0), 12),
                ("Rata-rata Payout Ratio",
                 f"{detail_b.get('pr_avg', 'N/A')}%",
                 detail_b.get("poin_pr", 0), 10),
                ("Frekuensi Dividen",
                 f"{detail_b.get('frekuensi_div', 0)}/5 tahun",
                 detail_b.get("poin_freq", 0), 8),
                ("AEPD",
                 str(detail_b.get("aepd", "N/A")),
                 detail_b.get("poin_aepd", 0), 5),
            ]
            df_b = pd.DataFrame(rows_b,
                                columns=["Indikator", "Nilai", "Poin", "Maks"])
            st.dataframe(
                df_b,
                column_config={
                    "Poin": st.column_config.ProgressColumn(
                        min_value=0, max_value=12, format="%d"),
                },
                use_container_width=True, hide_index=True,
            )
            if detail_b.get("anomali_yield"):
                st.warning(
                    "⚠️ Yield saat ini jauh di atas rata-rata historis — "
                    "verifikasi apakah ini disebabkan penurunan harga, "
                    "bukan kenaikan dividen."
                )

        with tab_c:
            eps_yoy_val = detail_c.get("eps_yoy")
            poin_c      = detail_c.get("poin_c", 0)
            st.metric("EPS Growth YoY",
                      f"{eps_yoy_val:.1f}%" if eps_yoy_val is not None else "N/A",
                      delta=f"{poin_c}/10 poin")

        with tab_d:
            sektor_upper = sektor.strip().title()
            rows_d = []
            if sektor_upper in SEKTOR_BANK:
                rows_d = [
                    ("CAR", detail_d.get("car"), detail_d.get("poin_car", 0), 5),
                    ("NPL", detail_d.get("npl"), detail_d.get("poin_npl", 0), 5),
                ]
            elif sektor_upper in SEKTOR_INFRA:
                rows_d = [
                    ("Debt/EBITDA", detail_d.get("debt_ebitda"),
                     detail_d.get("poin_de", 0), 5),
                    ("ICR", detail_d.get("icr"), detail_d.get("poin_icr", 0), 5),
                ]
            else:
                rows_d = [
                    ("DER", detail_d.get("der"), detail_d.get("poin_der", 0), 5),
                    ("ICR", detail_d.get("icr"), detail_d.get("poin_icr", 0), 5),
                ]
            df_d = pd.DataFrame(
                [(r[0],
                  f"{r[1]:.2f}" if r[1] is not None else "N/A",
                  r[2], r[3])
                 for r in rows_d],
                columns=["Indikator", "Nilai", "Poin", "Maks"],
            )
            st.dataframe(
                df_d,
                column_config={
                    "Poin": st.column_config.ProgressColumn(
                        min_value=0, max_value=5, format="%d"),
                },
                use_container_width=True, hide_index=True,
            )
            if not is_liquid and sektor_upper in (SEKTOR_BANK | SEKTOR_INFRA):
                st.caption(
                    "ℹ️ Data CAR/NPL/Debt-EBITDA tidak tersedia dari yfinance. "
                    "Dimensi D dihitung dengan data yang ada saja."
                )

        # ── Forward Yield Projection ───────────────────────────────────────
        st.markdown("---")
        st.subheader("📈 Estimasi Forward Dividend Yield")
        if forward:
            fc1, fc2, fc3 = st.columns(3)
            fc1.metric("EPS Forward",    f"Rp {forward['eps_fwd']:,.2f}")
            fc2.metric("DPS Forward",    f"Rp {forward['dps_fwd']:,.2f}")
            fc3.metric("Forward DY",     f"{forward['dy_fwd']:.2f}%",
                       delta=forward["label"])
            st.caption(
                "⚠️ Proyeksi berbasis asumsi mekanis dari data historis — "
                "bukan jaminan."
            )
        else:
            st.info("Data tidak mencukupi untuk menghitung proyeksi forward yield.")

    # ═══════════════════════════════════════════════════════════════════════════
    # UI — EXPORT PDF
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("---")
    if st.button("📄 Generate Laporan PDF", use_container_width=True):
        with st.spinner("Membuat laporan PDF..."):
            pdf_bytes = _generate_pdf(
                ticker=ticker_bersih,
                company=company_name,
                sector=sektor,
                syariah=syariah,
                curr_price=curr_price,
                klasifikasi=klasifikasi,
                skor_hdy=skor_hdy,
                konsistensi=konsistensi,
                yield_val=yield_val,
                payout=payout,
                cagr=cagr,
                dy_avg3=dy_avg3 * 100 if dy_avg3 else None,
                dy_avg5=dy_avg5 * 100 if dy_avg5 else None,
                detail_a=detail_a,
                detail_b=detail_b,
                detail_c=detail_c,
                detail_d=detail_d,
                dim_a=dim_a, dim_b=dim_b, dim_c=dim_c, dim_d=dim_d,
                forward=forward,
                knockout_alasan=knockout_alasan,
                jumlah_lot=int(jumlah_lot),
                harga_beli=float(harga_beli),
                arrays=arrays,
            )
        st.download_button(
            label="⬇️ Download PDF",
            data=pdf_bytes,
            file_name=(f"ExpertStockPro_Dividen_{ticker_bersih}_"
                       f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"),
            mime="application/pdf",
            use_container_width=True,
        )

    st.markdown("---")
    st.caption(
        "⚠️ **DISCLAIMER:** Laporan ini dihasilkan secara otomatis menggunakan "
        "algoritma analisis fundamental. Bukan merupakan ajakan atau rekomendasi "
        "pasti untuk membeli/menjual saham. Keputusan investasi sepenuhnya "
        "tanggung jawab pribadi. Selalu terapkan manajemen risiko dan lakukan "
        "DYOR sebelum mengambil keputusan di pasar modal."
    )
