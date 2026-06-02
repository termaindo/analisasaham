"""
data_loader.py
==============
Dua tanggung jawab utama:
  1. get_liquid_stocks()      → baca liquid_stocks.csv dari /data (repo lokal)
  2. enrich_and_filter()      → proses enrichment untuk Panel Admin
  3. get_full_stock_data()    → satu pintu fetch yfinance (anti rate-limit)

Tidak ada lagi dependency ke Google Drive API.
liquid_stocks.csv dikelola manual oleh admin: hasil enrichment di-download
lalu di-commit ke folder /data di GitHub.

Profil enrichment:
  - "trading"  : Value_MA20 >= 2M, ROE >= 10%, tanpa enrichment HDY
  - "dividen"  : Value_MA20 >= 500jt, ROE >= 5%, dengan enrichment HDY
    (EPS_5Y, DPS_5Y, FCF_5Y, PR_5Y, DY_5Y, ICR, DebtEBITDA)
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import os
from bs4 import BeautifulSoup

# ── Path konstanta ────────────────────────────────────────────────────────────
_BASE_DIR              = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRE_LIQUID_PATH        = os.path.join(_BASE_DIR, "data", "pre_liquid_stocks.csv")
LIQUID_PATH            = os.path.join(_BASE_DIR, "data", "liquid_stocks.csv")
LIQUID_DIVIDEND_PATH   = os.path.join(_BASE_DIR, "data", "liquid_dividend_stocks.csv")

# ── Threshold per profil ──────────────────────────────────────────────────────
_PROFILE_THRESHOLDS = {
    "trading": {"min_value_ma20": 2_000_000_000, "min_roe": 10.0},
    "dividen": {"min_value_ma20":   500_000_000, "min_roe":  5.0},
}

# Sektor yang dihitung DebtEBITDA (sesuai ALUR_DATA.md)
_SEKTOR_DEBT_EBITDA = {"Infrastruktur", "Utilitas"}

# Sektor Bank/Finansial untuk CAR/NPL
_SEKTOR_BANK = {"Bank", "Finansial", "Financial Services"}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER UMUM
# ─────────────────────────────────────────────────────────────────────────────

def hitung_div_yield_normal(info: dict) -> float:
    """Mencegah angka dividen aneh (seperti 409% atau 909%)."""
    raw_yield = info.get("dividendYield")
    if raw_yield is None:
        return 0.0
    return float(raw_yield) if raw_yield > 1 else float(raw_yield * 100)


def scrape_local_financial_data(ticker: str) -> dict:
    """Scrape CAR & NPL dari idnfinancials untuk saham Bank."""
    clean_ticker = ticker.replace(".JK", "")
    headers  = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    scraped  = {"CAR": None, "NPL": None}
    try:
        url  = f"https://www.idnfinancials.com/id/{clean_ticker}/financial-ratios"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup    = BeautifulSoup(resp.text, "html.parser")
            car_row = soup.find(
                string=lambda t: t and ("Capital Adequacy Ratio" in t or "CAR" in t)
            )
            if car_row:
                try:
                    scraped["CAR"] = float(
                        car_row.find_next("td").text.strip()
                        .replace("%", "").replace(",", ".")
                    )
                except Exception:
                    pass
            npl_row = soup.find(
                string=lambda t: t and ("Non-Performing Loan" in t or "NPL" in t)
            )
            if npl_row:
                try:
                    scraped["NPL"] = float(
                        npl_row.find_next("td").text.strip()
                        .replace("%", "").replace(",", ".")
                    )
                except Exception:
                    pass
    except Exception as e:
        print(f"[scrape] Gagal scraping {ticker}: {e}")
    return scraped


def _parse_pct(val) -> float | None:
    """Parse nilai persen dari string/float ke float. None jika gagal."""
    try:
        return float(str(val).replace("%", "").replace(",", ".").strip())
    except Exception:
        return None


def _safe_float(val) -> float | None:
    """Konversi ke float; None jika tidak bisa."""
    try:
        f = float(val)
        return f if not np.isnan(f) else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SATU PINTU DATA YFINANCE  (dipakai semua modul)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def get_full_stock_data(ticker: str, interval: str = "1d") -> dict:
    """
    Ambil semua data yfinance sekaligus untuk satu ticker.
    Cache TTL 1 jam — mencegah rate-limit.
    Mengembalikan dict: info, history, financials, balance_sheet, cashflow, dividends.
    """
    _period_map = {
        "1m":  "7d",   "2m":  "60d",  "5m":  "60d",
        "15m": "60d",  "30m": "60d",  "60m": "730d",
        "90m": "60d",  "1h":  "730d",
        "1d":  "2y",   "5d":  "2y",   "1wk": "5y",
        "1mo": "10y",  "3mo": "10y",
    }
    period = _period_map.get(interval, "2y")
    stock  = yf.Ticker(ticker)

    data: dict = {
        "info":          {},
        "history":       pd.DataFrame(),
        "financials":    pd.DataFrame(),
        "balance_sheet": pd.DataFrame(),
        "cashflow":      pd.DataFrame(),
        "dividends":     pd.Series(dtype="float64"),
    }

    try:
        df = stock.history(period=period, interval=interval)
        if not df.empty:
            df.index    = df.index.tz_localize(None)
            data["history"] = df
    except Exception:
        pass

    try:
        info     = stock.info
        industry = info.get("industry", "")
        sector   = info.get("sector", "")
        if "Bank" in industry or sector == "Financial Services":
            local = scrape_local_financial_data(ticker)
            info["capitalAdequacyRatio"] = (
                local["CAR"] if local["CAR"] is not None else 18.0
            )
            info["nonPerformingLoan"] = (
                local["NPL"] if local["NPL"] is not None else 2.5
            )
        data["info"] = info

        divs = stock.dividends
        if divs.empty and "Dividends" in stock.actions:
            divs = stock.actions["Dividends"]
        data["dividends"] = divs
    except Exception:
        pass

    try:
        data["financials"]    = stock.financials
        data["balance_sheet"] = stock.balance_sheet
        data["cashflow"]      = stock.cashflow
    except Exception:
        pass

    return data


# ─────────────────────────────────────────────────────────────────────────────
# BACA INPUT & LIQUID STOCKS
# ─────────────────────────────────────────────────────────────────────────────

def get_pre_liquid_stocks() -> pd.DataFrame:
    """
    Membaca data/pre_liquid_stocks.csv dengan auto-detect separator (, atau ;)
    Dibuat untuk mencegah error kolom bersatu akibat format Excel Indonesia.
    """
    if not os.path.exists(PRE_LIQUID_PATH):
        return pd.DataFrame()
    try:
        # sep=None dan engine='python' membuat pandas mendeteksi otomatis , atau ;
        df = pd.read_csv(PRE_LIQUID_PATH, sep=None, engine='python')
        return df
    except Exception as e:
        print(f"[get_pre_liquid_stocks] Gagal baca {PRE_LIQUID_PATH}: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def get_liquid_stocks() -> pd.DataFrame:
    """
    Baca liquid_stocks.csv dari folder /data di repo lokal.
    """
    if not os.path.exists(LIQUID_PATH):
        return pd.DataFrame()
    try:
        df = pd.read_csv(LIQUID_PATH, sep=None, engine='python')
        return df
    except Exception as e:
        print(f"[get_liquid_stocks] Gagal baca {LIQUID_PATH}: {e}")
        return pd.DataFrame()


def clear_liquid_stocks_cache() -> None:
    """Panggil setelah admin selesai upload liquid_stocks.csv ke GitHub."""
    get_liquid_stocks.clear()


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def get_liquid_dividend_stocks() -> pd.DataFrame:
    """
    Baca liquid_dividend_stocks.csv dari folder /data di repo lokal.
    """
    if not os.path.exists(LIQUID_DIVIDEND_PATH):
        return pd.DataFrame()
    try:
        df = pd.read_csv(LIQUID_DIVIDEND_PATH, sep=None, engine='python')
        return df
    except Exception as e:
        print(f"[get_liquid_dividend_stocks] Gagal baca {LIQUID_DIVIDEND_PATH}: {e}")
        return pd.DataFrame()


def clear_liquid_dividend_stocks_cache() -> None:
    """Panggil setelah admin selesai upload liquid_dividend_stocks.csv ke GitHub."""
    get_liquid_dividend_stocks.clear()


# ─────────────────────────────────────────────────────────────────────────────
# HELPER LOOKUP  (dipakai screening.py dan modul lain)
# ─────────────────────────────────────────────────────────────────────────────

def get_ticker_row(ticker_bersih: str, df: pd.DataFrame) -> pd.Series | None:
    """
    Ambil satu baris dari liquid_stocks atau pre_liquid DataFrame.
    """
    if df.empty:
        return None
    col = (
        "Ticker"      if "Ticker"      in df.columns else
        "Kode Saham"  if "Kode Saham"  in df.columns else
        None
    )
    if col is None:
        return None
    mask = (
        df[col].astype(str)
        .str.replace(".JK", "", regex=False)
        .str.strip() == ticker_bersih
    )
    rows = df[mask]
    return rows.iloc[0] if not rows.empty else None


def get_value_ma20(ticker_bersih: str, df: pd.DataFrame) -> float | None:
    """Ambil Value_MA20 dari liquid_stocks DataFrame. None jika tidak ada."""
    row = get_ticker_row(ticker_bersih, df)
    if row is None:
        return None
    val = row.get("Value_MA20")
    return float(val) if val is not None and not pd.isna(val) else None


def is_ticker_liquid(ticker_bersih: str, df: pd.DataFrame) -> bool:
    """Cek apakah ticker ada di liquid_stocks."""
    return get_ticker_row(ticker_bersih, df) is not None


# ─────────────────────────────────────────────────────────────────────────────
# NORMALISASI KOLOM  (untuk admin panel)
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalisasi nama kolom agar konsisten terlepas dari variasi input CSV."""
    df = df.copy()
    df.columns = df.columns.str.strip()
    rename_map = {}
    for col in df.columns:
        c = col.lower().strip().lstrip("\ufeff")
        if c in ("ticker", "kode saham", "kode", "saham"):
            rename_map[col] = "Ticker"
        elif c in ("sektor", "sector"):
            rename_map[col] = "Sektor"
        elif c in ("syariah",):
            rename_map[col] = "Syariah"
        elif c in ("mktcap", "mkt cap", "market cap", "market_cap"):
            rename_map[col] = "MktCap"
        elif c.startswith("roe"):
            rename_map[col] = "ROE"
        elif c.startswith("roa"):
            rename_map[col] = "ROA"
        elif c.startswith("npm") or "profit margin" in c:
            rename_map[col] = "NPM"
    return df.rename(columns=rename_map)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER ENRICHMENT HDY
# ─────────────────────────────────────────────────────────────────────────────

def _get_annual_close_prices(hist: pd.DataFrame) -> dict[int, float]:
    """
    Ambil harga Close akhir tahun dari history harian.
    Return: {tahun: close_akhir_tahun}
    """
    if hist.empty or "Close" not in hist.columns:
        return {}
    df = hist.copy()
    df.index = pd.to_datetime(df.index)
    result = {}
    for year, group in df.groupby(df.index.year):
        result[int(year)] = float(group["Close"].iloc[-1])
    return result


def _build_5y_array(
    annual_data: dict[int, float | None],
    ref_year: int,
) -> list:
    """
    Bangun array 5 elemen [t-4, t-3, t-2, t-1, t0] dari dict {tahun: nilai}.
    """
    return [annual_data.get(ref_year - (4 - i)) for i in range(5)]


def _enrich_hdy(
    ticker: str,
    sektor: str,
    data: dict,
) -> dict:
    """
    Hitung kolom HDY untuk satu ticker:
      EPS_5Y, DPS_5Y, FCF_5Y, PR_5Y, DY_5Y, ICR, DebtEBITDA
    """
    result = {
        "EPS_5Y":      None,
        "DPS_5Y":      None,
        "FCF_5Y":      None,
        "PR_5Y":       None,
        "DY_5Y":       None,
        "ICR":         None,
        "DebtEBITDA":  None,
    }

    info      = data.get("info", {})
    hist      = data.get("history", pd.DataFrame())
    fin       = data.get("financials", pd.DataFrame())
    cashflow  = data.get("cashflow", pd.DataFrame())
    dividends = data.get("dividends", pd.Series(dtype="float64"))

    ref_year = pd.Timestamp.now().year - 1

    # ── EPS_5Y ────────────────────────────────────────────────────────────────
    try:
        eps_annual: dict[int, float | None] = {}
        shares = _safe_float(info.get("sharesOutstanding"))
        if not fin.empty and shares and shares > 0:
            ni_row = None
            for k in ["Normalized Income", "Net Income", "NetIncome",
                      "Net Income Common Stockholders"]:
                if k in fin.index:
                    ni_row = fin.loc[k]
                    break
            if ni_row is not None:
                for col in ni_row.index:
                    try:
                        year = pd.Timestamp(col).year
                        val  = _safe_float(ni_row[col])
                        eps_annual[year] = val / shares if val is not None else None
                    except Exception:
                        pass
        result["EPS_5Y"] = json.dumps(_build_5y_array(eps_annual, ref_year))
    except Exception:
        result["EPS_5Y"] = json.dumps([None] * 5)

    # ── DPS_5Y ────────────────────────────────────────────────────────────────
    # PERBAIKAN: stock.dividends yfinance sudah berbentuk nominal PER LEMBAR SAHAM. Jangan dibagi shares lagi.
    try:
        dps_annual: dict[int, float | None] = {}
        if not dividends.empty:
            divs = dividends.copy()
            divs.index = pd.to_datetime(divs.index)
            for year, group in divs.groupby(divs.index.year):
                dps_annual[int(year)] = float(group.sum())
        result["DPS_5Y"] = json.dumps(_build_5y_array(dps_annual, ref_year))
    except Exception:
        result["DPS_5Y"] = json.dumps([None] * 5)

    # ── FCF_5Y ────────────────────────────────────────────────────────────────
    try:
        fcf_annual: dict[int, float | None] = {}
        if not cashflow.empty:
            fcf_row = None
            for k in ["Free Cash Flow", "FreeCashFlow"]:
                if k in cashflow.index:
                    fcf_row = cashflow.loc[k]
                    break
            if fcf_row is not None:
                for col in fcf_row.index:
                    try:
                        year = pd.Timestamp(col).year
                        fcf_annual[year] = _safe_float(fcf_row[col])
                    except Exception:
                        pass
        result["FCF_5Y"] = json.dumps(_build_5y_array(fcf_annual, ref_year))
    except Exception:
        result["FCF_5Y"] = json.dumps([None] * 5)

    # ── PR_5Y ─────────────────────────────────────────────────────────────────
    try:
        eps_arr = json.loads(result["EPS_5Y"] or "[]")
        dps_arr = json.loads(result["DPS_5Y"] or "[]")
        pr_arr  = []
        for eps_val, dps_val in zip(eps_arr, dps_arr):
            if eps_val is not None and dps_val is not None and eps_val > 0:
                pr_arr.append(round(dps_val / eps_val, 4))
            else:
                pr_arr.append(None)
        result["PR_5Y"] = json.dumps(pr_arr)
    except Exception:
        result["PR_5Y"] = json.dumps([None] * 5)

    # ── DY_5Y ─────────────────────────────────────────────────────────────────
    try:
        dps_arr     = json.loads(result["DPS_5Y"] or "[]")
        annual_close = _get_annual_close_prices(hist)
        dy_arr      = []
        for i, dps_val in enumerate(dps_arr):
            year = ref_year - (4 - i)
            close_val = annual_close.get(year)
            if dps_val is not None and close_val and close_val > 0:
                dy_arr.append(round(dps_val / close_val, 4))
            else:
                dy_arr.append(None)
        result["DY_5Y"] = json.dumps(dy_arr)
    except Exception:
        result["DY_5Y"] = json.dumps([None] * 5)

    # ── ICR ───────────────────────────────────────────────────────────────────
    try:
        ebit     = None
        interest = None
        if not fin.empty:
            for k in ["EBIT", "Ebit", "Operating Income"]:
                if k in fin.index:
                    ebit = _safe_float(fin.loc[k].iloc[0]); break
            for k in ["Interest Expense", "InterestExpense",
                      "Interest Expense Non Operating"]:
                if k in fin.index:
                    raw = _safe_float(fin.loc[k].iloc[0])
                    interest = abs(raw) if raw is not None else None
                    break
        if ebit is not None and interest and interest > 0:
            result["ICR"] = round(ebit / interest, 2)
    except Exception:
        pass

    # ── DebtEBITDA ────────────────────────────────────────────────────────────
    try:
        if sektor in _SEKTOR_DEBT_EBITDA:
            total_debt = _safe_float(info.get("totalDebt"))
            ebitda     = None
            if not fin.empty:
                for k in ["EBITDA", "Ebitda"]:
                    if k in fin.index:
                        ebitda = _safe_float(fin.loc[k].iloc[0]); break
            if total_debt is not None and ebitda and ebitda > 0:
                result["DebtEBITDA"] = round(total_debt / ebitda, 2)
    except Exception:
        pass

    return result


# ─────────────────────────────────────────────────────────────────────────────
# ENRICHMENT & FILTER  (untuk Panel Admin)
# ─────────────────────────────────────────────────────────────────────────────

def enrich_and_filter(
    df_input: pd.DataFrame,
    min_value_ma20: int   = 2_000_000_000,
    min_roe: float        = 10.0,
    profil: str           = "trading",
    progress_callback     = None,
) -> tuple[pd.DataFrame, int, int]:
    """
    Terima DataFrame dari pre_liquid_stocks.csv, proses enrichment, lalu filter.
    """
    df_pre = _normalize_columns(df_input)

    required = ["Ticker", "Sektor", "Syariah", "MktCap"]
    missing  = [r for r in required if r not in df_pre.columns]
    if missing:
        raise ValueError(
            f"Kolom wajib tidak ditemukan setelah normalisasi: {missing}. "
            f"Kolom tersedia: {list(df_pre.columns)}"
        )

    is_dividen = profil.lower() == "dividen"
    records    = []
    total      = len(df_pre)

    for i, row in enumerate(df_pre.itertuples(index=False), start=1):
        ticker_raw = str(row.Ticker).strip().replace(".JK", "")
        ticker     = ticker_raw + ".JK"
        sektor     = row.Sektor
        syariah    = row.Syariah
        mkt_cap    = row.MktCap

        roe_from_file = _parse_pct(getattr(row, "ROE", None)) if hasattr(row, "ROE") else None
        roa_from_file = _parse_pct(getattr(row, "ROA", None)) if hasattr(row, "ROA") else None
        npm_from_file = _parse_pct(getattr(row, "NPM", None)) if hasattr(row, "NPM") else None

        if progress_callback:
            progress_callback(i, total, ticker)

        rec = {
            "Ticker":             ticker_raw,
            "Sektor":             sektor,
            "Syariah":            syariah,
            "MktCap":             mkt_cap,
            "Value_MA20":         None,
            "ROE":                roe_from_file,
            "ROA":                roa_from_file,
            "NPM":                npm_from_file,
            "CAR":                None,
            "NPL":                None,
            "_PER_median_ticker": None,
            "_PBV_median_ticker": None,
            "EPS_5Y":     None,
            "DPS_5Y":     None,
            "FCF_5Y":     None,
            "PR_5Y":      None,
            "DY_5Y":      None,
            "ICR":        None,
            "DebtEBITDA": None,
        }

        try:
            data = get_full_stock_data(ticker, interval="1d")
            info = data["info"]
            hist = data["history"]
            fin  = data["financials"]
            bs   = data["balance_sheet"]

            # ── Value MA20 ────────────────────────────────────────────────────
            if not hist.empty and "Close" in hist.columns and "Volume" in hist.columns:
                h             = hist.copy()
                h["Value"]    = h["Close"] * h["Volume"]
                rec["Value_MA20"] = h["Value"].tail(20).mean()

            # ── ROE & ROA — fetch yfinance jika kosong ────────────────────────
            if rec["ROE"] is None or rec["ROA"] is None:
                try:
                    net_income = total_equity = total_assets = None
                    if not fin.empty:
                        for k in ["Net Income", "NetIncome", "Net Income Common Stockholders"]:
                            if k in fin.index:
                                net_income = fin.loc[k].iloc[0]; break
                    if not bs.empty:
                        for k in ["Stockholders Equity", "Total Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"]:
                            if k in bs.index:
                                total_equity = bs.loc[k].iloc[0]; break
                        for k in ["Total Assets", "TotalAssets"]:
                            if k in bs.index:
                                total_assets = bs.loc[k].iloc[0]; break
                    if rec["ROE"] is None and net_income is not None and total_equity and total_equity != 0:
                        rec["ROE"] = round(float(net_income / total_equity) * 100, 2)
                    if rec["ROA"] is None and net_income is not None and total_assets and total_assets != 0:
                        rec["ROA"] = round(float(net_income / total_assets) * 100, 2)
                except Exception:
                    pass

            # ── CAR & NPL khusus Bank ─────────────────────────────────────────
            industry = info.get("industry", "")
            yf_sector = info.get("sector", "")
            if "Bank" in industry or yf_sector == "Financial Services":
                rec["CAR"] = info.get("capitalAdequacyRatio")
                rec["NPL"] = info.get("nonPerformingLoan")

            # ── Median PER & PBV historis 3 tahun per ticker ──────────────────
            try:
                closes = hist.tail(252 * 3)["Close"] if len(hist) >= 252 else hist["Close"]
                eps  = info.get("trailingEps")
                bvps = info.get("bookValue")
                if eps  and eps  > 0 and not closes.empty:
                    rec["_PER_median_ticker"] = float((closes / eps).median())
                if bvps and bvps > 0 and not closes.empty:
                    rec["_PBV_median_ticker"] = float((closes / bvps).median())
            except Exception:
                pass

            # ── Enrichment HDY — hanya untuk profil dividen ───────────────────
            if is_dividen:
                hdy = _enrich_hdy(ticker, sektor, data)
                rec.update(hdy)

        except Exception as e:
            print(f"[enrich] Gagal fetch {ticker}: {e}")

        records.append(rec)

    df = pd.DataFrame(records)

    # ── Agregasi median PER & PBV per sektor ──────────────────────────────────
    df = df.join(df.groupby("Sektor")["_PER_median_ticker"].median().rename("Median_PER_3Y"), on="Sektor")
    df = df.join(df.groupby("Sektor")["_PBV_median_ticker"].median().rename("Median_PBV_3Y"), on="Sektor")
    df.drop(columns=["_PER_median_ticker", "_PBV_median_ticker"], inplace=True)

    # ── Filter berdasarkan profil ──────────────────────────────────────────────
    before = len(df)
    df = df[df["Value_MA20"].notna() & (df["Value_MA20"] >= min_value_ma20)]
    df = df[df["ROE"].notna()        & (df["ROE"] >= min_roe)]
    df = df[df["ROA"].notna()        & (df["ROA"] > 0)]
    after = len(df)

    if is_dividen:
        hdy_cols = ["EPS_5Y", "DPS_5Y", "FCF_5Y", "PR_5Y", "DY_5Y", "ICR", "DebtEBITDA"]
        for col in hdy_cols:
            if col not in df.columns:
                df[col] = None

    df.reset_index(drop=True, inplace=True)
    return df, before, after


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT UNTUK PANEL ADMIN  (dipanggil app.py Step 2)
# ─────────────────────────────────────────────────────────────────────────────

def process_liquid_stocks(
    df_pre: pd.DataFrame,
    min_value_ma20: int = 2_000_000_000,
    min_roe: float      = 10.0,
    profil: str         = "trading",
) -> pd.DataFrame:
    """
    Dipanggil oleh app.py di Step 2 panel admin.
    """
    df_hasil, before, after = enrich_and_filter(
        df_input      = df_pre,
        min_value_ma20= min_value_ma20,
        min_roe       = min_roe,
        profil        = profil,
    )

    st.info(
        f"📊 Profil: **{profil.upper()}** | "
        f"Total awal: {before} saham → Lolos filter: {after} saham"
    )

    if before > 0 and after == 0:
        st.warning("⚠️ Semua saham dibuang filter. Menampilkan 5 sampel tanpa filter:")
        df_debug, _, _ = enrich_and_filter(
            df_input      = df_pre,
            min_value_ma20= 0,
            min_roe       = -999,
            profil        = profil,
        )
        cols = [c for c in ["Ticker", "Value_MA20", "ROE", "ROA"] if c in df_debug.columns]
        st.dataframe(df_debug[cols].head(5), use_container_width=True)

    return df_hasil
