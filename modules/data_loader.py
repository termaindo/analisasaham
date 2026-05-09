import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup

# --- FUNGSI PEMBANTU (Helper) ---
def hitung_div_yield_normal(info):
    """Mencegah angka dividen aneh (seperti 409% atau 909%)"""
    raw_yield = info.get('dividendYield')
    if raw_yield is None: return 0.0
    return float(raw_yield) if raw_yield > 1 else float(raw_yield * 100)

def scrape_local_financial_data(ticker):
    """
    Fungsi untuk menyedot data spesifik (CAR, NPL) dari portal lokal 
    jika yfinance tidak menyediakannya.
    """
    clean_ticker = ticker.replace('.JK', '')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    
    scraped_data = {
        'CAR': None,
        'NPL': None,
    }
    
    try:
        url = f"https://www.idnfinancials.com/id/{clean_ticker}/financial-ratios"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            car_row = soup.find(string=lambda text: text and ('Capital Adequacy Ratio' in text or 'CAR' in text))
            if car_row:
                try:
                    car_value_str = car_row.find_next('td').text.strip()
                    scraped_data['CAR'] = float(car_value_str.replace('%', '').replace(',', '.'))
                except: pass
                
            npl_row = soup.find(string=lambda text: text and ('Non-Performing Loan' in text or 'NPL' in text))
            if npl_row:
                try:
                    npl_value_str = npl_row.find_next('td').text.strip()
                    scraped_data['NPL'] = float(npl_value_str.replace('%', '').replace(',', '.'))
                except: pass
                
    except Exception as e:
        print(f"Peringatan: Gagal melakukan scraping untuk {ticker}. Menggunakan nilai default. Detail: {e}")
        
    return scraped_data

# --- SATU PINTU DATA (Anti-Rate Limit) ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_full_stock_data(ticker, interval='1d'):  # ✅ Parameter interval ditambahkan
    """
    Mengambil semua data sekaligus untuk mencegah error 'Data tidak ditemukan'.
    Sudah terintegrasi dengan scraping khusus sektor perbankan.

    Parameter:
        ticker   : Kode saham (contoh: 'BBCA.JK')
        interval : Interval candle yfinance (default: '1d').
                   Nilai valid: '1m','2m','5m','15m','30m','60m',
                                '90m','1h','1d','5d','1wk','1mo','3mo'
                   Catatan: interval menit hanya tersedia untuk data < 60 hari.
    """

    # Sesuaikan period otomatis berdasarkan interval
    # (interval pendek butuh period lebih singkat agar tidak error di yfinance)
    _period_map = {
        '1m': '7d', '2m': '60d', '5m': '60d',
        '15m': '60d', '30m': '60d', '60m': '730d',
        '90m': '60d', '1h': '730d',
        '1d': '2y', '5d': '2y', '1wk': '5y',
        '1mo': '10y', '3mo': '10y'
    }
    period = _period_map.get(interval, '2y')

    stock = yf.Ticker(ticker)
    data = {
        "info": {},
        "history": pd.DataFrame(),
        "financials": pd.DataFrame(),
        "balance_sheet": pd.DataFrame(),
        "cashflow": pd.DataFrame(),
        "dividends": pd.Series(dtype='float64')
    }

    # 1. Ambil History dengan interval & period yang sesuai
    try:
        df = stock.history(period=period, interval=interval)  # ✅ interval diteruskan ke yfinance
        if not df.empty:
            df.index = df.index.tz_localize(None)
            data["history"] = df
    except: pass

    # 2. Ambil Info, Scraping (jika Bank), & Dividen
    try:
        info = stock.info
        
        industry = info.get('industry', '')
        sector = info.get('sector', '')
        is_bank = 'Bank' in industry or sector == 'Financial Services'
        
        if is_bank:
            local_data = scrape_local_financial_data(ticker)
            info['capitalAdequacyRatio'] = local_data['CAR'] if local_data['CAR'] is not None else 18.0
            info['nonPerformingLoan'] = local_data['NPL'] if local_data['NPL'] is not None else 2.5
        
        data["info"] = info
        
        divs = stock.dividends
        if divs.empty:
            divs = stock.actions['Dividends'] if 'Dividends' in stock.actions else pd.Series(dtype='float64')
        data["dividends"] = divs
    except: pass

    # 3. Ambil Laporan Keuangan, Neraca & Cashflow
    try:
        data["financials"] = stock.financials
        data["balance_sheet"] = stock.balance_sheet
        data["cashflow"] = stock.cashflow
    except: pass

    return data


# --- ENRICHMENT & FILTER (untuk Panel Admin) ---
def enrich_and_filter(pre_csv_path='pre_liquid_stocks.csv',
                      out_csv_path='liquid_stocks.csv',
                      min_value_ma20=2_000_000_000,
                      min_roe=10.0,
                      progress_callback=None):
    """
    Membaca pre_liquid_stocks.csv, fetch data tiap saham, lalu:
      - Hitung Value_MA20, ROE, ROA, CAR (Bank), NPL (Bank)
      - Hitung Median PER & PBV historis 3 tahun per ticker,
        lalu agregasi menjadi median per sektor
      - Filter: Value_MA20 >= min_value_ma20, ROE >= min_roe, ROA > 0
      - Simpan hasilnya ke liquid_stocks.csv

    progress_callback(i, total, ticker) → opsional, untuk progress bar Streamlit.
    """
    df_pre = pd.read_csv(pre_csv_path, sep=None, engine='python')  # auto-detect separator

    # Normalisasi nama kolom (jaga-jaga spasi/kapital berbeda)
    df_pre.columns = df_pre.columns.str.strip()
    col_map = {c: c for c in df_pre.columns}
    # Pastikan kolom wajib ada
    required = ['Kode Saham', 'Sektor', 'Syariah', 'Mkt Cap']
    for r in required:
        if r not in df_pre.columns:
            raise ValueError(f"Kolom '{r}' tidak ditemukan di {pre_csv_path}")

    records = []
    total = len(df_pre)

    for i, row in df_pre.iterrows():
        ticker_raw = str(row['Kode Saham']).strip()
        ticker = ticker_raw if ticker_raw.endswith('.JK') else ticker_raw + '.JK'
        sektor  = row['Sektor']
        syariah = row['Syariah']
        mkt_cap = row['Mkt Cap']

        if progress_callback:
            progress_callback(i, total, ticker)

        rec = {
            'Kode Saham': ticker_raw,
            'Sektor': sektor,
            'Syariah': syariah,
            'Mkt Cap': mkt_cap,
            'Value_MA20': None,
            'ROE': None,
            'ROA': None,
            'CAR': None,
            'NPL': None,
            '_PER_median_ticker': None,   # sementara, untuk agregasi sektoral
            '_PBV_median_ticker': None,
        }

        try:
            data = get_full_stock_data(ticker, interval='1d')
            info = data['info']
            hist = data['history']
            fin  = data['financials']
            bs   = data['balance_sheet']

            # ── Value MA20 ──────────────────────────────────────────────
            if not hist.empty and 'Close' in hist.columns and 'Volume' in hist.columns:
                hist = hist.copy()
                hist['Value'] = hist['Close'] * hist['Volume']
                rec['Value_MA20'] = hist['Value'].tail(20).mean()

            # ── ROE & ROA ────────────────────────────────────────────────
            # ROE = Net Income / Total Equity
            # ROA = Net Income / Total Assets
            try:
                net_income = None
                total_equity = None
                total_assets = None

                if not fin.empty:
                    ni_keys = ['Net Income', 'NetIncome', 'Net Income Common Stockholders']
                    for k in ni_keys:
                        if k in fin.index:
                            net_income = fin.loc[k].iloc[0]
                            break

                if not bs.empty:
                    eq_keys = ['Stockholders Equity', 'Total Stockholders Equity',
                               'Common Stock Equity', 'Total Equity Gross Minority Interest']
                    for k in eq_keys:
                        if k in bs.index:
                            total_equity = bs.loc[k].iloc[0]
                            break

                    asset_keys = ['Total Assets', 'TotalAssets']
                    for k in asset_keys:
                        if k in bs.index:
                            total_assets = bs.loc[k].iloc[0]
                            break

                if net_income and total_equity and total_equity != 0:
                    rec['ROE'] = round(float(net_income / total_equity) * 100, 2)
                if net_income and total_assets and total_assets != 0:
                    rec['ROA'] = round(float(net_income / total_assets) * 100, 2)
            except:
                pass

            # ── CAR & NPL (Khusus Bank) ──────────────────────────────────
            industry = info.get('industry', '')
            sector_yf = info.get('sector', '')
            is_bank = 'Bank' in industry or sector_yf == 'Financial Services'
            if is_bank:
                rec['CAR'] = info.get('capitalAdequacyRatio')
                rec['NPL'] = info.get('nonPerformingLoan')

            # ── Median PER & PBV Historis 3 Tahun per Ticker ────────────
            # Gunakan history 3 tahun + EPS / BV per share dari info
            # PER  = Close / EPS  → pakai trailingEps dari info (proxy stabil)
            # PBV  = Close / Book Value per Share
            try:
                hist_3y = hist.tail(252 * 3) if len(hist) >= 252 else hist
                closes = hist_3y['Close']

                eps = info.get('trailingEps')
                bvps = info.get('bookValue')  # Book Value Per Share

                if eps and eps > 0 and not closes.empty:
                    per_series = closes / eps
                    rec['_PER_median_ticker'] = float(per_series.median())

                if bvps and bvps > 0 and not closes.empty:
                    pbv_series = closes / bvps
                    rec['_PBV_median_ticker'] = float(pbv_series.median())
            except:
                pass

        except Exception as e:
            print(f"[enrich] Gagal fetch {ticker}: {e}")

        records.append(rec)

    df = pd.DataFrame(records)

    # ── Hitung Median PER & PBV per Sektor ──────────────────────────────
    sektoral_per = (
        df.groupby('Sektor')['_PER_median_ticker']
        .median()
        .rename('Median_PER_3Y')
    )
    sektoral_pbv = (
        df.groupby('Sektor')['_PBV_median_ticker']
        .median()
        .rename('Median_PBV_3Y')
    )
    df = df.join(sektoral_per, on='Sektor')
    df = df.join(sektoral_pbv, on='Sektor')

    # Buang kolom sementara
    df.drop(columns=['_PER_median_ticker', '_PBV_median_ticker'], inplace=True)

    # ── Filter ───────────────────────────────────────────────────────────
    before = len(df)
    df = df[df['Value_MA20'].notna() & (df['Value_MA20'] >= min_value_ma20)]
    df = df[df['ROE'].notna()        & (df['ROE'] >= min_roe)]
    df = df[df['ROA'].notna()        & (df['ROA'] > 0)]
    after = len(df)

    df.reset_index(drop=True, inplace=True)
    df.to_csv(out_csv_path, index=False)

    return df, before, after


# --- ENTRY POINT YANG DIPANGGIL app.py (Step 2 Panel Admin) ---
def process_liquid_stocks(df_pre: pd.DataFrame,
                          min_value_ma20: int = 2_000_000_000,
                          min_roe: float = 10.0) -> pd.DataFrame:
    """
    Wrapper yang dipanggil oleh app.py di Step 2 panel admin.
    Menerima DataFrame dari pre_liquid_stocks.csv,
    menjalankan enrich_and_filter(), dan mengembalikan df hasil.

    Parameter:
        df_pre        : DataFrame dari pre_liquid_stocks.csv
        min_value_ma20: Filter minimum Value MA20 (default Rp 2 M)
        min_roe       : Filter minimum ROE dalam % (default 10%)

    Return:
        DataFrame hasil enrichment yang siap disimpan sebagai liquid_stocks.csv
    """
    import tempfile, os

    # Simpan df_pre ke file sementara agar bisa dibaca enrich_and_filter()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                     delete=False, encoding='utf-8') as tmp_in:
        df_pre.to_csv(tmp_in, index=False)
        tmp_in_path = tmp_in.name

    tmp_out_path = tmp_in_path.replace('.csv', '_out.csv')

    try:
        df_hasil, _, _ = enrich_and_filter(
            pre_csv_path=tmp_in_path,
            out_csv_path=tmp_out_path,
            min_value_ma20=min_value_ma20,
            min_roe=min_roe,
            progress_callback=None   # progress bar dihandle app.py via st.spinner
        )
    finally:
        # Bersihkan file sementara
        if os.path.exists(tmp_in_path):  os.remove(tmp_in_path)
        if os.path.exists(tmp_out_path): os.remove(tmp_out_path)

    return df_hasil
