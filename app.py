import streamlit as st

# --- 1. CONFIG HALAMAN ---
st.set_page_config(
    page_title="Expert Stock Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. IMPORT MODUL ---
try:
    from modules import screening
    from modules import analisa_cepat
    from modules import teknikal
    from modules import fundamental
    from modules import dividen
    from modules import perbandingan
except ImportError as e:
    st.error(f"⚠️ Terjadi Kesalahan Import: {e}")
    st.info("Pastikan file analisa_cepat.py tidak memiliki error syntax.")
    st.stop()

# --- 3. CSS CUSTOM ---
st.markdown("""
    <style>
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    [data-testid="stSidebar"] {display: none;}
    footer {visibility: hidden;}
    
    /* Tombol Menu Besar */
    div.stButton > button {
        width: 100%;
        border-radius: 12px;
        height: 85px;
        font-weight: bold;
        font-size: 18px;
        background-color: #1e2b3e;
        color: white;
        border: 1px solid #4a4a4a;
        margin-bottom: 10px;
    }
    div.stButton > button:hover {
        background-color: #ff0000;
        border-color: #ff0000;
        color: white;
    }
    
    /* Tombol Back Kecil */
    .back-btn-container button {
        height: 40px !important;
        background-color: #444 !important;
        font-size: 14px !important;
    }
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
        
        with st.form("login_form"):
            input_nama = st.text_input("👤 Nama Panggilan", placeholder="Contoh: Sobat Musa")
            password = st.text_input("🔑 Password Akses", type="password")
            submit = st.form_submit_button("MASUK SISTEM", use_container_width=True)

            if submit:
                try: correct = st.secrets["PASSWORD_RAHASIA"]
                except: correct = "12345"

                if password.strip() == correct:  
                    if input_nama.strip() == "":
                        st.warning("Mohon isi nama panggilan.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.user_name = input_nama
                        st.rerun()
                else:
                    st.error("Password salah.")

        st.markdown("<br>", unsafe_allow_html=True)
        st.info("🔒 Belum punya akses premium?")
        st.link_button("🛒 Beli Akses via Lynk.id", "https://lynk.id/hahastoresby", use_container_width=True)

# --- 6. DASHBOARD MENU ---
def show_dashboard():
    st.markdown(f"### 👋 Halo Sobat <span style='color:#ff0000'>{st.session_state.user_name}</span>!", unsafe_allow_html=True)
    st.write("Silakan pilih menu analisa:")
    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 Screening Harian", use_container_width=True):
            st.session_state.current_menu = "screening"; st.rerun()
    with c2:
        if st.button("⚡ Analisa Cepat", use_container_width=True):
            st.session_state.current_menu = "analisa_cepat"; st.rerun()

    c3, c4 = st.columns(2)
    with c3:
        if st.button("📈 Teknikal Mendalam", use_container_width=True):
            st.session_state.current_menu = "teknikal"; st.rerun()
    with c4:
        if st.button("📊 Fundamental Pro", use_container_width=True):
            st.session_state.current_menu = "fundamental"; st.rerun()

    c5, c6 = st.columns(2)
    with c5:
        if st.button("💰 Analisa Dividen", use_container_width=True):
            st.session_state.current_menu = "dividen"; st.rerun()
    with c6:
        if st.button("⚖️ Perbandingan Saham", use_container_width=True):
            st.session_state.current_menu = "perbandingan"; st.rerun()

    st.markdown("---")
    if st.button("Keluar / Logout"):
        st.session_state.logged_in = False
        st.session_state.user_name = ""
        st.rerun()

# --- 7. MAIN ROUTER ---
def main_app():
    if st.session_state.current_menu == "Beranda":
        show_dashboard()
    else:
        # Tombol Back
        col_back, _ = st.columns([1, 4])
        with col_back:
            st.markdown('<div class="back-btn-container">', unsafe_allow_html=True)
            if st.button("⬅️ Menu Utama"):
                st.session_state.current_menu = "Beranda"; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("---")

        if st.session_state.current_menu == "screening": screening.run_screening()
        elif st.session_state.current_menu == "analisa_cepat": analisa_cepat.run_analisa_cepat()
        elif st.session_state.current_menu == "teknikal": teknikal.run_teknikal()
        elif st.session_state.current_menu == "fundamental": fundamental.run_fundamental()
        elif st.session_state.current_menu == "dividen": dividen.run_dividen()
        elif st.session_state.current_menu == "perbandingan": perbandingan.run_perbandingan()

if __name__ == "__main__":
    if st.session_state.logged_in: main_app()
    else: login_page()
