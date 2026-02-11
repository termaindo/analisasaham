import streamlit as st
import pandas as pd
import yfinance as yf

# ==========================================
# KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="Musa Stock Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- KEAMANAN PASSWORD (SECRETS) ---
try:
    PASSWORD_RAHASIA = st.secrets["PASSWORD_RAHASIA"]
except FileNotFoundError:
    PASSWORD_RAHASIA = "12345" # Password cadangan jika dijalankan lokal

# Link Lynk.id Bapak
LINK_LYNK_ID = "https://lynk.id/musatanaja"

# ==========================================
# BAGIAN 1: CSS CUSTOM
# ==========================================
def local_css():
    st.markdown("""
    <style>
    /* Tombol Beli Merah */
    a[href^="https://lynk.id"] {
        background-color: #ff4b4b;
        color: white;
        text-decoration: none;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        display: block;
        text-align: center;
        font-weight: bold;
        border: 1px solid #ff4b4b;
    }
    a[href^="https://lynk.id"]:hover {
        background-color: #cc0000;
        border-color: #cc0000;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# BAGIAN 2: FUNGSI FITUR (KAMAR KOSONG)
# ==========================================

# 1. SCREENING SAHAM HARIAN
def fitur_screening():
    st.title("🔍 Screening Saham Harian")
    st.markdown("---")
    st.info("💡 Area ini akan diisi kode Python dari Prompt Screening Saham Anda.")
    # [TEMPEL KODE PROMPT SCREENING DI SINI]

# 2. ANALISA TEKNIKAL
def fitur_teknikal():
    st.title("📈 Analisa Teknikal")
    st.markdown("---")
    st.info("💡 Area ini akan diisi kode Python dari Prompt Analisa Teknikal Anda.")
    # [TEMPEL KODE PROMPT TEKNIKAL DI SINI]

# 3. PERBANDINGAN 2 SAHAM
def fitur_perbandingan():
    st.title("⚖️ Perbandingan 2 Saham")
    st.markdown("---")
    st.info("💡 Area ini akan diisi kode Python dari Prompt Perbandingan Saham Anda.")
    # [TEMPEL KODE PROMPT PERBANDINGAN DI SINI]

# 4. ANALISA FUNDAMENTAL
def fitur_fundamental():
    st.title("📊 Analisa Fundamental")
    st.markdown("---")
    st.info("💡 Area ini akan diisi kode Python dari Prompt Analisa Fundamental Anda.")
    # [TEMPEL KODE PROMPT FUNDAMENTAL DI SINI]

# 5. ANALISA SAHAM DIVIDEN (BARU)
def fitur_dividen():
    st.title("💰 Analisa Saham Dividen")
    st.markdown("---")
    st.info("💡 Area ini akan diisi kode Python dari Prompt Analisa Dividen Anda.")
    # [TEMPEL KODE PROMPT DIVIDEN DI SINI]

def halaman_beranda():
    st.title("Selamat Datang di Dashboard Saham")
    st.image("https://images.unsplash.com/photo-1611974765270-ca1258634369?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80", caption="Market Dashboard")
    st.write("""
    Silakan pilih menu di sebelah kiri (Sidebar) untuk mulai:
    
    1. **Screening Harian**: Cari saham potensial hari ini.
    2. **Analisa Teknikal**: Cek grafik harga & indikator.
    3. **Perbandingan**: Adu performa dua saham.
    4. **Fundamental**: Cek kesehatan keuangan perusahaan.
    5. **Dividen**: Analisa imbal hasil dividen.
    """)

# ==========================================
# BAGIAN 3: LOGIKA UTAMA (MAIN)
# ==========================================

if 'status_login' not in st.session_state:
    st.session_state['status_login'] = False

def main():
    local_css()
    
    # --- TAMPILAN 1: BELUM LOGIN ---
    if not st.session_state['status_login']:
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("<h1 style='text-align: center;'>📈 Konsultan Saham Pro</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center;'>Selamat datang di Aplikasi Analisa Saham & Trading.</p>", unsafe_allow_html=True)
            st.markdown("---")
            
            st.write("🔑 **Masukkan Kode Akses Premium:**")
            input_pass = st.text_input("Password", type="password", label_visibility="collapsed")
            
            if st.button("Buka Aplikasi", use_container_width=True):
                if input_pass == PASSWORD_RAHASIA:
                    st.session_state['status_login'] = True
                    st.rerun()
                else:
                    st.error("Kode akses salah.")

            st.info("🔒 Aplikasi ini dikunci khusus untuk Member Premium.")
            st.markdown("<br>", unsafe_allow_html=True)
            st.write("**Belum punya Kode Akses?**")
            st.link_button("🛒 Beli Kode Akses (Klik Di Sini)", LINK_LYNK_ID, use_container_width=True)

    # --- TAMPILAN 2: SUDAH LOGIN ---
    else:
        with st.sidebar:
            st.header("Musa Stock Pro")
            st.success("Status: Member Premium")
            st.markdown("---")
            
            # MENU BARU (Urutan 1-5)
            pilihan_menu = st.radio(
                "Pilih Fitur:",
                (
                    "🏠 Beranda", 
                    "🔍 1. Screening Harian", 
                    "📈 2. Analisa Teknikal", 
                    "⚖️ 3. Perbandingan Saham", 
                    "📊 4. Analisa Fundamental",
                    "💰 5. Analisa Dividen"
                )
            )
            
            st.markdown("---")
            if st.button("Log Out"):
                st.session_state['status_login'] = False
                st.rerun()

        # NAVIGASI KE FUNGSI
        if pilihan_menu == "🏠 Beranda":
            halaman_beranda()
        elif pilihan_menu == "🔍 1. Screening Harian":
            fitur_screening()
        elif pilihan_menu == "📈 2. Analisa Teknikal":
            fitur_teknikal()
        elif pilihan_menu == "⚖️ 3. Perbandingan Saham":
            fitur_perbandingan()
        elif pilihan_menu == "📊 4. Analisa Fundamental":
            fitur_fundamental()
        elif pilihan_menu == "💰 5. Analisa Dividen":
            fitur_dividen()

if __name__ == "__main__":
    main()



# --- IMPORT LIBRARY KHUSUS UNTUK FITUR INI ---
import datetime
import pytz

def fitur_screening():
    st.title("🔍 Screening Saham: Top 30 Teraktif")
    st.markdown("---")

    # 1. SINKRONISASI WAKTU (WIB)
    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(wib)
    jam_sekarang = now.strftime('%H:%M')
    tanggal_sekarang = now.strftime('%d %B %Y')

    # Tentukan Sesi Pasar
    if now.hour < 16:
        sesi_pasar = "LIVE MARKET (Fokus: Volatilitas Intraday)"
    else:
        sesi_pasar = "POST MARKET (Fokus: Analisa Penutupan)"

    st.info(f"""
    **📅 Waktu:** {tanggal_sekarang} - {jam_sekarang} WIB
    **🎯 Fokus:** 30 Saham Paling Likuid (Market Leaders)
    """)

    # 2. KRITERIA SCREENING
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        * ✅ Harga > Rp 55
        * ✅ Trend: Harga > MA20 > MA50
        """)
    with col2:
        st.markdown("""
        * ✅ Value Transaksi > 10 Miliar
        * ✅ Volume Spike (Vol > Rata-rata)
        """)

    tombol_scan = st.button("Mulai Screening (Proses ±40 Detik)")

    # 3. DAFTAR 30 SAHAM TERAKTIF (Update)
    # Kombinasi Big Caps, Bank Digital, Komoditas, dan Properti
    saham_top30 = [
        # BANK BIG CAPS
        "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", 
        # TELEKOMUNIKASI
        "TLKM.JK", "ISAT.JK", "EXCL.JK", "TOWR.JK",
        # TEKNOLOGI & BANK DIGITAL
        "GOTO.JK", "ARTO.JK", "BUKA.JK", "BRIS.JK",
        # PERTAMBANGAN & ENERGI
        "ADRO.JK", "ANTM.JK", "MDKA.JK", "PTBA.JK", 
        "INCO.JK", "PGAS.JK", "MEDC.JK", "AKRA.JK", "HRUM.JK",
        # CONSUMER GOODS & RETAIL
        "ICBP.JK", "INDF.JK", "UNVR.JK", "AMRT.JK", "CPIN.JK",
        # ASTRA & PROPERTI
        "ASII.JK", "UNTR.JK", "CTRA.JK", "SMRA.JK"
    ]

    # 4. LOGIKA SCREENING
    if tombol_scan:
        hasil_lolos = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_saham = len(saham_top30)

        for i, ticker in enumerate(saham_top30):
            # Update Progress Bar
            progress = (i + 1) / total_saham
            progress_bar.progress(progress)
            status_text.text(f"Menganalisa ({i+1}/{total_saham}): {ticker}...")

            try:
                # Ambil data 3 bulan terakhir
                stock = yf.Ticker(ticker)
                df = stock.history(period="3mo")

                if len(df) < 55: continue

                # --- RUMUS INDIKATOR ---
                current_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                volume_now = df['Volume'].iloc[-1]
                
                # Moving Average
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['MA50'] = df['Close'].rolling(window=50).mean()
                df['VolMA20'] = df['Volume'].rolling(window=20).mean()

                ma20 = df['MA20'].iloc[-1]
                ma50 = df['MA50'].iloc[-1]
                vol_avg = df['VolMA20'].iloc[-1]

                # Nilai Transaksi
                transaksi_value = current_price * volume_now

                # --- FILTER ---
                cond1 = current_price > 55
                cond2 = (current_price > ma20) and (ma20 > ma50) # Uptrend
                cond3 = transaksi_value > 10_000_000_000 # Minimal 10 Miliar
                cond4 = volume_now > vol_avg # Volume Spike

                if cond1 and cond2 and cond3 and cond4:
                    # Hitung Risk Reward (Support & Resist 20 Hari)
                    support_level = df['Low'].tail(20).min()
                    resist_level = df['High'].tail(20).max()

                    risk_pct = ((support_level - current_price) / current_price) * 100
                    reward_pct = ((resist_level - current_price) / current_price) * 100
                    chg_pct = ((current_price - prev_price) / prev_price) * 100

                    hasil_lolos.append({
                        "Ticker": ticker.replace(".JK", ""),
                        "Harga": current_price,
                        "Chg (%)": round(chg_pct, 2),
                        "Trend": "Uptrend ✅",
                        "Vol Spike": "✅",
                        "Value (M)": round(transaksi_value / 1_000_000_000, 1),
                        "Support": support_level,
                        "Resist": resist_level,
                        "Risk (%)": round(risk_pct, 2),
                        "Reward (%)": round(reward_pct, 2)
                    })

            except Exception:
                continue 

        progress_bar.empty()
        status_text.empty()

        # 5. TAMPILKAN HASIL
        if len(hasil_lolos) > 0:
            st.success(f"Ditemukan {len(hasil_lolos)} saham potensial dari Top 30!")
            
            # Tabel Ringkas
            df_hasil = pd.DataFrame(hasil_lolos)
            st.dataframe(
                df_hasil[["Ticker", "Harga", "Chg (%)", "Vol Spike", "Value (M)"]],
                use_container_width=True
            )

            st.markdown("---")
            st.subheader("📝 Trading Plan Otomatis")
            
            # Detail Plan
            for item in hasil_lolos:
                with st.expander(f"Analisa: {item['Ticker']} (Risk: {item['Risk (%)']}% | Reward: +{item['Reward (%)']}%)"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("Entry Price", f"{item['Harga']:,.0f}")
                    with c2:
                        st.metric("Stop Loss", f"{item['Support']:,.0f}", f"{item['Risk (%)']}%")
                    with c3:
                        st.metric("Take Profit", f"{item['Resist']:,.0f}", f"+{item['Reward (%)']}%")
                    
                    st.caption("Plan ini dihitung berdasarkan Support & Resistance 20 hari terakhir.")
        else:
            st.warning("Saat ini pasar sedang konsolidasi. Belum ada saham di Top 30 yang memenuhi kriteria Uptrend + High Volume secara bersamaan.")

    st.caption("DISCLAIMER: Keputusan investasi ada di tangan Anda.")

