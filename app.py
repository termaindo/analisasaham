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
