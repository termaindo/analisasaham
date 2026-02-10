import streamlit as st
import pandas as pd
import yfinance as yf

# ==========================================
# KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="Expert Stock Pro",
    page_icon="📈",
    layout="wide", # Menggunakan layout lebar agar grafik saham jelas
    initial_sidebar_state="expanded"
)

# Password Rahasia
PASSWORD_RAHASIA = "SUKSESDISAHAM2026"

# ==========================================
# BAGIAN 1: CSS CUSTOM (Agar Tampilan Lebih Cantik)
# ==========================================
def local_css():
    st.markdown("""
    <style>
    /* Mengubah warna sidebar agar lebih tegas */
    [data-testid="stSidebar"] {
        background-color: #f0f2f6;
    }
    /* Mempercantik judul */
    h1 {
        color: #2c3e50;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# BAGIAN 2: FUNGSI FITUR (KAMAR KOSONG)
# ==========================================

def fitur_fundamental():
    st.title("📊 Analisa Fundamental")
    st.markdown("---")
    st.info("💡 Area ini akan diisi kode Python dari Prompt Analisa Fundamental Anda.")
    # [TEMPEL KODE DI SINI NANTI]

def fitur_teknikal():
    st.title("📈 Analisa Teknikal")
    st.markdown("---")
    st.info("💡 Area ini akan diisi kode Python dari Prompt Analisa Teknikal Anda.")
    # [TEMPEL KODE DI SINI NANTI]

def fitur_perbandingan():
    st.title("⚖️ Perbandingan Saham")
    st.markdown("---")
    st.info("💡 Area ini akan diisi kode Python dari Prompt Perbandingan Saham Anda.")
    # [TEMPEL KODE DI SINI NANTI]

def fitur_screening():
    st.title("🔍 Screening Harian")
    st.markdown("---")
    st.info("💡 Area ini akan diisi kode Python dari Prompt Screening Saham Anda.")
    # [TEMPEL KODE DI SINI NANTI]

def halaman_beranda():
    st.title("Selamat Datang, Pak Musa")
    st.image("https://images.unsplash.com/photo-1611974765270-ca1258634369?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80", caption="Market Dashboard")
    st.write("""
    Silakan pilih menu di sebelah kiri (Sidebar) untuk mulai melakukan analisa:
    
    * **Fundamental**: Cek kesehatan laporan keuangan perusahaan.
    * **Teknikal**: Cek grafik dan indikator harga.
    * **Perbandingan**: Adu performa dua saham.
    * **Screening**: Cari saham potensial hari ini.
    """)

# ==========================================
# BAGIAN 3: LOGIKA UTAMA (MAIN)
# ==========================================

# Inisialisasi Session State
if 'status_login' not in st.session_state:
    st.session_state['status_login'] = False

def main():
    local_css() # Panggil gaya tambahan
    
    # --- LOGIKA 1: BELUM LOGIN ---
    if not st.session_state['status_login']:
        # Buat kolom agar form login ada di tengah (tidak terlalu lebar)
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("<br><br>", unsafe_allow_html=True) # Spasi atas
            st.image("https://cdn-icons-png.flaticon.com/512/2910/2910311.png", width=100)
            st.title("Login Aplikasi")
            st.write("Silakan masukkan kode akses premium Anda.")
            
            input_pass = st.text_input("Kode Akses", type="password")
            tombol_masuk = st.button("Masuk Aplikasi", use_container_width=True)
            
            if tombol_masuk:
                if input_pass == PASSWORD_RAHASIA:
                    st.session_state['status_login'] = True
                    st.rerun()
                else:
                    st.error("Kode akses salah.")

    # --- LOGIKA 2: SUDAH LOGIN (TAMPILAN UTAMA) ---
    else:
        # --- SIDEBAR MENU ---
        with st.sidebar:
            st.header("Musa Stock Pro")
            st.write(f"User: Pak Musa")
            st.markdown("---")
            
            # Pilihan Menu dengan Radio Button
            pilihan_menu = st.radio(
                "Pilih Fitur:",
                ("🏠 Beranda", "📊 Fundamental", "📈 Teknikal", "⚖️ Perbandingan", "🔍 Screening")
            )
            
            st.markdown("---")
            if st.button("Log Out / Keluar"):
                st.session_state['status_login'] = False
                st.rerun()

        # --- KONTEN UTAMA BERDASARKAN PILIHAN ---
        if pilihan_menu == "🏠 Beranda":
            halaman_beranda()
        elif pilihan_menu == "📊 Fundamental":
            fitur_fundamental()
        elif pilihan_menu == "📈 Teknikal":
            fitur_teknikal()
        elif pilihan_menu == "⚖️ Perbandingan":
            fitur_perbandingan()
        elif pilihan_menu == "🔍 Screening":
            fitur_screening()

if __name__ == "__main__":
    main()