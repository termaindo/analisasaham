"""
screening_hdy.py
================
Modul Screening High Dividend Yield (HDY).

Universe saham: dibaca dari liquid_dividend_stocks.csv via
get_liquid_dividend_stocks(). Scoring menggunakan pendekatan dua tahap:
  1. Hard Knockout Filter — eliminasi cepat atas kondisi fatal
  2. Simplified 100-Point Scoring — penilaian mendalam per dimensi

Scoring 100 Poin:
  Dimensi A — Keberlanjutan Earnings & FCF  : 40 poin
  Dimensi B — Track Record Distribusi       : 40 poin
  Dimensi C — Momentum Terkini             : 10 poin
  Dimensi D — Kesehatan Balance Sheet      : 10 poin

Output: Top 5 kartu prioritas + Watchlist sampai rank 20, diurutkan
dari skor tertinggi. Dilengkapi info jarak hari ke ex-dividend date
untuk mitigasi dividend trap.

Stale warning: >= 2 hari dari candle valid terakhir.
"""

import json
import os
import concurrent.futures
from datetime import datetime, date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pytz
import streamlit as st
from fpdf import FPDF

from utils.data_loader import (
    get_full_stock_data,
    get_liquid_dividend_stocks,
    is_ticker_liquid,
    get_ticker_row,
    PRE_LIQUID_PATH,
    LIQUID_DIVIDEND_PATH,
    hitung_div_yield_normal,
)

# ─────────────────────────────────────────────────────────────────────────────
# KONSTANTA
# ─────────────────────────────────────────────────────────────────────────────

# Hard knockout thresholds
DER_MAX_GENERAL      = 3.0
CAR_MIN_BANK         = 8.0
NPL_MAX_BANK         = 5.0
DEBT_EBITDA_MAX_INFRA= 5.0
PAYOUT_RATIO_MAX_KO  = 1.0   # > 100% = knockout
FREQ_MIN_DIVIDEN     = 3     # minimum 3x dalam 5 tahun

# Warning thresholds
PAYOUT_WARNING       = 0.90  # > 90%
YIELD_ANOMALY        = 15.0  # > 15% (dalam %)
YIELD_ANOMALY_MULT   = 1.5   # DY_now > 1.5 * DY_avg_5y

# Score thresholds
SCORE_MIN_ENTRY      = 50    # minimum skor untuk masuk watchlist

# Ex-date warning windows
EXDATE_WARN_BEFORE   = 7     # hari sebelum ex-date = waspada dividend trap
EXDATE_WARN_AFTER    = 14    # hari setelah ex-date = harga mungkin masih terkoreksi

# Sektor
SEKTOR_BANK   = {"Bank", "Finansial", "Keuangan", "Perbankan", "Financial Services"}
SEKTOR_INFRA  = {"Infrastruktur", "Utilitas", "Infrastructure", "Utilities"}

_TZ_WIB = pytz.timezone("Asia/Jakarta")


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — PARSE DATA
# ─────────────────────────────────────────────────────────────────────────────

def _parse_json_col(val) -> list:
    """Parse kolom JSON array dari CSV; kembalikan list atau []."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return []
    if isinstance(val, list):
        return val
    try:
        parsed = json.loads(str(val))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _valid_floats(arr: list) -> list[float]:
    """Ambil nilai tidak None dan bukan NaN dari list; kembalikan list float."""
    result = []
    for v in arr:
        if v is None:
            continue
        try:
            f = float(v)
            if not np.isnan(f):
                result.append(f)
        except (TypeError, ValueError):
            continue
    return result


def _safe_float(val, default=None):
    """Konversi ke float aman; return default jika gagal atau NaN."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if np.isnan(f) else f
    except (TypeError, ValueError):
        return default


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — FORMAT RUPIAH
# ─────────────────────────────────────────────────────────────────────────────

def format_rp(angka) -> str:
    """Format angka ke string Rupiah dengan pemisah ribuan titik."""
    if isinstance(angka, str):
        return angka
    try:
        return f"{int(angka):,}".replace(",", ".")
    except Exception:
        return str(angka)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — SAFE LATIN-1 UNTUK PDF
# ─────────────────────────────────────────────────────────────────────────────

_LATIN1_MAP = {
    "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2022": "*", "\u2026": "...",
    "\u2192": "->", "\u00d7": "x", "\u00b0": " deg",
    "\u2605": "*", "\u2713": "v", "\u2715": "x",
    "\u26a0": "[!]", "\u2705": "[OK]", "\u274c": "[X]",
}

def _safe_latin1(text: str) -> str:
    """Sanitasi string agar aman untuk FPDF latin-1."""
    if not isinstance(text, str):
        text = str(text)
    for ch, repl in _LATIN1_MAP.items():
        text = text.replace(ch, repl)
    return text.encode("latin-1", "ignore").decode("latin-1")


# ─────────────────────────────────────────────────────────────────────────────
# LOAD UNIVERSE
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def load_universe_hdy() -> tuple[list[str], pd.DataFrame]:
    """
    Muat universe saham dari liquid_dividend_stocks.csv.
    Return: (ticker_list, df_universe)
    """
    df = get_liquid_dividend_stocks()
    if df.empty:
        return [], pd.DataFrame()

    df = _normalize_universe_cols(df)
    if "Kode Saham" not in df.columns:
        return [], pd.DataFrame()

    ticker_list = [
        (t if t.endswith(".JK") else t + ".JK")
        for t in df["Kode Saham"].astype(str).str.strip().tolist()
        if t and t.lower() not in ("nan", "none", "")
    ]
    return ticker_list, df


def _normalize_universe_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Normalisasi nama kolom DataFrame universe."""
    df = df.copy()
    df.columns = df.columns.str.strip()
    rename_map = {}
    for col in df.columns:
        c = col.lower().strip().lstrip("\ufeff")
        if c in ("ticker", "kode saham", "kode", "saham"):
            rename_map[col] = "Kode Saham"
        elif c in ("sektor", "sector"):
            rename_map[col] = "Sektor"
        elif c == "syariah":
            rename_map[col] = "Syariah"
        elif c in ("mktcap", "mkt cap", "market cap", "market_cap"):
            rename_map[col] = "MktCap"
        elif c.startswith("roe"):
            rename_map[col] = "ROE"
    return df.rename(columns=rename_map)


def _get_row_val(row, key, default=None):
    """Ambil nilai dari Series row secara aman."""
    try:
        v = row.get(key, default)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return default
        return v
    except Exception:
        return default


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — INFO EX-DATE
# ─────────────────────────────────────────────────────────────────────────────

def _get_exdate_info(info: dict) -> dict:
    """
    Ambil ex-dividend date dari yfinance info dan hitung jarak ke hari ini.
    Return dict: {ex_date_str, days_diff, status, warna, pesan}
    """
    today = datetime.now(_TZ_WIB).date()
    ex_ts = info.get("exDividendDate")

    if not ex_ts:
        return {
            "ex_date_str": "N/A",
            "days_diff":   None,
            "status":      "unknown",
            "warna":       "#9E9E9E",
            "pesan":       "Ex-date tidak tersedia",
        }

    try:
        ex_date = pd.Timestamp(ex_ts, unit="s").date()
        diff    = (ex_date - today).days   # positif = belum, negatif = sudah lewat

        ex_date_str = ex_date.strftime("%d %b %Y")

        if diff > 0 and diff <= EXDATE_WARN_BEFORE:
            status = "menjelang"
            warna  = "#FF9800"
            pesan  = (f"⚠️ Ex-date {ex_date_str} ({diff} hari lagi) — "
                      f"waspada dividend trap: harga sering terkoreksi setelah ex-date")
        elif diff > EXDATE_WARN_BEFORE:
            status = "jauh"
            warna  = "#00C853"
            pesan  = f"Ex-date {ex_date_str} ({diff} hari lagi)"
        elif diff == 0:
            status = "hari_ini"
            warna  = "#FF5252"
            pesan  = f"🚨 Hari ini adalah Ex-date! Tidak dapat dividen jika beli hari ini."
        elif diff < 0 and abs(diff) <= EXDATE_WARN_AFTER:
            status = "baru_lewat"
            warna  = "#FF6D00"
            pesan  = (f"⚠️ Ex-date sudah lewat {abs(diff)} hari lalu ({ex_date_str}) — "
                      f"harga mungkin masih dalam fase koreksi pasca ex-date")
        else:
            status = "sudah_lewat"
            warna  = "#9E9E9E"
            pesan  = f"Ex-date terakhir: {ex_date_str} ({abs(diff)} hari lalu)"

        return {
            "ex_date_str": ex_date_str,
            "days_diff":   diff,
            "status":      status,
            "warna":       warna,
            "pesan":       pesan,
        }
    except Exception:
        return {
            "ex_date_str": "N/A",
            "days_diff":   None,
            "status":      "unknown",
            "warna":       "#9E9E9E",
            "pesan":       "Ex-date tidak dapat diparsing",
        }


# ─────────────────────────────────────────────────────────────────────────────
# TAHAP 1 — HARD KNOCKOUT
# ─────────────────────────────────────────────────────────────────────────────

def check_hard_knockout(arrays: dict, info: dict, sektor: str,
                        ticker_row) -> list[str]:
    """
    Periksa semua kondisi hard knockout.
    Return list alasan; kosong = lolos semua.
    """
    alasan = []
    fcf_5y = arrays.get("fcf_5y", [])
    pr_5y  = arrays.get("pr_5y",  [])
    dps_5y = arrays.get("dps_5y", [])

    # ── FCF negatif ≥ 2 tahun berturut-turut ──────────────────────────────
    fcf_valid = _valid_floats(fcf_5y)
    if len(fcf_valid) >= 2:
        negatif_berturut = 0
        for v in reversed(fcf_valid):
            if v < 0:
                negatif_berturut += 1
            else:
                break
        if negatif_berturut >= 2:
            alasan.append("FCF negatif ≥ 2 tahun berturut-turut (dividen dibayar dari utang/cadangan)")

    # ── Payout Ratio > 100% dalam 2 tahun terakhir ────────────────────────
    pr_valid = _valid_floats(pr_5y)
    if len(pr_valid) >= 2:
        pr_2_terakhir = pr_valid[-2:]
        if all(v > PAYOUT_RATIO_MAX_KO for v in pr_2_terakhir):
            alasan.append("Payout Ratio > 100% dalam 2 tahun terakhir (membayar melebihi yang diperoleh)")

    # ── Frekuensi dividen < 3x dalam 5 tahun ──────────────────────────────
    dps_valid = _valid_floats(dps_5y)
    frekuensi = sum(1 for v in dps_valid if v > 0)
    if frekuensi < FREQ_MIN_DIVIDEN:
        alasan.append(f"Frekuensi dividen hanya {frekuensi}x dalam 5 tahun (minimum {FREQ_MIN_DIVIDEN}x)")

    sektor_title = str(sektor).strip().title()

    if sektor_title in SEKTOR_BANK:
        # ── CAR & NPL untuk Bank ──────────────────────────────────────────
        car = _safe_float(_get_row_val(ticker_row, "CAR") if ticker_row is not None else None)
        if car is None:
            car = _safe_float(info.get("capitalAdequacyRatio"))
        if car is not None and car < CAR_MIN_BANK:
            alasan.append(f"CAR {car:.1f}% di bawah minimum OJK 8%")

        npl = _safe_float(_get_row_val(ticker_row, "NPL") if ticker_row is not None else None)
        if npl is None:
            npl = _safe_float(info.get("nonPerformingLoan"))
        if npl is not None and npl > NPL_MAX_BANK:
            alasan.append(f"NPL {npl:.1f}% melampaui batas kritis 5%")

    elif sektor_title in SEKTOR_INFRA:
        # ── Debt/EBITDA untuk Infrastruktur ──────────────────────────────
        de = _safe_float(arrays.get("debt_ebitda"))
        if de is None and ticker_row is not None:
            de = _safe_float(_get_row_val(ticker_row, "DebtEBITDA"))
        if de is not None and de > DEBT_EBITDA_MAX_INFRA:
            alasan.append(f"Debt/EBITDA {de:.1f}x melampaui batas aman 5x")

    else:
        # ── DER untuk sektor umum ─────────────────────────────────────────
        der_raw = _safe_float(info.get("debtToEquity"))
        if der_raw is not None:
            der = der_raw / 100.0
            if der > DER_MAX_GENERAL:
                alasan.append(f"DER {der:.2f}x melampaui batas ekstrem 3.0x")

    return alasan


# ─────────────────────────────────────────────────────────────────────────────
# TAHAP 2 — SCORING 100 POIN
# ─────────────────────────────────────────────────────────────────────────────

def _score_dim_a(arrays: dict) -> tuple[int, dict]:
    """
    Dimensi A — Keberlanjutan Earnings & FCF · maks 40 poin.
    Indikator:
      1. AAGR EPS 5 Tahun          (12 poin)
      2. Riwayat FCF Positif       (10 poin)
      3. FCF Payout Ratio rata-rata (5 poin)
      4. Konsistensi Tumbuh EPS    ( 3 poin)
      5. DPS Stability Score       (10 poin)
    """
    detail = {}
    total  = 0

    eps_5y  = arrays.get("eps_5y", [])
    fcf_5y  = arrays.get("fcf_5y", [])
    dps_5y  = arrays.get("dps_5y", [])
    pr_5y   = arrays.get("pr_5y",  [])

    eps_valid = _valid_floats(eps_5y)
    fcf_valid = _valid_floats(fcf_5y)
    dps_valid = _valid_floats(dps_5y)
    pr_valid  = _valid_floats(pr_5y)

    # ── 1. AAGR EPS (12 poin) ─────────────────────────────────────────────
    aagr = None
    if len(eps_valid) >= 2:
        growths = []
        for i in range(1, len(eps_valid)):
            prev = eps_valid[i - 1]
            curr = eps_valid[i]
            if prev > 0 and curr is not None:
                growths.append((curr - prev) / prev)
        if growths:
            aagr = float(np.mean(growths)) * 100
    if aagr is not None:
        poin_aagr = (12 if aagr >= 10 else 9 if aagr >= 7
                     else 6 if aagr >= 5 else 3 if aagr >= 2 else 0)
    else:
        poin_aagr = 0
    detail["aagr_eps"]  = round(aagr, 2) if aagr is not None else None
    detail["poin_aagr"] = poin_aagr
    total += poin_aagr

    # ── 2. Riwayat FCF Positif (10 poin) ──────────────────────────────────
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
    detail["fcf_positif"] = fcf_positif
    detail["poin_fcf"]    = poin_fcf
    total += poin_fcf

    # ── 3. FCF Payout Ratio rata-rata (5 poin) ────────────────────────────
    # Proxy: rata-rata PR_5Y sebagai aproksimasi FCF PR karena
    # shares outstanding tidak tersedia langsung di kolom CSV
    if pr_valid and fcf_valid:
        fcf_pr    = float(np.mean(pr_valid))
        poin_fpr  = (5 if fcf_pr <= 0.60 else 3 if fcf_pr <= 0.80 else 0)
    else:
        fcf_pr    = None
        poin_fpr  = 0
    detail["fcf_pr"]     = round(fcf_pr * 100, 1) if fcf_pr is not None else None
    detail["poin_fpr"]   = poin_fpr
    total += poin_fpr

    # ── 4. Konsistensi Pertumbuhan EPS (3 poin) ───────────────────────────
    eps_tumbuh = 0
    if len(eps_valid) >= 2:
        for i in range(1, len(eps_valid)):
            if eps_valid[i] > eps_valid[i - 1]:
                eps_tumbuh += 1
    poin_konsisten = (3 if eps_tumbuh >= 4 else 1 if eps_tumbuh == 3 else 0)
    detail["eps_tumbuh"]      = eps_tumbuh
    detail["poin_konsisten"]  = poin_konsisten
    total += poin_konsisten

    # ── 5. DPS Stability Score (10 poin) ──────────────────────────────────
    # Hitung jumlah sukses DPS[i] >= DPS[i-1] dari maksimal 4 perbandingan
    dps_stability = 0
    if len(dps_valid) >= 2:
        checks = list(zip(dps_valid[:-1], dps_valid[1:]))[-4:]   # maks 4 perbandingan
        dps_stability = sum(1 for prev, curr in checks if curr >= prev)
    poin_dps_a = (10 if dps_stability == 4
                  else 7 if dps_stability == 3
                  else 4 if dps_stability == 2 else 0)
    detail["dps_stability"]  = dps_stability
    detail["poin_dps_a"]     = poin_dps_a
    total += poin_dps_a

    return min(total, 40), detail


def _score_dim_b(arrays: dict, curr_dy: float | None) -> tuple[int, dict]:
    """
    Dimensi B — Track Record Distribusi Dividen · maks 40 poin.
    Indikator:
      1. Rata-rata DY 5 Tahun   (15 poin)
      2. Rata-rata PR 5 Tahun   (10 poin)
      3. Frekuensi Dividen      ( 5 poin)
      4. AEPD                   ( 5 poin)
      5. DPS Stability B        ( 5 poin)
    """
    detail = {}
    total  = 0

    dy_5y  = arrays.get("dy_5y",  [])
    pr_5y  = arrays.get("pr_5y",  [])
    dps_5y = arrays.get("dps_5y", [])

    dy_valid  = _valid_floats(dy_5y)
    pr_valid  = _valid_floats(pr_5y)
    dps_valid = _valid_floats(dps_5y)

    # ── 1. Rata-rata DY 5 tahun (15 poin) ─────────────────────────────────
    dy_avg = float(np.mean(dy_valid)) * 100 if dy_valid else None
    if dy_avg is not None:
        poin_dy = (15 if dy_avg >= 8
                   else 11 if dy_avg >= 6
                   else 7  if dy_avg >= 4
                   else 3  if dy_avg >= 2 else 0)
    else:
        poin_dy = 0

    # Yield anomaly flag
    anomali_yield = False
    if dy_avg is not None and curr_dy is not None and dy_avg > 0:
        if curr_dy > YIELD_ANOMALY_MULT * dy_avg:
            anomali_yield = True

    detail["dy_avg"]       = round(dy_avg, 2) if dy_avg is not None else None
    detail["poin_dy"]      = poin_dy
    detail["anomali_yield"]= anomali_yield
    total += poin_dy

    # ── 2. Rata-rata PR 5 tahun (10 poin) ─────────────────────────────────
    pr_avg = float(np.mean(pr_valid)) * 100 if pr_valid else None
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

    # ── 3. Frekuensi Dividen (5 poin) ─────────────────────────────────────
    frekuensi = sum(1 for v in dps_valid if v > 0)
    poin_freq = (5 if frekuensi >= 5 else 3 if frekuensi >= 3 else 0)
    detail["frekuensi"]  = frekuensi
    detail["poin_freq"]  = poin_freq
    total += poin_freq

    # ── 4. AEPD (5 poin) ──────────────────────────────────────────────────
    aepd = None
    if dy_avg is not None and pr_avg is not None and pr_avg > 0:
        aepd = (10 * (dy_avg / 100)) / (pr_avg / 100)
    poin_aepd = (5 if aepd is not None and aepd >= 2.0
                 else 3 if aepd is not None and aepd >= 1.0 else 0)
    detail["aepd"]      = round(aepd, 2) if aepd is not None else None
    detail["poin_aepd"] = poin_aepd
    total += poin_aepd

    # ── 5. DPS Stability B (5 poin) — gunakan ulang stability count ────────
    # DPS stability count sudah dihitung di Dimensi A; re-hitung di sini
    # karena fungsi ini independen
    dps_stability = 0
    if len(dps_valid) >= 2:
        checks = list(zip(dps_valid[:-1], dps_valid[1:]))[-4:]
        dps_stability = sum(1 for prev, curr in checks if curr >= prev)
    poin_dps_b = (5 if dps_stability == 4
                  else 3 if dps_stability == 3 else 0)
    detail["poin_dps_b"] = poin_dps_b
    total += poin_dps_b

    return min(total, 40), detail


def _score_dim_c(arrays: dict, info: dict) -> tuple[int, dict]:
    """Dimensi C — Momentum Terkini · maks 10 poin."""
    detail   = {}
    eps_5y   = arrays.get("eps_5y", [])
    eps_valid = _valid_floats(eps_5y)

    eps_yoy = None
    if len(eps_valid) >= 2:
        e_curr = eps_valid[-1]
        e_prev = eps_valid[-2]
        if e_prev != 0:
            eps_yoy = ((e_curr - e_prev) / abs(e_prev)) * 100

    if eps_yoy is None:
        eg = _safe_float(info.get("earningsGrowth"))
        if eg is not None:
            eps_yoy = eg * 100

    if eps_yoy is not None:
        poin_c = (10 if eps_yoy >= 10
                  else 7 if eps_yoy >= 5
                  else 4 if eps_yoy >= 0 else 0)
    else:
        poin_c = 0

    detail["eps_yoy"] = round(eps_yoy, 1) if eps_yoy is not None else None
    detail["poin_c"]  = poin_c
    return poin_c, detail


def _score_dim_d(arrays: dict, info: dict, sektor: str,
                 ticker_row) -> tuple[int, dict]:
    """Dimensi D — Kesehatan Balance Sheet · maks 10 poin."""
    detail       = {}
    total        = 0
    sektor_title = str(sektor).strip().title()

    if sektor_title in SEKTOR_BANK:
        car = _safe_float(_get_row_val(ticker_row, "CAR") if ticker_row is not None else None)
        if car is None:
            car = _safe_float(info.get("capitalAdequacyRatio"))
        poin_car = (5 if car is not None and car >= 17
                    else 3 if car is not None and car >= 14
                    else 1 if car is not None and car >= 8 else 0)
        detail["car"]      = car
        detail["poin_car"] = poin_car
        total += poin_car

        npl = _safe_float(_get_row_val(ticker_row, "NPL") if ticker_row is not None else None)
        if npl is None:
            npl = _safe_float(info.get("nonPerformingLoan"))
        poin_npl = (5 if npl is not None and npl < 2
                    else 3 if npl is not None and npl <= 5 else 0)
        detail["npl"]      = npl
        detail["poin_npl"] = poin_npl
        total += poin_npl

    elif sektor_title in SEKTOR_INFRA:
        de = _safe_float(arrays.get("debt_ebitda"))
        if de is None and ticker_row is not None:
            de = _safe_float(_get_row_val(ticker_row, "DebtEBITDA"))
        poin_de = (5 if de is not None and de <= 3
                   else 3 if de is not None and de <= 5 else 0)
        detail["debt_ebitda"] = de
        detail["poin_de"]     = poin_de
        total += poin_de

        icr = _safe_float(arrays.get("icr"))
        if icr is None and ticker_row is not None:
            icr = _safe_float(_get_row_val(ticker_row, "ICR"))
        if icr is None:
            ebit    = _safe_float(info.get("ebit"))
            int_exp = _safe_float(info.get("interestExpense"))
            if ebit is not None and int_exp and int_exp != 0:
                icr = abs(ebit / int_exp)
        poin_icr = (5 if icr is not None and icr >= 3
                    else 3 if icr is not None and icr >= 1.5 else 0)
        detail["icr"]      = icr
        detail["poin_icr"] = poin_icr
        total += poin_icr

    else:
        der_raw = _safe_float(info.get("debtToEquity"))
        der     = (der_raw / 100.0) if der_raw is not None else None
        poin_der = (5 if der is not None and der <= 0.5
                    else 3 if der is not None and der <= 1.5
                    else 1 if der is not None and der <= 3.0 else 0)
        detail["der"]      = round(der, 2) if der is not None else None
        detail["poin_der"] = poin_der
        total += poin_der

        icr = _safe_float(arrays.get("icr"))
        if icr is None and ticker_row is not None:
            icr = _safe_float(_get_row_val(ticker_row, "ICR"))
        if icr is None:
            ebit    = _safe_float(info.get("ebit"))
            int_exp = _safe_float(info.get("interestExpense"))
            if ebit is not None and int_exp and int_exp != 0:
                icr = abs(ebit / int_exp)
        poin_icr = (5 if icr is not None and icr >= 5
                    else 3 if icr is not None and icr >= 3
                    else 1 if icr is not None and icr >= 1.5 else 0)
        detail["icr"]      = icr
        detail["poin_icr"] = poin_icr
        total += poin_icr

    return min(total, 10), detail


def _hitung_forward_yield(arrays: dict, info: dict, curr_price: float) -> dict | None:
    """Proyeksi forward DY berbasis blended AAGR + YoY EPS dan PR historis."""
    eps_5y  = arrays.get("eps_5y", [])
    pr_5y   = arrays.get("pr_5y",  [])
    eps_valid = _valid_floats(eps_5y)
    pr_valid  = _valid_floats(pr_5y)

    if not eps_valid or not pr_valid or curr_price <= 0:
        return None

    eps_last = eps_valid[-1]
    if eps_last <= 0:
        return None

    pr_avg = float(np.mean(pr_valid))

    aagr = 0.0
    if len(eps_valid) >= 2:
        growths = []
        for i in range(1, len(eps_valid)):
            if eps_valid[i - 1] > 0:
                growths.append((eps_valid[i] - eps_valid[i - 1]) / eps_valid[i - 1])
        aagr = float(np.mean(growths)) if growths else 0.0

    eps_yoy = 0.0
    if len(eps_valid) >= 2 and eps_valid[-2] > 0:
        eps_yoy = (eps_valid[-1] - eps_valid[-2]) / abs(eps_valid[-2])
    else:
        eg = _safe_float(info.get("earningsGrowth"))
        if eg is not None:
            eps_yoy = eg

    eps_fwd = (eps_last * (1 + aagr) + eps_last * (1 + eps_yoy)) / 2
    dps_fwd = eps_fwd * pr_avg
    dy_fwd  = (dps_fwd / curr_price) * 100

    label = ("🟢 Sangat Layak" if dy_fwd >= 10
             else "🟡 Layak"   if dy_fwd >= 6
             else "🔴 Kurang Layak")

    return {
        "eps_fwd": round(eps_fwd, 2),
        "dps_fwd": round(dps_fwd, 2),
        "dy_fwd":  round(dy_fwd, 2),
        "label":   label,
    }


def _label_kelayakan(skor: int) -> tuple[str, str]:
    """Return (label_teks, warna_hex) berdasarkan skor."""
    if skor >= 80:
        return "⭐ Prima",       "#FFD600"
    elif skor >= 65:
        return "✅ Layak",        "#00C853"
    elif skor >= 50:
        return "⚠️ Perhatikan",  "#FF9800"
    else:
        return "❌ Tidak Layak",  "#D50000"


# ─────────────────────────────────────────────────────────────────────────────
# WORKER — PROSES SATU TICKER
# ─────────────────────────────────────────────────────────────────────────────

def process_single_hdy(
    ticker: str,
    df_universe: pd.DataFrame,
) -> dict | None:
    """
    Proses satu ticker untuk screening HDY.
    Return dict hasil lengkap atau None jika tidak lolos / error.
    """
    ticker_bersih = ticker.replace(".JK", "")

    try:
        # ── Ambil data dari universe ──────────────────────────────────────
        ticker_row = get_ticker_row(ticker_bersih, df_universe)
        if ticker_row is None:
            return None

        sektor  = str(_get_row_val(ticker_row, "Sektor", "Lainnya"))
        syariah = str(_get_row_val(ticker_row, "Syariah", "Tidak"))

        # ── Build arrays HDY dari liquid_dividend_stocks ──────────────────
        arrays = {
            "eps_5y":      _parse_json_col(_get_row_val(ticker_row, "EPS_5Y")),
            "dps_5y":      _parse_json_col(_get_row_val(ticker_row, "DPS_5Y")),
            "fcf_5y":      _parse_json_col(_get_row_val(ticker_row, "FCF_5Y")),
            "pr_5y":       _parse_json_col(_get_row_val(ticker_row, "PR_5Y")),
            "dy_5y":       _parse_json_col(_get_row_val(ticker_row, "DY_5Y")),
            "icr":         _safe_float(_get_row_val(ticker_row, "ICR")),
            "debt_ebitda": _safe_float(_get_row_val(ticker_row, "DebtEBITDA")),
        }

        # ── Ambil data live (harga, ex-date, yield current) ───────────────
        stock_data = get_full_stock_data(ticker, interval="1d")
        info       = stock_data.get("info", {})
        history    = stock_data.get("history", pd.DataFrame())

        if history.empty:
            return None

        curr_price = _safe_float(
            info.get("currentPrice")
            or (history["Close"].iloc[-1] if not history.empty else None)
        )
        if curr_price is None or curr_price <= 0:
            return None

        # ── Harga terkini & stale days ────────────────────────────────────
        hist_clean = history[(history["Close"] > 0) & (history["Volume"] > 0)]
        if hist_clean.empty:
            return None

        last_valid_date = pd.to_datetime(hist_clean.index[-1]).date()
        today           = datetime.now(_TZ_WIB).date()
        stale_days      = max((today - last_valid_date).days, 0)

        # ── Dividend yield saat ini ───────────────────────────────────────
        curr_dy = hitung_div_yield_normal(info)  # dalam %

        # ── Hard Knockout ─────────────────────────────────────────────────
        ko_alasan = check_hard_knockout(arrays, info, sektor, ticker_row)
        if ko_alasan:
            return None   # langsung gugur, tidak masuk hasil

        # ── Scoring ───────────────────────────────────────────────────────
        dim_a, detail_a = _score_dim_a(arrays)
        dim_b, detail_b = _score_dim_b(arrays, curr_dy)
        dim_c, detail_c = _score_dim_c(arrays, info)
        dim_d, detail_d = _score_dim_d(arrays, info, sektor, ticker_row)
        skor_total      = min(100, max(0, dim_a + dim_b + dim_c + dim_d))

        label_kls, warna_kls = _label_kelayakan(skor_total)
        forward = _hitung_forward_yield(arrays, info, curr_price)
        exdate  = _get_exdate_info(info)

        # ── DPS terakhir ──────────────────────────────────────────────────
        dps_valid = _valid_floats(arrays["dps_5y"])
        dps_terakhir = dps_valid[-1] if dps_valid else None

        # ── Yield rata-rata 5 tahun ───────────────────────────────────────
        dy_valid = _valid_floats(arrays["dy_5y"])
        dy_avg5  = float(np.mean(dy_valid)) * 100 if dy_valid else None

        return {
            "Ticker":         ticker_bersih,
            "Sektor":         sektor,
            "Syariah":        syariah,
            "Skor":           skor_total,
            "Label":          label_kls,
            "Warna":          warna_kls,
            "Harga":          int(curr_price),
            "DY_Curr":        round(curr_dy, 2),
            "DY_Avg5":        round(dy_avg5, 2) if dy_avg5 else None,
            "DPS_Terakhir":   round(dps_terakhir, 2) if dps_terakhir else None,
            "Forward":        forward,
            "Exdate":         exdate,
            "StaleDays":      stale_days,
            "AnomalyYield":   detail_b.get("anomali_yield", False),
            "DimA":           dim_a,
            "DimB":           dim_b,
            "DimC":           dim_c,
            "DimD":           dim_d,
            "DetailA":        detail_a,
            "DetailB":        detail_b,
            "DetailC":        detail_c,
            "DetailD":        detail_d,
            "Arrays":         arrays,
            "Info":           info,
        }

    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR FILTER
# ─────────────────────────────────────────────────────────────────────────────

def apply_sidebar_filters_hdy(
    ticker_list: list[str],
    df_universe: pd.DataFrame,
) -> list[str]:
    """Terapkan filter sektor, syariah, MktCap dari sidebar."""
    if df_universe.empty:
        return ticker_list

    if "Sektor" in df_universe.columns:
        semua_sektor   = sorted(df_universe["Sektor"].dropna().unique().tolist())
        pilihan_sektor = st.sidebar.multiselect(
            "Filter Sektor", semua_sektor, default=semua_sektor,
        )
    else:
        pilihan_sektor = []

    only_syariah = st.sidebar.checkbox("Hanya Saham Syariah", value=False)

    if "MktCap" in df_universe.columns:
        semua_mktcap   = sorted(df_universe["MktCap"].dropna().unique().tolist())
        pilihan_mktcap = st.sidebar.multiselect(
            "Filter Market Cap", semua_mktcap, default=semua_mktcap,
        )
    else:
        pilihan_mktcap = []

    dy_min = st.sidebar.slider(
        "Minimum DY Saat Ini (%)", min_value=0.0, max_value=20.0, value=0.0, step=0.5,
    )
    score_min = st.sidebar.slider(
        "Minimum Skor HDY", min_value=0, max_value=100, value=50, step=5,
    )

    filtered = []
    for ticker_jk in ticker_list:
        t    = ticker_jk.replace(".JK", "")
        mask = df_universe["Kode Saham"].astype(str).str.strip() == t
        rows = df_universe[mask]
        if rows.empty:
            filtered.append(ticker_jk)
            continue
        row = rows.iloc[0]
        if pilihan_sektor and "Sektor" in row.index:
            if row["Sektor"] not in pilihan_sektor:
                continue
        if only_syariah and "Syariah" in row.index:
            if str(row["Syariah"]).strip().lower() not in ("ya", "yes", "true", "1"):
                continue
        if pilihan_mktcap and "MktCap" in row.index:
            if row["MktCap"] not in pilihan_mktcap:
                continue
        filtered.append(ticker_jk)

    # Simpan filter skor & DY ke session state untuk dipakai post-processing
    st.session_state["hdy_filter_score_min"] = score_min
    st.session_state["hdy_filter_dy_min"]    = dy_min

    return filtered


# ─────────────────────────────────────────────────────────────────────────────
# PDF EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def export_to_pdf_hdy(
    top5: list[dict],
    watchlist: list[dict],
    logo_path: str = "logo_expert_stock_pro.png",
) -> bytes:
    """Generate laporan PDF screening HDY."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── Header ──────────────────────────────────────────────────────────────
    pdf.set_fill_color(20, 20, 20)
    pdf.rect(0, 0, 210, 25, "F")

    if not os.path.exists(logo_path):
        logo_path = "../logo_expert_stock_pro.png"
    if os.path.exists(logo_path):
        pdf.set_fill_color(218, 165, 32)
        pdf.rect(10, 3, 19, 19, "F")
        pdf.image(logo_path, x=10.5, y=3.5, w=18, h=18)

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 15)
    pdf.set_xy(35, 8)
    pdf.cell(0, 10, "Expert Stock Pro - Screening HDY Pro", ln=True)
    pdf.set_y(28)

    pdf.set_font("Arial", "I", 10)
    pdf.set_text_color(0, 0, 255)
    pdf.cell(0, 5, "Sumber: https://s.id/pintarsaham", ln=True, align="C",
             link="https://s.id/pintarsaham")
    pdf.ln(2)

    waktu_cetak = datetime.now(_TZ_WIB).strftime("%d-%m-%Y %H:%M WIB")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 6, _safe_latin1(f"Dicetak: {waktu_cetak}"), ln=True, align="R")
    pdf.set_font("Arial", "I", 9)
    pdf.cell(0, 5,
             "Strategi: High Dividend Yield (HDY) | Sumber: liquid_dividend_stocks.csv",
             ln=True, align="C")
    pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
    pdf.ln(5)

    # ── Top 5 ──────────────────────────────────────────────────────────────
    pdf.set_fill_color(220, 235, 255)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(190, 8, "  A. TOP 5 PRIORITAS DIVIDEN", 0, ln=True, fill=True)
    pdf.ln(2)

    for item in top5:
        pdf.set_font("Arial", "B", 10)
        fwd_str = (f"| FwdDY: {item['Forward']['dy_fwd']:.1f}%"
                   if item.get("Forward") else "")
        pdf.cell(190, 6, _safe_latin1(
            f"{item['Ticker']} - {item['Sektor']} | {item['Label']} | "
            f"Skor: {item['Skor']}/100 {fwd_str}"
        ), ln=True)
        pdf.set_font("Arial", "", 9)
        pdf.cell(60, 5, _safe_latin1(f"Harga: Rp {format_rp(item['Harga'])}"), 0)
        pdf.set_text_color(0, 128, 0)
        pdf.cell(65, 5, _safe_latin1(
            f"DY Saat Ini: {item['DY_Curr']:.2f}%"
            + (f" | Avg5Y: {item['DY_Avg5']:.2f}%" if item['DY_Avg5'] else "")
        ), 0)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(65, 5,
                 _safe_latin1(f"Ex-Date: {item['Exdate']['ex_date_str']}"), ln=True)
        pdf.set_font("Arial", "I", 8)
        pdf.cell(190, 4,
                 _safe_latin1(f"Ex-Date Note: {item['Exdate']['pesan']}"), ln=True)
        if item.get("AnomalyYield"):
            pdf.set_text_color(200, 100, 0)
            pdf.cell(190, 4,
                     "Yield Anomaly: Yield saat ini jauh di atas rata-rata historis",
                     ln=True)
            pdf.set_text_color(0, 0, 0)
        pdf.line(10, pdf.get_y() + 1, 200, pdf.get_y() + 1)
        pdf.ln(3)

    # ── Watchlist ─────────────────────────────────────────────────────────
    if watchlist:
        pdf.ln(3)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(190, 8, "  B. WATCHLIST (RANK 6-20)", 0, ln=True, fill=True)
        pdf.ln(2)
        for w in watchlist:
            pdf.set_font("Arial", "B", 9)
            pdf.cell(190, 5, _safe_latin1(
                f"{w['Ticker']} ({w['Sektor'][:20]}) | {w['Label']} | "
                f"Skor: {w['Skor']} | DY: {w['DY_Curr']:.1f}%"
                + (f" | Avg5Y: {w['DY_Avg5']:.1f}%" if w['DY_Avg5'] else "")
            ), ln=True)
            pdf.set_font("Arial", "I", 7)
            pdf.cell(190, 4,
                     _safe_latin1(f"Ex-Date: {w['Exdate']['pesan']}"), ln=True)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)

    # ── Disclaimer ────────────────────────────────────────────────────────
    pdf.ln(5)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(190, 5, "DISCLAIMER:", ln=True)
    pdf.set_font("Arial", "I", 7)
    pdf.multi_cell(190, 4, _safe_latin1(
        "Laporan ini dihasilkan secara otomatis menggunakan algoritma scoring HDY. "
        "Bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk membeli/menjual saham. "
        "Keputusan investasi sepenuhnya menjadi tanggung jawab pribadi investor. "
        "Selalu lakukan DYOR dan terapkan manajemen risiko."
    ))

    try:
        out = pdf.output(dest="S")
        return out.encode("latin-1") if isinstance(out, str) else bytes(out)
    except Exception:
        return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_screening_hdy() -> None:
    """Entry point modul Screening HDY — dipanggil dari app.py."""

    # ── Load universe ─────────────────────────────────────────────────────
    ticker_list, df_universe = load_universe_hdy()

    if not ticker_list:
        st.error(
            "❌ `liquid_dividend_stocks.csv` tidak ditemukan atau kosong. "
            "Jalankan enrichment profil **Dividen** di Panel Admin terlebih dahulu, "
            "lalu upload hasilnya ke folder `/data` di GitHub."
        )
        st.stop()

    # ── Sidebar info & filter ─────────────────────────────────────────────
    st.sidebar.success(
        f"Universe HDY: **{len(ticker_list)} saham** dari `liquid_dividend_stocks.csv`"
    )
    ticker_list = apply_sidebar_filters_hdy(ticker_list, df_universe)

    if not ticker_list:
        st.warning("Tidak ada saham yang cocok dengan filter yang dipilih.")
        st.stop()

    # ── Judul ─────────────────────────────────────────────────────────────
    st.markdown(
        "<h1 style='text-align:center;'>💰 Screening Saham High Dividend Yield Pro</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:#90CAF9;'>"
        "Menyaring saham terbaik untuk strategi dividend investing jangka panjang."
        "</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    with st.expander("📖 Cara Membaca Hasil Screening HDY"):
        st.markdown("""
        **Skor HDY 100 Poin** dihitung dari 4 dimensi:
        - **Dimensi A (40 poin):** Keberlanjutan Earnings & FCF — apakah laba dan arus kas cukup untuk membiayai dividen ke depan
        - **Dimensi B (40 poin):** Track Record Distribusi — rekam jejak pembayaran dividen historis
        - **Dimensi C (10 poin):** Momentum Terkini — pertumbuhan EPS tahun terakhir
        - **Dimensi D (10 poin):** Kesehatan Balance Sheet — leverage dan kemampuan bayar utang

        **Label Kelayakan:**
        ⭐ Prima (≥80) | ✅ Layak (65-79) | ⚠️ Perhatikan (50-64) | ❌ Tidak Layak (<50)

        **Ex-Date Warning:**
        Beli saham *sebelum* cum-date (1 hari bursa sebelum ex-date) untuk mendapat dividen.
        Harga sering terkoreksi setelah ex-date — ini bukan sinyal jual otomatis, tapi perlu diantisipasi.
        """)

    # ── Tombol jalankan ───────────────────────────────────────────────────
    if st.button(
        "🚀 JALANKAN SCREENING HDY",
        use_container_width=True,
        type="primary",
    ):
        raw_results   = []
        loading_ph    = st.empty()
        loading_ph.write("### 🔄 Menganalisa saham HDY... Mohon tunggu.")
        status_text   = st.empty()
        progress_bar  = st.progress(0)
        total_saham   = len(ticker_list)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(process_single_hdy, ticker, df_universe): ticker
                for ticker in ticker_list
            }
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                completed += 1
                status_text.text(f"Memeriksa {completed} saham...")
                progress_bar.progress(completed / total_saham)
                result = future.result()
                if result is not None:
                    raw_results.append(result)

        loading_ph.empty()
        status_text.empty()
        progress_bar.empty()

        if not raw_results:
            st.warning(
                "Tidak ada saham yang lolos screening HDY dengan filter saat ini. "
                "Coba perluas filter di sidebar."
            )
            st.stop()

        # ── Post-filter: skor & DY minimum ───────────────────────────────
        score_min = st.session_state.get("hdy_filter_score_min", SCORE_MIN_ENTRY)
        dy_min    = st.session_state.get("hdy_filter_dy_min", 0.0)

        final_results = [
            r for r in raw_results
            if r["Skor"] >= score_min and r["DY_Curr"] >= dy_min
        ]
        final_results.sort(key=lambda x: x["Skor"], reverse=True)

        # ── Stale warning ─────────────────────────────────────────────────
        if final_results:
            max_stale = max(r["StaleDays"] for r in final_results)
            if max_stale >= 2:
                st.warning(
                    f"⚠️ Data {max_stale} hari tertinggal — kemungkinan libur bursa. "
                    f"Harga dan DY yang ditampilkan adalah data candle terakhir yang valid."
                )

        st.session_state["hdy_results"]      = final_results
        st.session_state["hdy_raw_results"]  = raw_results
        st.session_state["hdy_done"]         = True

    # ── TAMPILKAN HASIL ───────────────────────────────────────────────────
    if not st.session_state.get("hdy_done", False):
        return

    final_results = st.session_state.get("hdy_results", [])
    raw_results   = st.session_state.get("hdy_raw_results", [])

    if not final_results:
        st.warning(
            "Tidak ada saham yang memenuhi kriteria minimum (Skor & DY filter). "
            "Turunkan slider filter di sidebar."
        )
        return

    top5      = final_results[:5]
    watchlist = final_results[5:20]

    # ═══════════════════════════════════════════════════════════════════════
    # BAGIAN 1 — MARKET OVERVIEW
    # ═══════════════════════════════════════════════════════════════════════
    st.subheader("📊 Overview Sektor Dividen")

    df_all = pd.DataFrame(raw_results)
    if not df_all.empty and "Sektor" in df_all.columns:
        sector_summary = (
            df_all.groupby("Sektor")
            .agg(Avg_Skor=("Skor", "mean"), Jumlah=("Ticker", "count"))
            .reset_index()
            .sort_values("Avg_Skor", ascending=False)
        )
        col_chart, col_info = st.columns([2, 1])
        with col_chart:
            fig = px.bar(
                sector_summary,
                x="Sektor", y="Avg_Skor",
                color="Avg_Skor", color_continuous_scale="Greens",
                text=sector_summary["Avg_Skor"].apply(lambda v: f"{v:.0f}"),
                title="Rata-rata Skor HDY per Sektor",
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
                font_color="white", height=320,
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        with col_info:
            st.markdown("**Top 3 Sektor Terkuat:**")
            for _, row in sector_summary.head(3).iterrows():
                st.success(f"**{row['Sektor']}** — Avg Skor: {row['Avg_Skor']:.0f}")
            st.markdown(f"**Total lolos KO:** {len(raw_results)} saham")
            st.markdown(f"**Masuk hasil (skor ≥ filter):** {len(final_results)} saham")

    st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # BAGIAN 2 — TOP 5 PRIORITAS
    # ═══════════════════════════════════════════════════════════════════════
    st.header("🏆 Top 5 Prioritas Dividend Investing")

    cols = st.columns(min(len(top5), 5))
    for idx, item in enumerate(top5):
        with cols[idx]:
            warna      = item["Warna"]
            fwd        = item.get("Forward")
            exdate     = item["Exdate"]
            warna_teks = "#000" if warna == "#FFD600" else "#fff"

            # Card header
            st.markdown(
                f"""
                <div style="background:#1e2b3e;border-radius:10px;padding:14px;
                            border:2px solid {warna};text-align:center;
                            margin-bottom:4px;">
                    <div style="font-size:1.3em;font-weight:900;color:white;">
                        {item['Ticker']}
                    </div>
                    <div style="font-size:0.78em;color:#90CAF9;">{item['Sektor']}</div>
                    <div style="margin:6px 0;">
                        <span style="background:{warna};color:{warna_teks};
                                     padding:2px 10px;border-radius:12px;
                                     font-size:0.82em;font-weight:bold;">
                            {item['Label']}
                        </span>
                    </div>
                    <div style="font-size:2em;font-weight:900;color:{warna};">
                        {item['Skor']}
                        <span style="font-size:0.5em;color:#A0A0A0;">/100</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Metrik utama
            st.metric("Harga",        f"Rp {format_rp(item['Harga'])}")
            st.metric("DY Saat Ini",   f"{item['DY_Curr']:.2f}%")
            if item["DY_Avg5"]:
                st.metric("DY Rata-rata 5Y", f"{item['DY_Avg5']:.2f}%")
            if fwd:
                st.metric("Forward DY",
                          f"{fwd['dy_fwd']:.2f}%",
                          delta=fwd["label"].replace("🟢", "").replace("🟡", "").replace("🔴", "").strip())
            if item.get("AnomalyYield"):
                st.warning("⚠️ Yield Anomaly")

            # Ex-date info
            st.markdown(
                f"<div style='font-size:0.8em;padding:6px;background:#1a1a2e;"
                f"border-radius:6px;border-left:3px solid {exdate['warna']};'>"
                f"<b style='color:{exdate['warna']};'>Ex-Date:</b><br>"
                f"<span style='color:#E0E0E0;font-size:0.95em;'>{exdate['ex_date_str']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if exdate["status"] in ("menjelang", "hari_ini", "baru_lewat"):
                st.markdown(
                    f"<div style='font-size:0.75em;color:{exdate['warna']};margin-top:4px;'>"
                    f"{exdate['pesan']}</div>",
                    unsafe_allow_html=True,
                )

            # Dim breakdown mini
            st.markdown(
                f"<div style='font-size:0.75em;color:#607D8B;margin-top:6px;'>"
                f"A:{item['DimA']}/40 B:{item['DimB']}/40 "
                f"C:{item['DimC']}/10 D:{item['DimD']}/10"
                f"</div>",
                unsafe_allow_html=True,
            )
            if item["Syariah"].lower() in ("ya", "yes"):
                st.markdown("🕌 **Syariah**")

    # ═══════════════════════════════════════════════════════════════════════
    # BAGIAN 3 — WATCHLIST (rank 6–20)
    # ═══════════════════════════════════════════════════════════════════════
    if watchlist:
        st.markdown("---")
        st.subheader(f"📋 Watchlist HDY — Rank 6 s.d. {min(20, 5 + len(watchlist))}")

        df_watch = pd.DataFrame([{
            "Rank":           idx + 6,
            "Ticker":         w["Ticker"],
            "Sektor":         w["Sektor"],
            "Syariah":        "Ya" if w["Syariah"].lower() in ("ya", "yes") else "Tidak",
            "Label":          w["Label"],
            "Skor":           w["Skor"],
            "Harga (Rp)":     w["Harga"],
            "DY Saat Ini (%)":w["DY_Curr"],
            "DY Avg 5Y (%)":  w["DY_Avg5"] if w["DY_Avg5"] else "N/A",
            "Fwd DY (%)":     w["Forward"]["dy_fwd"] if w.get("Forward") else "N/A",
            "Fwd Label":      w["Forward"]["label"] if w.get("Forward") else "N/A",
            "Ex-Date":        w["Exdate"]["ex_date_str"],
            "Ex Note":        w["Exdate"]["pesan"],
            "A/B/C/D":        f"{w['DimA']}/{w['DimB']}/{w['DimC']}/{w['DimD']}",
        } for idx, w in enumerate(watchlist)])

        def _color_row(row):
            skor = row["Skor"]
            if skor >= 80:
                c = "background-color:#1a2e1a"
            elif skor >= 65:
                c = "background-color:#1a2a1a"
            elif skor >= 50:
                c = "background-color:#2a2a12"
            else:
                c = "background-color:#2a1212"
            return [c] * len(row)

        st.dataframe(
            df_watch.style.apply(_color_row, axis=1),
            column_config={
                "Skor": st.column_config.ProgressColumn(
                    min_value=0, max_value=100, format="%d",
                ),
                "DY Saat Ini (%)": st.column_config.NumberColumn(format="%.2f%%"),
            },
            use_container_width=True,
            hide_index=True,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # BAGIAN 4 — DETAIL SCORING EKSPANDER
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("🔍 Detail Skor Per Dimensi (Top 5)", expanded=False):
        for item in top5:
            st.markdown(f"#### {item['Ticker']} — Skor: {item['Skor']}/100")
            c1, c2, c3, c4 = st.columns(4)
            da, db, dc, dd = item["DetailA"], item["DetailB"], item["DetailC"], item["DetailD"]
            with c1:
                st.markdown(f"**Dimensi A: {item['DimA']}/40**")
                st.caption(f"AAGR EPS: {da.get('aagr_eps', 'N/A')}% → {da.get('poin_aagr', 0)}pt")
                st.caption(f"FCF Positif: {da.get('fcf_positif', 0)}/5 → {da.get('poin_fcf', 0)}pt")
                st.caption(f"FCF PR avg: {da.get('fcf_pr', 'N/A')}% → {da.get('poin_fpr', 0)}pt")
                st.caption(f"EPS Tumbuh: {da.get('eps_tumbuh', 0)} tahun → {da.get('poin_konsisten', 0)}pt")
                st.caption(f"DPS Stability: {da.get('dps_stability', 0)}/4 → {da.get('poin_dps_a', 0)}pt")
            with c2:
                st.markdown(f"**Dimensi B: {item['DimB']}/40**")
                st.caption(f"DY Avg 5Y: {db.get('dy_avg', 'N/A')}% → {db.get('poin_dy', 0)}pt")
                st.caption(f"PR Avg 5Y: {db.get('pr_avg', 'N/A')}% → {db.get('poin_pr', 0)}pt")
                st.caption(f"Freq Div: {db.get('frekuensi', 0)}/5 → {db.get('poin_freq', 0)}pt")
                st.caption(f"AEPD: {db.get('aepd', 'N/A')} → {db.get('poin_aepd', 0)}pt")
                st.caption(f"DPS Stability B → {db.get('poin_dps_b', 0)}pt")
            with c3:
                st.markdown(f"**Dimensi C: {item['DimC']}/10**")
                st.caption(f"EPS YoY: {dc.get('eps_yoy', 'N/A')}% → {dc.get('poin_c', 0)}pt")
            with c4:
                st.markdown(f"**Dimensi D: {item['DimD']}/10**")
                sektor_t = str(item["Sektor"]).strip().title()
                if sektor_t in SEKTOR_BANK:
                    st.caption(f"CAR: {dd.get('car', 'N/A')}% → {dd.get('poin_car', 0)}pt")
                    st.caption(f"NPL: {dd.get('npl', 'N/A')}% → {dd.get('poin_npl', 0)}pt")
                elif sektor_t in SEKTOR_INFRA:
                    st.caption(f"Debt/EBITDA: {dd.get('debt_ebitda', 'N/A')}x → {dd.get('poin_de', 0)}pt")
                    st.caption(f"ICR: {dd.get('icr', 'N/A')}x → {dd.get('poin_icr', 0)}pt")
                else:
                    st.caption(f"DER: {dd.get('der', 'N/A')}x → {dd.get('poin_der', 0)}pt")
                    st.caption(f"ICR: {dd.get('icr', 'N/A')}x → {dd.get('poin_icr', 0)}pt")
            st.markdown("---")

    # ═══════════════════════════════════════════════════════════════════════
    # EXPORT PDF & DISCLAIMER
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("<br>", unsafe_allow_html=True)
    waktu_str = datetime.now(_TZ_WIB).strftime("%Y%m%d_%H%M")
    pdf_bytes = export_to_pdf_hdy(top5, watchlist)
    st.download_button(
        label="📥 UNDUH LAPORAN SCREENING HDY (PDF)",
        data=pdf_bytes,
        file_name=f"ExpertStockPro_ScreeningHDY_{waktu_str}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    st.markdown("---")
    st.caption(
        "⚠️ **DISCLAIMER:** Hasil screening ini dihasilkan secara otomatis oleh algoritma. "
        "Bukan merupakan rekomendasi beli/jual. Keputusan investasi sepenuhnya tanggung "
        "jawab Anda. Selalu lakukan DYOR dan terapkan manajemen risiko."
    )


if __name__ == "__main__":
    run_screening_hdy()
