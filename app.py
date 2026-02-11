import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import pytz

# ==========================================
# 1. KONFIGURASI HALAMAN
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
    PASSWORD_RAHASIA = "12345" # Password cadangan lokal

# Link Lynk.id Bapak
LINK_LYNK_ID = "https://lynk.id/musatanaja"

# ==========================================
# 2. CSS CUSTOM (TAMPILAN)
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
# 3. FUNGSI FITUR-FITUR
# ==========================================

# --- FITUR 1: SCREENING SAHAM (UPDATED: TOP 50) ---
def fitur_screening():
    st.title("🔍 Screening Saham: Top 50 Teraktif")
    st.markdown("---")

    # A. SINKRONISASI WAKTU
    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(wib)
    jam_sekarang = now.strftime('%H:%M')
    tanggal_sekarang = now.strftime('%d %B %Y')

    if now.hour < 16:
        sesi_pasar = "LIVE MARKET (Fokus: Volatilitas Intraday)"
    else:
        sesi_pasar = "POST MARKET (Fokus: Analisa Penutupan)"

    st.info(f"""
    **📅 Waktu:** {tanggal_sekarang} - {jam_sekarang} WIB
    **🎯 Fokus:** 50 Saham Paling Likuid (Bluechip + High Volatility)
    """)

    # B. KRITERIA SCREENING
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

    tombol_scan = st.button("Mulai Screening (Proses ±60 Detik)")

    # C. DAFTAR 50 SAHAM (DIPERLUAS)
    # Mencakup Big Caps, Grup Barito, Bank Digital, Energi, & Properti
    saham_top50 = [
        # 1. BANK BIG CAPS & DIGITAL (8)
        "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", 
        "BBTN.JK", "BRIS.JK", "ARTO.JK", "BFIN.JK",
        
        # 2. GRUP BARITO & ENERGI PANAS (5)
        "BREN.JK", "TPIA.JK", "BRPT.JK", "PGEO.JK", "AMMN.JK",
        
        # 3. TELEKOMUNIKASI & MENARA (5)
        "TLKM.JK", "ISAT.JK", "EXCL.JK", "TOWR.JK", "MTEL.JK",
        
        # 4. TEKNOLOGI (3)
        "GOTO.JK", "BUKA.JK", "EMTK.JK",
        
        # 5. TAMBANG & KOMODITAS (12)
        "ADRO.JK", "ANTM.JK", "MDKA.JK", "PTBA.JK", "INCO.JK", 
        "PGAS.JK", "MEDC.JK", "AKRA.JK", "HRUM.JK", "ITMG.JK", 
        "TINS.JK", "MBMA.JK",
        
        # 6. CONSUMER & RETAIL (8)
        "ICBP.JK", "INDF.JK", "UNVR.JK", "AMRT.JK", "CPIN.JK", 
        "MYOR.JK", "ACES.JK", "MAPI.JK",
        
        # 7. PROPERTI & KONSTRUKSI (5)
        "CTRA.JK", "SMRA.JK", "BSDE.JK", "PWON.JK", "PANI.JK",
        
        # 8. LAIN-LAIN (4)
        "ASII.JK", "UNTR.JK", "KLBF.JK", "JSMR.JK"
    ]

    # D. LOGIKA SCREENING
    if tombol_scan:
        hasil_lolos = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_saham = len(saham_top50)

        for i, ticker in enumerate(saham_top50):
            progress = (i + 1) / total_saham
            progress_bar.progress(progress)
            status_text.text(f"Menganalisa ({i+1}/{total_saham}): {ticker}...")

            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period="3mo")

                if len(df) < 55: continue

                current_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                volume_now = df['Volume'].iloc[-1]
                
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['MA50'] = df['Close'].rolling(window=50).mean()
                df['VolMA20'] = df['Volume'].rolling(window=20).mean()

                ma20 = df['MA20'].iloc[-1]
                ma50 = df['MA50'].iloc[-1]
                vol_avg = df['VolMA20'].iloc[-1]
                transaksi_value = current_price * volume_now

                # Kriteria Filter
                cond1 = current_price > 55
                cond2 = (current_price > ma20) and (ma20 > ma50) # Uptrend
                cond3 = transaksi_value > 10_000_000_000 # Liquid > 10M
                cond4 = volume_now > vol_avg # Ada lonjakan volume

                if cond1 and cond2 and cond3 and cond4:
                    support_level = df['Low'].tail(20).min()
                    resist_level = df['High'].tail(20).max()
                    risk_pct = ((support_level - current_price) / current_price) * 100
                    reward_pct = ((resist_level - current_price) / current_price) * 100
                    chg_pct = ((current_price - prev_price) / prev_price) * 100

                    hasil_lolos.append({
                        "Ticker": ticker.replace(".JK", ""),
                        "Harga": current_price,
                        "Chg (%)": round(chg_pct, 2),
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

        if len(hasil_lolos) > 0:
            st.success(f"Ditemukan {len(hasil_lolos)} saham potensial dari Top 50!")
            df_hasil = pd.DataFrame(hasil_lolos)
            st.dataframe(df_hasil[["Ticker", "Harga", "Chg (%)", "Vol Spike", "Value (M)"]], use_container_width=True)
            
            st.markdown("---")
            st.subheader("📝 Trading Plan Otomatis")
            for item in hasil_lolos:
                with st.expander(f"Analisa: {item['Ticker']} (Risk: {item['Risk (%)']}% | Reward: +{item['Reward (%)']}%)"):
                    c1, c2, c3 = st.columns(3)
                    with c1: st.metric("Entry Price", f"{item['Harga']:,.0f}")
                    with c2: st.metric("Stop Loss", f"{item['Support']:,.0f}", f"{item['Risk (%)']}%")
                    with c3: st.metric("Take Profit", f"{item['Resist']:,.0f}", f"+{item['Reward (%)']}%")
        else:
            st.warning("Hari ini pasar sangat selektif. Belum ada saham di Top 50 yang memenuhi kriteria (Uptrend + High Volume + Liquid). Coba cek lagi nanti sore.")

# --- FITUR LAIN (MASIH KOSONG / PLACEHOLDER) ---

def fitur_teknikal():
    st.title("📈 Analisa Teknikal")
    st.info("Fitur ini akan kita isi di tahap selanjutnya.")

def fitur_perbandingan():
    st.title("⚖️ Perbandingan Saham")
    st.info("Fitur ini akan kita isi di tahap selanjutnya.")

def fitur_fundamental():
    st.title("📊 Analisa Fundamental")
    st.info("Fitur ini akan kita isi di tahap selanjutnya.")

def fitur_dividen():
    st.title("💰 Analisa Dividen")
    st.info("Fitur ini akan kita isi di tahap selanjutnya.")

def halaman_beranda():
    st.title("Selamat Datang di Dashboard Saham")
    st.write("Silakan pilih menu di sebelah kiri (Sidebar).")

# ==========================================
# 4. LOGIKA UTAMA (MAIN LOOP)
# ==========================================

if 'status_login' not in st.session_state:
    st.session_state['status_login'] = False

def main():
    local_css()
    
    # --- JIKA BELUM LOGIN ---
    if not st.session_state['status_login']:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<h1 style='text-align: center;'>📈 Konsultan Saham Pro</h1>", unsafe_allow_html=True)
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
            st.link_button("🛒 Beli Kode Akses", LINK_LYNK_ID, use_container_width=True)

    # --- JIKA SUDAH LOGIN ---
    else:
        with st.sidebar:
            st.header("Musa Stock Pro")
            st.success("Status: Member Premium")
            st.markdown("---")
            
            pilihan_menu = st.radio(
                "Pilih Fitur:",
                ("🏠 Beranda", "🔍 1. Screening Harian", "📈 2. Analisa Teknikal", 
                 "⚖️ 3. Perbandingan Saham", "📊 4. Analisa Fundamental", "💰 5. Analisa Dividen")
            )
            
            st.markdown("---")
            if st.button("Log Out"):
                st.session_state['status_login'] = False
                st.rerun()

        if pilihan_menu == "🏠 Beranda": halaman_beranda()
        elif pilihan_menu == "🔍 1. Screening Harian": fitur_screening()
        elif pilihan_menu == "📈 2. Analisa Teknikal": fitur_teknikal()
        elif pilihan_menu == "⚖️ 3. Perbandingan Saham": fitur_perbandingan()
        elif pilihan_menu == "📊 4. Analisa Fundamental": fitur_fundamental()
        elif pilihan_menu == "💰 5. Analisa Dividen": fitur_dividen()

if __name__ == "__main__":
    main()
