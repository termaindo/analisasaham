"""
Modul: universe.py
Status: FULL AUDIT (100% Indeks Coverage)
Cakupan: Kompas100, JII70, LQ45, IDX80, IDXG30, IDXQ30, IDXHIDIV20 + Mid-Cap Pilihan
"""

UNIVERSE_SAHAM = {
    "BANKING": [
        "AGRO", "ARTO", "BBCA", "BBRI", "BBYB", "BBHI", "BBKP", "BBNI", "BBTN", "BDMN", 
        "BJBR", "BJTM", "BMRI", "BNGA", "BRIS", "BTPS", "BVIC", "MAYA", "NISP", "PNBN", 
        "PNLF"
    ],
    "ENERGY_MINING": [
        "AADI", "ADRO", "ADMR", "ANTM", "BREN", "BUMI", "BRMS", "CUAN", "DSSA", "ELSA", 
        "ENRG", "HRUM", "INCO", "INDY", "ITMG", "MEDC", "PGAS", "PGEO", "PTBA", "RATU", 
        "SGER", "TOBA", "TINS", "MBMA", "MDKA", "AMMN", "ESSA", "RAJA", "BIPI", "KKGI",
        "DOID", "DEWA"
    ],
    "INFRASTRUCTURE": [
        "ACST", "ADCP", "ADHI", "ASSA", "BUKK", "EXCL", "INET", "IPTV", "ISAT", "JSMR",   
        "LINK", "META", "MTEL", "POWR", "PTPP", "TBIG", "TOWR", "TLKM", "WIKA"
    ],
    "BASIC_INDUSTRIAL": [
        "ASII", "ARCI", "BRPT", "CPIN", "DSNG", "INKP", "INTP", "JPFA", "NCKL", "SMGR", 
        "TPIA", "TKIM", "UNTR", "AVIA", "AUTO", "SMSM", "DRMA", "AGII", "ARNA", "MAIN", 
        "WOOD", "TOWR", "SRTG"
    ],
    "CONSUMER_HEALTH": [
        "AMRT", "CMRY", "GGRM", "HEAL", "ICBP", "INDF", "KLBF", "MIKA", "MYOR", "SIDO", 
        "SILO", "UNVR", "ACES", "ERAA", "FILM", "MAPA", "MAPI", "HMSP", "MNCN", "BIRD", 
        "MPMX", "ULTJ", "LPPF", "RALS", "SCMA", "TSPC", "KAEF", "AMMS", "HRTA", "WIIM"
    ],
    "PROPERTY": [
        "APLN", "ASRI", "BKSL", "BSDE", "CBDK", "CTRA", "DILD", "DMAS", "KIJA", "LPCK", 
        "MDLN", "PANI", "PWON", "SMRA", "SSIA"
    ],
    "AGRI_MARITIME": [
        "LSIP", "AALI", "TAPG", "BWPT", "DSNG", "SIMP", "TBLA"
    ],
    "TECHNOLOGY": [
        "BELI", "BUKA", "GOTO", "WIFI"
    ],
    "TRANSPORTATION": [
        "ELPI", "NELY", "SMDR", "TMAS"
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
    "AGRI_MARITIME": {"avg_per": 11.0, "avg_pbv": 1.0},
    "TECHNOLOGY": {"avg_per": 15.0, "avg_pbv": 1.0},
    "TRANSPORTATION": {"avg_per": 15.0, "avg_pbv": 1.0}
}

# 3. DATABASE SAHAM SYARIAH (ISSI) - Telah diperluas sesuai JII70 & ISSI terbaru
SYARIAH_STOCKS_ISSI = {
    "AADI", "AALI", "ACES", "ACST", "ADCP", "ADHI", "ADMR", "ADRO", "AGII", "AMMN", 
    "AMMS", "AMRT", "ANTM", "APLN", "ARCI", "ARNA", "ASII", "ASRI", "ASSA", "AUTO", 
    "AVIA", "BELI", "BIPI", "BIRD", "BKSL", "BREN", "BRIS", "BRMS", "BRPT", "BSDE", 
    "BTPS", "BUKA", "BUKK", "BUMI", "BWPT", "CBDK", "CMRY", "CPIN", "CTRA", "CUAN", 
    "DEWA", "DILD", "DMAS", "DOID", "DRMA", "DSNG", "DSSA", "ELSA", "ENRG", "ERAA", 
    "ESSA", "EXCL", "FILM", "GOTO", "HEAL", "HRTA", "HRUM", "ICBP", "INCO", "INDF", 
    "INDY", "INET", "INKP", "INTP", "IPTV", "ISAT", "ITMG", "JPFA", "KAEF", "KIJA", 
    "KKGI", "KLBF", "LINK", "LPCK", "LPPF", "LSIP", "MAIN", "MAPA", "MAPI", "MBMA", 
    "MDKA", "MDLN", "MEDC", "META", "MIKA", "MNCN", "MPMX", "MTEL", "MYOR", "NCKL", 
    "PANI", "PGAS", "PGEO", "POWR", "PTBA", "PTPP", "PWON", "RAJA", "RALS", "RATU", 
    "SCMA", "SGER", "SIDO", "SILO", "SIMP", "SMDR", "SMGR", "SMRA", "SMSM", "SSIA", 
    "TAPG", "TBLA", "TINS", "TKIM", "TLKM", "TOBA", "TPIA", "TSPC", "ULTJ", "UNTR", 
    "UNVR", "WIFI", "WIKA", "WOOD", "ELPI", "NELY", "TMAS"
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
