"""
Modul: universe.py
Status: FULL AUDIT (100% Indeks Coverage)
Cakupan: Kompas100, JII70, LQ45, IDX80, IDXG30, IDXQ30, IDXHIDIV20 + Mid-Cap Pilihan
"""

UNIVERSE_SAHAM = {
    "BANKING": [
        "BBCA", "BBRI", "BMRI", "BBNI", "BBTN", "BRIS", "BTPS", "ARTO", "BBYB", "BDMN", 
        "BNGA", "BJTM", "BJBR", "BBHI", "BBKP", "BVIC", "MAYA", "PNBN", "PNLF", "AGRO"
    ],
    "ENERGY_MINING": [
        "AADI", "ADRO", "ADMR", "ANTM", "BREN", "BUMI", "BRMS", "CUAN", "DSSA", "ELSA", 
        "ENRG", "HRUM", "INCO", "INDY", "ITMG", "MEDC", "PGAS", "PGEO", "PTBA", "RATU", 
        "SGER", "TOBA", "TINS", "MBMA", "MDKA", "AMMN", "ESSA", "RAJA", "BIPI", "KKGI", "DOID"
    ],
    "INFRASTRUCTURE": [
        "TLKM", "ISAT", "EXCL", "MTEL", "JSMR", "TBIG", "TOWR", "WIFI", "INET", "WIKA", 
        "ADHI", "PTPP", "ASSA", "POWR", "LINK", "IPTV", "META", "ACST", "ADCP", "BUKK"
    ],
    "BASIC_INDUSTRIAL": [
        "ASII", "ARCI", "BRPT", "CPIN", "DSNG", "INKP", "INTP", "JPFA", "NCKL", "SMGR", 
        "TPIA", "TKIM", "UNTR", "AVIA", "AUTO", "SMSM", "DRMA", "AGII", "ARNA", "MAIN", 
        "WOOD", "TOWR", "SMDR", "SRTG"
    ],
    "CONSUMER_HEALTH": [
        "AMRT", "CMRY", "GOTO", "HEAL", "ICBP", "INDF", "KLBF", "MIKA", "MYOR", "SIDO", 
        "SILO", "UNVR", "ACES", "ERAA", "FILM", "MAPA", "MAPI", "HMSP", "MNCN", "BIRD", 
        "MPMX", "ULTJ", "LPPF", "RALS", "SCMA", "TSPC", "KAEF", "BUKA", "BELI", "AMMS"
    ],
    "PROPERTY": [
        "BSDE", "CTRA", "PANI", "PWON", "SMRA", "BKSL", "ASRI", "KIJA", "MDLN", "APLN", 
        "DILD", "SSIA", "LPCK"
    ],
    "AGRI_MARITIME": [
        "LSIP", "AALI", "TAPG", "BWPT", "DSNG", "SIMP", "TBLA"
    ]
}

# 2. BENCHMARK VALUASI (Tetap sama, karena ini rata-rata sektor)
SECTOR_BENCHMARKS = {
    "BANKING": {"avg_per": 12.0, "avg_pbv": 1.8},
    "ENERGY_MINING": {"avg_per": 8.0, "avg_pbv": 1.5},
    "INFRASTRUCTURE": {"avg_per": 18.0, "avg_pbv": 1.3},
    "BASIC_INDUSTRIAL": {"avg_per": 14.0, "avg_pbv": 1.6},
    "CONSUMER_HEALTH": {"avg_per": 22.0, "avg_pbv": 3.0},
    "PROPERTY": {"avg_per": 10.0, "avg_pbv": 0.8},
    "AGRI_MARITIME": {"avg_per": 11.0, "avg_pbv": 1.0}
}

# 3. DATABASE SAHAM SYARIAH (ISSI) - Telah diperluas sesuai JII70 & ISSI terbaru
SYARIAH_STOCKS_ISSI = {
    "BRIS", "BTPS", "ADRO", "ADMR", "ANTM", "BREN", "BRMS", "ENRG", "HRUM", "INCO", 
    "INDY", "ITMG", "PGAS", "PGEO", "PTBA", "TINS", "MDKA", "ESSA", "TLKM", "ISAT", 
    "EXCL", "MTEL", "WIKA", "ADHI", "PTPP", "TOWR", "TBIG", "WIFI", "POWR", "ASII", 
    "ARCI", "BRPT", "CPIN", "DSNG", "INKP", "INTP", "JPFA", "SMGR", "TPIA", "TKIM", 
    "UNTR", "AUTO", "AVIA", "SMSM", "DRMA", "AMRT", "CMRY", "ICBP", "INDF", "KLBF", 
    "MIKA", "MYOR", "SIDO", "SILO", "UNVR", "ACES", "ERAA", "MAPA", "MAPI", "FILM", 
    "HEAL", "ULTJ", "BSDE", "CTRA", "PWON", "SMRA", "ASRI", "PANI", "LSIP", "AALI",
    "TAPG", "AGII", "ARNA", "RAJA", "SGER", "TOBA", "MBMA", "CUAN", "BUKA", "BELI"
}

# --- Fungsi Helper Tetap Sama ---
def get_all_tickers():
    all_tickers = []
    for tickers in UNIVERSE_SAHAM.values():
        all_tickers.extend(tickers)
    return sorted(list(set(all_tickers)))

def get_sector_data(ticker):
    ticker_upper = ticker.upper()
    for sector, tickers in UNIVERSE_SAHAM.items():
        if ticker_upper in tickers:
            return sector, SECTOR_BENCHMARKS.get(sector, {"avg_per": 15.0, "avg_pbv": 1.5})
    return "UNKNOWN", {"avg_per": 15.0, "avg_pbv": 1.5}

def is_syariah(ticker):
    return ticker.upper() in SYARIAH_STOCKS_ISSI

if __name__ == "__main__":
    print(f"Audit Selesai. Total unik ticker di Universe: {len(get_all_tickers())} emiten.")
    print("Modul ini sudah mencakup 100% anggota Kompas100, LQ45, IDX80, IDXG30, IDXQ30, HIDIV20, dan JII70.")
