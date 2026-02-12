import streamlit as st
from streamlit_option_menu import option_menu

# --- IMPORT MODUL (Pastikan file-file ini ada di folder modules) ---
try:
    from modules import screening, teknikal, fundamental, dividen, perbandingan
except ImportError:
    st.error("⚠️ Error: File modul tidak ditemukan. Pastikan folder 'modules' berisi file: screening.py, teknikal.py, fundamental.py, dividen.py, perbandingan.py")
    st.stop()

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Expert Stock Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS: TAMPILAN PREMIUM & SEMBUNYIKAN HEADER ---
st.markdown("""
    <style>
    /* 1. Menyembunyikan Header Streamlit, Tombol Fork, & GitHub */
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    
    /* 2. Styling Tombol Merah Khas */
    div.stButton > button {
        background-color: #ff0000;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        border: none;
        padding: 10px 24px;
        transition: all 0.3s;
    }
    div.stButton > button:hover {
        background-color: #cc0000;
        transform: scale(1.02);
        color: white;
    }

    /* 3. Styling Kartu Dashboard */
    .dashboard-card {
        background-color: #1e2b3e;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #ff0000;
        margin-bottom: 10px;
    }
    h4 { margin-top: 0; color: #ffffff; }
    p { color: #cccccc; font-size: 0.9rem; }
    </style>
""", unsafe_allow_html=True)

# --- INISIALISASI SESSION STATE (Untuk Login & Navigasi) ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""
if 'current_menu' not in st.session_state:
    st.session_state.current_menu = "Beranda"

# --- FUNGSI LOGIN (GERBANG) ---
def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #ff0000;'>🔒 EXPERT STOCK PRO</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Silakan masuk untuk mengakses data pasar premium.</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            # INPUT NAMA (Akan disimpan untuk sapaan)
            input_nama = st.text_input("👤 Nama Panggilan Anda", placeholder="Contoh: Pak Musa")
            
            # INPUT PASSWORD
            password = st.text_input("🔑 Password Akses", type="password")
            
            submit = st.form_submit_button("MASUK SISTEM", use_container_width=True)

            if submit:
                # GANTI PASSWORD DI SINI (Default: 12345)
                if password == "12345":  
                    if input_nama.strip() == "":
                        st.warning("Mohon isi nama panggilan Anda.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.user_name = input_nama
                        st.rerun() # Refresh halaman untuk masuk
                else:
                    st.error("Password salah. Silakan coba lagi.")

# --- HALAMAN UTAMA (SETELAH LOGIN) ---
def main_app():
    # 1. SIDEBAR MENU
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user_name}")
        st.markdown("---")
        
        # Mapping Index Menu agar sinkron dengan tombol dashboard
        menu_options = ["Beranda", "Screening Harian", "Analisa Teknikal", "Analisa Fundamental", "Analisa Dividen", "Perbandingan Saham"]
        
        # Menentukan index default berdasarkan pilihan terakhir
        try:
            default_index = menu_options.index(st.session_state.current_menu)
        except ValueError:
            default_index = 0

        selected = option_menu(
            menu_title="Navigasi Utama",
            options=menu_options,
            icons=["house", "search", "graph-up-arrow", "building", "cash-coin", "scales"],
            menu_icon="cast",
            default_index=default_index,
            styles={
                "container": {"padding": "5!important", "background-color": "#0e1117"},
                "icon": {"color": "orange", "font-size": "18px"}, 
                "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#262730"},
                "nav-link-selected": {"background-color": "#ff0000"},
            }
        )
        
        # Update session state jika menu diklik dari sidebar
        if selected != st.session_state.current_menu:
            st.session_state.current_menu = selected
            st.rerun()
            
        st.markdown("---")
        if st.button("Keluar / Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_name = ""
            st.rerun()

    # 2. LOGIKA KONTEN UTAMA
    if st.session_state.current_menu == "Beranda":
        show_dashboard()
    elif st.session_state.current_menu == "Screening Harian":
        screening.run_screening()
    elif st.session_state.current_menu == "Analisa Teknikal":
        teknikal.run_teknikal()
    elif st.session_state.current_menu == "Analisa Fundamental":
        fundamental.run_fundamental()
    elif st.session_state.current_menu == "Analisa Dividen":
        dividen.run_dividen()
    elif st.session_state.current_menu == "Perbandingan Saham":
        perbandingan.run_perbandingan()

# --- FUNGSI TAMPILAN DASHBOARD (BERANDA) ---
def show_dashboard():
    # Sapaan Personal
    st.title(f"👋 Selamat Datang, {st.session_state.user_name}!")
    st.markdown("### Dashboard Navigasi Pasar Saham")
    st.write("Silakan pilih modul analisa yang ingin Anda gunakan hari ini:")
    st.markdown("---")

    # GRID NAVIGASI (Pengganti Hamburger Menu)
    # Baris 1
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        <div class="dashboard-card">
            <h4>🔍 Screening Harian</h4>
            <p>Temukan saham yang sedang bergerak liar hari ini dengan momentum tinggi & volume spike.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Buka Screening ➔", key="btn_scr"):
            st.session_state.current_menu = "Screening Harian"
            st.rerun()

    with c2:
        st.markdown("""
        <div class="dashboard-card">
            <h4>📈 Analisa Teknikal</h4>
            <p>Lihat chart candlestick, indikator RSI, MACD, dan tentukan titik entry/exit.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Buka Chart Teknikal ➔", key="btn_tek"):
            st.session_state.current_menu = "Analisa Teknikal"
            st.rerun()

    # Baris 2
    c3, c4 = st.columns(2)
    with c3:
        st.markdown("""
        <div class="dashboard-card">
            <h4>💰 Analisa Dividen</h4>
            <p>Cari saham 'sapi perah' dengan yield tinggi dan fundamental cashflow kuat.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Cek Dividen ➔", key="btn_div"):
            st.session_state.current_menu = "Analisa Dividen"
            st.rerun()

    with c4:
        st.markdown("""
        <div class="dashboard-card">
            <h4>📊 Analisa Fundamental</h4>
            <p>Bedah laporan keuangan, valuasi wajar (Fair Value), dan Margin of Safety.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Cek Fundamental ➔", key="btn_fund"):
            st.session_state.current_menu = "Analisa Fundamental"
            st.rerun()
            
    # Baris 3 (Tambahan)
    c5, c6 = st.columns(2)
    with c5:
        st.markdown("""
        <div class="dashboard-card">
            <h4>⚖️ Perbandingan Saham</h4>
            <p>Head-to-head dua saham untuk menentukan mana yang lebih layak beli.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Mulai Bandingkan ➔", key="btn_comp"):
            st.session_state.current_menu = "Perbandingan Saham"
            st.rerun()

# --- EKSEKUSI PROGRAM ---
if __name__ == "__main__":
    if st.session_state.logged_in:
        main_app()
    else:
        login_page()
