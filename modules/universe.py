"""
Modul: universe.py
Fungsi: Single Source of Truth untuk data saham, sektor, benchmark valuasi, dan status syariah.
Update: Februari 2026
"""

# 1. DATABASE SAHAM BERDASARKAN SEKTOR (Gabungan Indeks Mayor)
UNIVERSE_SAHAM = {
    "BANKING": [
        "BBCA", "BBRI", "BMRI", "BBNI", "BBTN", "BRIS", "BTPS", "ARTO", "BBYB", "BDMN", "BNGA"
    ],
    "ENERGY_MINING": [
        "AADI", "ADRO", "ADMR", "ANTM", "BREN", "BUMI", "BRMS", "CUAN", "DSSA", "ELSA", 
        "ENRG", "HRUM", "INCO", "INDY", "ITMG", "MEDC", "PGAS", "PGEO", "PTBA", "RATU", 
        "SGER", "TOBA", "TINS", "MBMA", "MDKA", "AMMN"
    ],
    "INFRASTRUCTURE": [
        "TLKM", "ISAT", "EXCL", "MTEL", "JSMR", "TBIG", "TOWR", "WIFI", "INET", "WIKA", 
        "ADHI", "PTPP"
    ],
    "BASIC_INDUSTRIAL": [
        "ASII", "ARCI", "BRPT", "CPIN", "DSNG", "INKP", "INTP", "JPFA", "NCKL", "SMGR", 
        "TPIA", "TKIM", "UNTR", "AVIA", "AUTO"
    ],
    "CONSUMER_HEALTH": [
        "AMRT", "CMRY", "GOTO", "HEAL", "ICBP", "INDF", "KLBF", "MIKA", "MYOR", "SIDO", 
        "SILO", "UNVR", "ACES", "ERAA", "FILM", "MAPA", "MAPI", "HMSP", "MNCN", "BIRD", "MPMX"
    ],
    "PROPERTY": [
        "BSDE", "CTRA", "PANI", "PWON", "SMRA", "BKSL", "ASRI"
    ],
    "AGRI_MARITIME": [
        "LSIP", "SMDR", "SRTG"
    ]
}

# 2. BENCHMARK VALUASI RATA-RATA 5 TAHUN (Estimasi per Sektor)
SECTOR_BENCHMARKS = {
    "BANKING": {"avg_per": 12.0, "avg_pbv": 1.8},
    "ENERGY_MINING": {"avg_per": 8.0, "avg_pbv": 1.5},
    "INFRASTRUCTURE": {"avg_per": 18.0, "avg_pbv": 1.3},
    "BASIC_INDUSTRIAL": {"avg_per": 14.0, "avg_pbv": 1.6},
    "CONSUMER_HEALTH": {"avg_per": 22.0, "avg_pbv": 3.0},
    "PROPERTY": {"avg_per": 10.0, "avg_pbv": 0.8},
    "AGRI_MARITIME": {"avg_per": 11.0, "avg_pbv": 1.0}
}

# 3. DATABASE SAHAM SYARIAH (ISSI)
# Menggunakan tipe data Set {} untuk pencarian O(1) yang sangat ringan dan cepat.
# Saat ini diisi dengan saham syariah yang ada di UNIVERSE_SAHAM sebagai basis awal.
SYARIAH_STOCKS_ISSI = {
    # Perbankan
    "BRIS", "BTPS", 
    # Energi & Tambang
    "ADRO", "ADMR", "ANTM", "BREN", "BRMS", "ENRG", "HRUM", "INCO", "INDY", "ITMG", 
    "PGAS", "PGEO", "PTBA", "TINS", "MDKA",
    # Infrastruktur & Telekomunikasi
    "TLKM", "ISAT", "EXCL", "MTEL", "WIKA", "ADHI", "PTPP", "TOWR", "TBIG", "WIFI",
    # Industri Dasar
    "ASII", "ARCI", "BRPT", "CPIN", "DSNG", "INKP", "INTP", "JPFA", "SMGR", "TPIA", 
    "TKIM", "UNTR", "AUTO", "AVIA",
    # Konsumsi & Kesehatan
    "AMRT", "CMRY", "ICBP", "INDF", "KLBF", "MIKA", "MYOR", "SIDO", "SILO", "UNVR", 
    "ACES", "ERAA", "MAPA", "MAPI", "FILM", "HEAL",
    # Properti
    "BSDE", "CTRA", "PWON", "SMRA", "ASRI", "PANI",
    # Agri & Maritim
    "LSIP"
    
    # NOTE: Bapak bisa menambahkan ratusan kode saham ISSI lainnya di bawah ini, 
    # cukup pisahkan dengan tanda koma dan beri tanda kutip (misal: "AALI", "ABBA", dst).
}

# ==========================================
# FUNGSI-FUNGSI PENDUKUNG (HELPER FUNCTIONS)
# ==========================================

def get_all_tickers():
    """
    Mengambil daftar semua kode saham unik yang ada di UNIVERSE_SAHAM.
    Output: List string yang sudah diurutkan sesuai abjad.
    """
    all_tickers = []
    for tickers in UNIVERSE_SAHAM.values():
        all_tickers.extend(tickers)
    return sorted(list(set(all_tickers)))

def get_sector_data(ticker):
    """
    Mencari sektor dan angka acuan (benchmark) valuasi dari sebuah saham.
    Input: String ticker (misal: "BBCA")
    Output: Tuple berisi (Nama Sektor, Dictionary Benchmark)
    """
    ticker_upper = ticker.upper()
    for sector, tickers in UNIVERSE_SAHAM.items():
        if ticker_upper in tickers:
            return sector, SECTOR_BENCHMARKS.get(sector, {"avg_per": 15.0, "avg_pbv": 1.5})
    
    # Jika saham di luar universe dimasukkan
    return "UNKNOWN", {"avg_per": 15.0, "avg_pbv": 1.5}

def is_syariah(ticker):
    """
    Mengecek apakah suatu saham berstatus syariah (masuk daftar ISSI).
    Input: String ticker (misal: "BRIS")
    Output: Boolean (True jika syariah, False jika tidak)
    """
    return ticker.upper() in SYARIAH_STOCKS_ISSI

# Pengujian singkat (Hanya berjalan jika file ini dieksekusi langsung)
if __name__ == "__main__":
    print(f"Total saham di Universe Utama: {len(get_all_tickers())} emiten")
    print(f"Sektor BIRD: {get_sector_data('BIRD')[0]}")
    print(f"Apakah BBCA Syariah? {is_syariah('BBCA')}")
    print(f"Apakah BRIS Syariah? {is_syariah('BRIS')}")
