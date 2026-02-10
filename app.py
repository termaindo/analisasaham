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

# --- PASSWORD & LINK PEMBELIAN ---
PASSWORD_RAHASIA = "SUKSES2026"  # Ganti dengan password yang Bapak mau
LINK_LYNK_ID = "https://lynk.id/musatanaja" # Ganti dengan link Lynk.id Bapak yang asli

# ==========================================
# BAGIAN 1: CSS CUSTOM (Agar Tampilan Mirip Aplikasi Sehat)
# ==========================================
def local_css():
    st.markdown("""
    <style>
    /* Mengubah warna tombol Link (Beli) menjadi Merah agar mirip screenshot */
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
    
    /* Mempercantik kotak info biru */
    .stAlert {
        border-radius: 10px;
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

def fitur_teknikal():
    st.title("📈 Analisa Teknikal")
    st.markdown("---")
    st.info("💡 Area ini akan diisi kode Python dari Prompt Analisa Teknikal Anda.")

def fitur_perbandingan():
    st.title("⚖️ Perbandingan Saham")
    st.markdown("---")
    st.info("💡 Area ini akan diisi kode Python dari Prompt Perbandingan Saham Anda.")

def fitur_screening():
    st.title("🔍 Screening Harian")
    st.markdown("---")
    st.info("💡 Area ini akan diisi kode Python dari Prompt Screening Saham Anda.")

def halaman_beranda():
    st.title("Selamat Datang di Dashboard Saham")
    st.image("https://images.unsplash.com/photo-1611974765270-ca1258634369?ixlib=rb-4.0.3&auto=format&fit=crop&w=1000&q=80", caption="Market Overview")
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
    
    # --- TAMPILAN 1: BELUM LOGIN (GERBANG DEPAN) ---
    if not st.session_state['status_login']:
        
        # Kita buat kolom di tengah agar rapi (seperti tampilan HP di desktop)
        col_space_1, col_login, col_space_2 = st.columns([1, 2, 1])
        
        with col_login:
            # 1. Judul & Logo (Saya pakai Emoji Grafik sebagai ganti daun)
            st.markdown("<h1 style='text-align: center;'>📈 Konsultan Saham Pro</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center;'>Selamat datang di Aplikasi Analisa Saham & Trading.</p>", unsafe_allow_html=True)
            
            st.markdown("---") # Garis Pembatas
            
            # 2. Input Password dengan Icon Kunci
            st.write("🔑 **Masukkan Kode Akses Premium:**")
            input_pass = st.text_input("Ketik kode akses Anda di sini...", type="password", label_visibility="collapsed")
            
            # Tombol Masuk (Kecil saja, di bawah password)
            if st.button("Buka Aplikasi", use_container_width=True, type="secondary"):
                if input_pass == PASSWORD_RAHASIA:
                    st.session_state['status_login'] = True
                    st.rerun()
                else:
                    st.error("Kode akses salah. Silakan coba lagi.")

            # 3. Kotak Biru (Info Terkunci)
            st.info("🔒 Aplikasi ini dikunci khusus untuk Member Premium.")
            
            st.markdown("<br>", unsafe_allow_html=True) # Spasi

            # 4. Teks Penawaran
            st.write("**Belum punya Kode Akses?** Dapatkan panduan trading lengkap, sinyal harian, dan akses aplikasi seumur hidup dengan biaya terjangkau.")
            
            # 5. Tombol Merah (Link Pembelian)
            # Menggunakan st.link_button agar mengarah ke web luar
            st.link_button("🛒 Beli Manual dan Kode Akses (Klik Di Sini)", LINK_LYNK_ID, use_container_width=True)

    # --- TAMPILAN 2: SUDAH LOGIN (DASHBOARD) ---
    else:
        # --- SIDEBAR MENU ---
        with st.sidebar:
            st.header("Musa Stock Pro")
            st.success("Status: Member Premium")
            st.markdown("---")
            
            # Pilihan Menu
            pilihan_menu = st.radio(
                "Pilih Fitur:",
                ("🏠 Beranda", "📊 Fundamental", "📈 Teknikal", "⚖️ Perbandingan", "🔍 Screening")
            )
            
            st.markdown("---")
            if st.button("Log Out / Keluar"):
                st.session_state['status_login'] = False
                st.rerun()

        # --- KONTEN UTAMA ---
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
