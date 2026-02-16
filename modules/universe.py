# universe.py (Updated with Benchmarks)

# Dictionary Saham berdasarkan Sektor
UNIVERSE_SAHAM = {
    "BANKING": ["BBCA", "BBRI", "BMRI", "BBNI", "BBTN", "BRIS", "BTPS", "ARTO", "BBYB", "BDMN", "BNGA"],
    "ENERGY_MINING": ["AADI", "ADRO", "ADMR", "ANTM", "BREN", "BUMI", "BRMS", "CUAN", "DSSA", "ELSA", "ENRG", "HRUM", "INCO", "INDY", "ITMG", "MEDC", "PGAS", "PGEO", "PTBA", "RATU", "SGER", "TOBA", "TINS", "MBMA", "MDKA", "AMMN"],
    "INFRASTRUCTURE": ["TLKM", "ISAT", "EXCL", "MTEL", "JSMR", "TBIG", "TOWR", "WIFI", "INET", "WIKA", "ADHI", "PTPP"],
    "BASIC_INDUSTRIAL": ["ASII", "ARCI", "BRPT", "CPIN", "DSNG", "INKP", "INTP", "JPFA", "NCKL", "SMGR", "TPIA", "TKIM", "UNTR", "AVIA", "AUTO"],
    "CONSUMER_HEALTH": ["AMRT", "CMRY", "GOTO", "HEAL", "ICBP", "INDF", "KLBF", "MIKA", "MYOR", "SIDO", "SILO", "UNVR", "ACES", "ERAA", "FILM", "MAPA", "MAPI", "HMSP", "MNCN", "BIRD", "MPMX"],
    "PROPERTY": ["BSDE", "CTRA", "PANI", "PWON", "SMRA", "BKSL", "ASRI"],
    "AGRI_MARITIME": ["LSIP", "SMDR", "SRTG"]
}

# Angka Benchmark Rata-rata Sektor (PER dan PBV)
SECTOR_BENCHMARKS = {
    "BANKING": {"avg_per": 12.0, "avg_pbv": 1.8},
    "ENERGY_MINING": {"avg_per": 8.0, "avg_pbv": 1.5},
    "INFRASTRUCTURE": {"avg_per": 18.0, "avg_pbv": 1.3},
    "BASIC_INDUSTRIAL": {"avg_per": 14.0, "avg_pbv": 1.6},
    "CONSUMER_HEALTH": {"avg_per": 22.0, "avg_pbv": 3.0},
    "PROPERTY": {"avg_per": 10.0, "avg_pbv": 0.8},
    "AGRI_MARITIME": {"avg_per": 11.0, "avg_pbv": 1.0}
}

def get_sector_data(ticker):
    """Mencari sektor dan benchmark-nya berdasarkan ticker."""
    for sector, tickers in UNIVERSE_SAHAM.items():
        if ticker.upper() in tickers:
            return sector, SECTOR_BENCHMARKS.get(sector)
    return "UNKNOWN", {"avg_per": 15.0, "avg_pbv": 1.5} # Default nilai tengah
