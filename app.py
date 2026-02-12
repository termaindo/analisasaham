import streamlit as st

# --- 1. IMPORT MODUL (Pastikan semua file ada di folder modules) ---
try:
    from modules import screening, analisa_cepat, teknikal, fundamental, dividen, perbandingan
except ImportError as e:
    st.error(f"⚠️ Error Import: {e}. Pastikan file analisa_cepat.py, screening.py, dll ada di folder 'modules'.")
    st.stop()

# --- 2. KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Expert Stock Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed" # Sidebar otomatis tertutup
)

# --- 3. CSS CUSTOM (TAMPILAN PREMIUM & HILANGKAN SIDEBAR) ---
st.markdown("""
    <style>
    /* Sembunyikan Header Streamlit & Sidebar Bawaan */
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    [data-testid="stSidebar"] {display: none;} /* Hilangkan Sidebar Total */
    
    /* Tombol Navigasi Menu Utama */
    .stButton > button {
        width: 100%;
        border-radius: 10px;
        height: 80px; /* Tombol Tinggi agar mudah dipencet */
        font-weight: bold;
        font-size: 18px;
        transition: all 0.3s;
        border: 1px solid #444;
    }
    
    /* Efek Hover Tombol */
    .stButton > button:hover {
        transform: scale(1.02);
        border-color: #ff0000;
        color: #ff0000;
    }

    /* Tombol Kembali (Back) lebih kecil */
    .back-btn > button {
        height: 40px !important;
        background-color: #333;
        color: white;
    }

    /* Kartu Dashboard */
    .dashboard-card {
        background-color: #1e2b3e;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #ff0000;
        margin-bottom: 10px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# --- 4. INISIALISASI SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""
if 'current_menu' not in st.session_state:
    st.session_state.current_menu = "Beranda"

# --- 5. HALAMAN LOGIN (GERBANG) ---
def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #ff0000;'>🔒 EXPERT STOCK PRO</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Portal Analisa Saham Profesional</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            # INPUT NAMA
            input_nama = st.text_input("👤 Nama Panggilan", placeholder="Contoh: Budi")
            
            # INPUT PASSWORD
            password = st.text_input("🔑 Password Akses", type="password")
            
            submit = st.form_submit_button("MASUK SISTEM", use_container_width=True)

            if submit:
                # Cek Password (Prioritas Secrets, Fallback ke 12345)
                try:
                    correct_pass = st.secrets["PASSWORD_RAHASIA"]
                except:
                    correct_pass = "12345"

                if password.strip() == correct_pass:  
                    if input_nama.strip() == "":
                        st.warning("Mohon isi nama panggilan Anda.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.user_name = input_nama
                        st.rerun()
                else:
                    st.error("Password salah. Silakan coba lagi.")

        # INFO PEMBELIAN (LYNK.ID)
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("🔒 Belum punya akses premium?")
        st.markdown("""
        <div style='text-align: center; margin-bottom: 10px;'>
            Dapatkan kode akses seumur hidup untuk fitur analisa lengkap.
        </div>
        """, unsafe_allow_html=True)
        
        # Link Button ke Lynk.id
        st.link_button("🛒 Beli Akses via Lynk.id (Klik Disini)", "https://lynk.id/hahastoresby", use_container_width=True)

# --- 6. DASHBOARD UTAMA (MENU PILIHAN) ---
def show_dashboard():
    # Sapaan Sobat
    st.title(f"👋 Halo Sobat {st.session_state.user_name}!")
    st.write("Menu Analisa Saham:")
    st.markdown("---")

    # GRID MENU (3 Baris x 2 Kolom)
    
    # Baris 1
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 Screening Saham Harian", use_container_width=True):
            st.session_state.current_menu = "screening"
            st.rerun()
    with c2:
        if st.button("⚡ Analisa Cepat", use_container_width=True):
            st.session_state.current_menu = "analisa_cepat"
            st.rerun()

    # Baris 2
    c3, c4 = st.columns(2)
    with c3:
        if st.button("📈 Analisa Teknikal Mendalam", use_container_width=True):
            st.session_state.current_menu = "teknikal"
            st.rerun()
    with c4:
        if st.button("📊 Analisa Fundamental", use_container_width=True):
            st.session_state.current_menu = "fundamental"
            st.rerun()

    # Baris 3
    c5, c6 = st.columns(2)
    with c5:
        if st.button("💰 Analisa Dividen", use_container_width=True):
            st.session_state.current_menu = "dividen"
            st.rerun()
    with c6:
        if st.button("⚖️ Perbandingan 2 Saham", use_container_width=True):
            st.session_state.current_menu = "perbandingan"
            st.rerun()

    # Tombol Logout
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Keluar / Logout", type="secondary", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_name = ""
        st.rerun()

# --- 7. LOGIKA NAVIGASI UTAMA ---
def main_app():
    # Jika di Beranda, tampilkan Dashboard Menu
    if st.session_state.current_menu == "Beranda":
        show_dashboard()
    
    # Jika masuk ke salah satu menu, tampilkan Tombol KEMBALI & Modulnya
    else:
        # Tombol Kembali ke Menu Utama
        col_back, _ = st.columns([1, 4])
        with col_back:
            st.markdown('<div class="back-btn">', unsafe_allow_html=True)
            if st.button("⬅️ Kembali ke Menu Utama"):
                st.session_state.current_menu = "Beranda"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # Router ke Modul
        if st.session_state.current_menu == "screening":
            screening.run_screening()
        elif st.session_state.current_menu == "analisa_cepat":
            analisa_cepat.run_analisa_cepat()
        elif st.session_state.current_menu == "teknikal":
            teknikal.run_teknikal()
        elif st.session_state.current_menu == "fundamental":
            fundamental.run_fundamental()
        elif st.session_state.current_menu == "dividen":
            dividen.run_dividen()
        elif st.session_state.current_menu == "perbandingan":
            perbandingan.run_perbandingan()

# --- 8. EKSEKUSI PROGRAM ---
if __name__ == "__main__":
    if st.session_state.logged_in:
        main_app()
    else:
        login_page()
