import streamlit as st

# --- 1. CONFIG HALAMAN (WAJIB DI PALING ATAS) ---
st.set_page_config(
    page_title="Expert Stock Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. IMPORT MODUL DENGAN AMAN ---
# Kita pisahkan import agar jika satu error, ketahuan yang mana
try:
    from modules import screening
    from modules import analisa_cepat
    from modules import teknikal
    from modules import fundamental
    from modules import dividen
    from modules import perbandingan
except ImportError as e:
    st.error(f"⚠️ Terjadi Kesalahan Import: {e}")
    st.info("Pastikan semua file di folder 'modules' memiliki akhiran .py (contoh: analisa_cepat.py)")
    st.stop()

# --- 3. CSS CUSTOM (TAMPILAN PREMIUM & HILANGKAN SIDEBAR) ---
st.markdown("""
    <style>
    /* Hilangkan Elemen Bawaan Streamlit */
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    [data-testid="stSidebar"] {display: none;} /* Hilangkan Sidebar Total */
    footer {visibility: hidden;}
    
    /* Styling Tombol Menu Utama (Dashboard) */
    div.stButton > button {
        width: 100%;
        border-radius: 12px;
        height: 90px; /* Tombol Tinggi */
        font-weight: bold;
        font-size: 20px;
        background-color: #1e2b3e;
        color: white;
        border: 1px solid #4a4a4a;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
    }
    
    /* Efek Hover Tombol */
    div.stButton > button:hover {
        background-color: #ff0000;
        color: white;
        border-color: #ff0000;
        transform: translateY(-3px);
        box-shadow: 0 6px 12px rgba(255, 0, 0, 0.4);
    }
    
    /* Styling Tombol Back (Kecil) */
    .back-btn-container button {
        height: 40px !important;
        background-color: #333 !important;
        font-size: 14px !important;
        border: none !important;
    }
    
    /* Styling Judul Sapaan */
    .sapaan {
        font-size: 28px;
        font-weight: bold;
        color: white;
        margin-bottom: 20px;
    }
    .sob { color: #ff0000; }
    </style>
""", unsafe_allow_html=True)

# --- 4. SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""
if 'current_menu' not in st.session_state:
    st.session_state.current_menu = "Beranda"

# --- 5. HALAMAN LOGIN ---
def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #ff0000;'>🔒 EXPERT STOCK PRO</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Portal Analisa Saham Profesional</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            input_nama = st.text_input("👤 Nama Panggilan", placeholder="Contoh: Sobat Musa")
            password = st.text_input("🔑 Password Akses", type="password")
            
            # Tombol Login
            submit = st.form_submit_button("MASUK SISTEM", use_container_width=True)

            if submit:
                # Cek Password (Secrets / Fallback)
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
        
        st.link_button("🛒 Beli Akses via Lynk.id (Klik Disini)", "https://lynk.id/hahastoresby", use_container_width=True)

# --- 6. DASHBOARD UTAMA (MENU BUTTON) ---
def show_dashboard():
    # Sapaan Sobat
    st.markdown(f"<div class='sapaan'>👋 Halo Sobat <span class='sob'>{st.session_state.user_name}</span>!</div>", unsafe_allow_html=True)
    st.write("Silakan pilih menu analisa di bawah ini:")
    st.markdown("---")

    # GRID MENU (3 Baris x 2 Kolom)
    # Gunakan Container agar rapi
    
    # BARIS 1
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 Screening Harian", use_container_width=True):
            st.session_state.current_menu = "screening"
            st.rerun()
    with c2:
        if st.button("⚡ Analisa Cepat", use_container_width=True):
            st.session_state.current_menu = "analisa_cepat"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True) # Spasi antar baris

    # BARIS 2
    c3, c4 = st.columns(2)
    with c3:
        if st.button("📈 Teknikal Mendalam", use_container_width=True):
            st.session_state.current_menu = "teknikal"
            st.rerun()
    with c4:
        if st.button("📊 Fundamental Pro", use_container_width=True):
            st.session_state.current_menu = "fundamental"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # BARIS 3
    c5, c6 = st.columns(2)
    with c5:
        if st.button("💰 Analisa Dividen", use_container_width=True):
            st.session_state.current_menu = "dividen"
            st.rerun()
    with c6:
        if st.button("⚖️ Perbandingan Saham", use_container_width=True):
            st.session_state.current_menu = "perbandingan"
            st.rerun()

    # Tombol Logout (Paling Bawah)
    st.markdown("---")
    if st.button("Keluar / Logout", key="logout_btn"):
        st.session_state.logged_in = False
        st.session_state.user_name = ""
        st.rerun()

# --- 7. LOGIKA NAVIGASI (MAIN ROUTER) ---
def main_app():
    # Jika di Beranda, tampilkan Dashboard Menu
    if st.session_state.current_menu == "Beranda":
        show_dashboard()
    
    # Jika masuk ke dalam menu
    else:
        # Tombol Kembali (Back) dengan styling khusus
        col_back, _ = st.columns([1, 4])
        with col_back:
            st.markdown('<div class="back-btn-container">', unsafe_allow_html=True)
            if st.button("⬅️ Menu Utama"):
                st.session_state.current_menu = "Beranda"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("---")

        # Panggil Modul Sesuai Pilihan
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

# --- 8. EKSEKUSI ---
if __name__ == "__main__":
    if st.session_state.logged_in:
        main_app()
    else:
        login_page()
