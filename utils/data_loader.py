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
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import os
from bs4 import BeautifulSoup

# ── Path konstanta ────────────────────────────────────────────────────────────
_BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
PRE_LIQUID_PATH   = os.path.join(_BASE_DIR, "data", "pre_liquid_stocks.csv")
LIQUID_PATH       = os.path.join(_BASE_DIR, "data", "liquid_stocks.csv")

# ─────────────────────────────────────────────────────────────────────────────
# HELPER
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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    scraped = {"CAR": None, "NPL": None}
    try:
        url = f"https://www.idnfinancials.com/id/{clean_ticker}/financial-ratios"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            car_row = soup.find(string=lambda t: t and ("Capital Adequacy Ratio" in t or "CAR" in t))
            if car_row:
                try:
                    scraped["CAR"] = float(
                        car_row.find_next("td").text.strip().replace("%", "").replace(",", ".")
                    )
                except Exception:
                    pass
            npl_row = soup.find(string=lambda t: t and ("Non-Performing Loan" in t or "NPL" in t))
            if npl_row:
                try:
                    scraped["NPL"] = float(
                        npl_row.find_next("td").text.strip().replace("%", "").replace(",", ".")
                    )
                except Exception:
                    pass
    except Exception as e:
        print(f"[scrape] Gagal scraping {ticker}: {e}")
    return scraped


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
        "1m": "7d",  "2m": "60d",  "5m": "60d",
        "15m": "60d", "30m": "60d", "60m": "730d",
        "90m": "60d", "1h": "730d",
        "1d": "2y",  "5d": "2y",  "1wk": "5y",
        "1mo": "10y", "3mo": "10y",
    }
    period = _period_map.get(interval, "2y")
    stock = yf.Ticker(ticker)

    data: dict = {
        "info": {},
        "history": pd.DataFrame(),
        "financials": pd.DataFrame(),
        "balance_sheet": pd.DataFrame(),
        "cashflow": pd.DataFrame(),
        "dividends": pd.Series(dtype="float64"),
    }

    try:
        df = stock.history(period=period, interval=interval)
        if not df.empty:
            df.index = df.index.tz_localize(None)
            data["history"] = df
    except Exception:
        pass

    try:
        info = stock.info
        industry = info.get("industry", "")
        sector = info.get("sector", "")
        if "Bank" in industry or sector == "Financial Services":
            local = scrape_local_financial_data(ticker)
            info["capitalAdequacyRatio"] = local["CAR"] if local["CAR"] is not None else 18.0
            info["nonPerformingLoan"]    = local["NPL"] if local["NPL"] is not None else 2.5
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
# BACA LIQUID STOCKS  (dipakai semua modul)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def get_liquid_stocks() -> pd.DataFrame:
    """
    Baca liquid_stocks.csv dari folder /data di repo lokal.
    Cache TTL 24 jam — cukup untuk frekuensi update mingguan.

    Mengembalikan DataFrame kosong (bukan error) jika file belum ada,
    sehingga modul lain bisa fallback ke pre_liquid_stocks.csv dengan aman.
    """
    if not os.path.exists(LIQUID_PATH):
        # File belum ada → admin belum upload hasil enrichment
        return pd.DataFrame()

    try:
        df = pd.read_csv(LIQUID_PATH)
        return df
    except Exception as e:
        print(f"[get_liquid_stocks] Gagal baca {LIQUID_PATH}: {e}")
        return pd.DataFrame()


def clear_liquid_stocks_cache() -> None:
    """Panggil setelah admin selesai upload liquid_stocks.csv ke GitHub."""
    get_liquid_stocks.clear()


# ─────────────────────────────────────────────────────────────────────────────
# HELPER LOOKUP  (dipakai screening.py dan modul lain)
# ─────────────────────────────────────────────────────────────────────────────

def get_ticker_row(ticker_bersih: str, df: pd.DataFrame) -> pd.Series | None:
    """
    Ambil satu baris dari liquid_stocks atau pre_liquid DataFrame.
    ticker_bersih = kode tanpa .JK (mis: 'BBCA').
    Mengembalikan None jika tidak ditemukan.
    """
    if df.empty:
        return None
    # Coba kolom 'Ticker' dulu, lalu 'Kode Saham'
    col = "Ticker" if "Ticker" in df.columns else ("Kode Saham" if "Kode Saham" in df.columns else None)
    if col is None:
        return None
    mask = df[col].astype(str).str.replace(".JK", "", regex=False).str.strip() == ticker_bersih
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
# ENRICHMENT & FILTER  (untuk Panel Admin)
# ─────────────────────────────────────────────────────────────────────────────

def enrich_and_filter(
    df_input: pd.DataFrame,
    min_value_ma20: int = 2_000_000_000,
    min_roe: float = 10.0,
    progress_callback=None,
) -> tuple[pd.DataFrame, int, int]:
    """
    Terima DataFrame dari pre_liquid_stocks.csv (sudah dinormalisasi),
    fetch data tiap saham dari yfinance, hitung kolom enrichment,
    lalu filter dan kembalikan (df_hasil, total_before, total_after).

    progress_callback(i, total, ticker) → opsional untuk progress bar UI.
    """
    df_pre = _normalize_columns(df_input)

    required = ["Ticker", "Sektor", "Syariah", "MktCap"]
    missing  = [r for r in required if r not in df_pre.columns]
    if missing:
        raise ValueError(
            f"Kolom wajib tidak ditemukan setelah normalisasi: {missing}. "
            f"Kolom tersedia: {list(df_pre.columns)}"
        )

    def parse_pct(val):
        try:
            return float(str(val).replace("%", "").replace(",", ".").strip())
        except Exception:
            return None

    records = []
    total   = len(df_pre)

    for i, row in enumerate(df_pre.itertuples(index=False), start=1):
        ticker_raw = str(row.Ticker).strip().replace(".JK", "")
        ticker     = ticker_raw + ".JK"
        sektor     = row.Sektor
        syariah    = row.Syariah
        mkt_cap    = row.MktCap

        roe_from_file = parse_pct(getattr(row, "ROE", None)) if hasattr(row, "ROE") else None
        roa_from_file = parse_pct(getattr(row, "ROA", None)) if hasattr(row, "ROA") else None
        npm_from_file = parse_pct(getattr(row, "NPM", None)) if hasattr(row, "NPM") else None

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
        }

        try:
            data = get_full_stock_data(ticker, interval="1d")
            info = data["info"]
            hist = data["history"]
            fin  = data["financials"]
            bs   = data["balance_sheet"]

            # Value MA20
            if not hist.empty and "Close" in hist.columns and "Volume" in hist.columns:
                h              = hist.copy()
                h["Value"]     = h["Close"] * h["Volume"]
                rec["Value_MA20"] = h["Value"].tail(20).mean()

            # ROE & ROA — fetch yfinance hanya jika tidak ada di file
            if rec["ROE"] is None or rec["ROA"] is None:
                try:
                    net_income = total_equity = total_assets = None
                    if not fin.empty:
                        for k in ["Net Income", "NetIncome", "Net Income Common Stockholders"]:
                            if k in fin.index:
                                net_income = fin.loc[k].iloc[0]; break
                    if not bs.empty:
                        for k in ["Stockholders Equity", "Total Stockholders Equity",
                                  "Common Stock Equity", "Total Equity Gross Minority Interest"]:
                            if k in bs.index:
                                total_equity = bs.loc[k].iloc[0]; break
                        for k in ["Total Assets", "TotalAssets"]:
                            if k in bs.index:
                                total_assets = bs.loc[k].iloc[0]; break
                    if rec["ROE"] is None and net_income and total_equity and total_equity != 0:
                        rec["ROE"] = round(float(net_income / total_equity) * 100, 2)
                    if rec["ROA"] is None and net_income and total_assets and total_assets != 0:
                        rec["ROA"] = round(float(net_income / total_assets) * 100, 2)
                except Exception:
                    pass

            # CAR & NPL khusus Bank
            if "Bank" in info.get("industry", "") or info.get("sector", "") == "Financial Services":
                rec["CAR"] = info.get("capitalAdequacyRatio")
                rec["NPL"] = info.get("nonPerformingLoan")

            # Median PER & PBV historis 3 tahun per ticker
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

        except Exception as e:
            print(f"[enrich] Gagal fetch {ticker}: {e}")

        records.append(rec)

    df = pd.DataFrame(records)

    # Agregasi median PER & PBV per sektor
    df = df.join(
        df.groupby("Sektor")["_PER_median_ticker"].median().rename("Median_PER_3Y"),
        on="Sektor",
    )
    df = df.join(
        df.groupby("Sektor")["_PBV_median_ticker"].median().rename("Median_PBV_3Y"),
        on="Sektor",
    )
    df.drop(columns=["_PER_median_ticker", "_PBV_median_ticker"], inplace=True)

    # Filter
    before = len(df)
    df = df[df["Value_MA20"].notna() & (df["Value_MA20"] >= min_value_ma20)]
    df = df[df["ROE"].notna()        & (df["ROE"] >= min_roe)]
    df = df[df["ROA"].notna()        & (df["ROA"] > 0)]
    after = len(df)

    df.reset_index(drop=True, inplace=True)
    return df, before, after


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT UNTUK PANEL ADMIN  (dipanggil app.py Step 2)
# ─────────────────────────────────────────────────────────────────────────────

def process_liquid_stocks(
    df_pre: pd.DataFrame,
    min_value_ma20: int = 2_000_000_000,
    min_roe: float = 10.0,
) -> pd.DataFrame:
    """
    Dipanggil oleh app.py di Step 2 panel admin.
    Menerima DataFrame langsung — tanpa file temporary.
    Mengembalikan DataFrame hasil enrichment & filter.
    """
    df_hasil, before, after = enrich_and_filter(
        df_input=df_pre,
        min_value_ma20=min_value_ma20,
        min_roe=min_roe,
    )

    st.info(f"📊 Total awal: {before} saham → Lolos filter: {after} saham")

    if before > 0 and after == 0:
        st.warning("⚠️ Semua saham dibuang filter. Menampilkan 5 sampel tanpa filter:")
        df_debug, _, _ = enrich_and_filter(
            df_input=df_pre,
            min_value_ma20=0,
            min_roe=-999,
        )
        cols = [c for c in ["Ticker", "Value_MA20", "ROE", "ROA"] if c in df_debug.columns]
        st.dataframe(df_debug[cols].head(5), use_container_width=True)

    return df_hasil
