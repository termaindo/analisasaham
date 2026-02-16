import streamlit as st
import importlib.util
import sys

# --- 1. CONFIG HALAMAN ---
st.set_page_config(
    page_title="Expert Stock Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. IMPORT MODUL (MODE AMAN) ---
def load_module(module_name):
    """Mencoba load modul, jika gagal akan return None"""
    try:
        return importlib.import_module(f"modules.{module_name}")
    except ImportError:
        return None
    except SyntaxError as e:
        st.error(f"⚠️ Error Pengetikan di {module_name}.py: {e}")
        return None

# Load semua modul
mod_screening = load_module("screening")
mod_cepat = load_module("analisa_cepat")
mod_teknikal = load_module("teknikal")
mod_fundamental = load_module("fundamental")
mod_dividen = load_module("dividen")
mod_perbandingan = load_module("perbandingan")

# --- 3. CSS CUSTOM ---
st.markdown("""
<style>
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    [data-testid="stSidebar"] {display: none;}
    footer {visibility: hidden;}
    
    div.stButton > button {
        width: 100%; border-radius: 12px; height: 85px;
        font-weight: bold; font-size: 18px;
        background-color: #1e2b3e; color: white; border: 1px solid #4a4a4a;
        margin-bottom: 10px;
    }
    div.stButton > button:hover {
        background-color: #ff0000; border-color: #ff0000; color: white;
    }
    
    [data-testid="stLinkButton"] a {
        background-color: #ff0000 !important;
        color: white !important;
        border-radius: 12px !important;
        border: none !important;
        font-weight: bold !important;
        height: 50px;
        display: flex;
        align-items: center;
        justify-content: center;
        text-decoration: none !important;
    }
    [data-testid="stLinkButton"] a:hover {
        background-color: #cc0000 !important;
        color: white !important;
    }

    .back-btn-container button {
        height: 40px !important; background-color: #444 !important; font-size: 14px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 4. SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_name' not in st.session_state: st.session_state.user_name = ""
if 'current_menu' not in st.session_state: st.session_state.current_menu = "Beranda"

# --- 5. HALAMAN LOGIN ---
def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br><h1 style='text-align: center; color: #ff0000;'>🔒 EXPERT STOCK PRO</h1>", unsafe_allow_html=True)
        with st.form("login_form"):
            nama = st.text_input("👤 Silakan Masukkan Nama Panggilan Anda", placeholder="Contoh: Rudi")
            pw = st.text_input("🔑 Password Akses", type="password")
            if st.form_submit_button("MASUK SISTEM", use_container_width=True):
                try: correct = st.secrets["PASSWORD_RAHASIA"]
                except: correct = "12345"
                if pw.strip() == correct:
                    if nama.strip() == "": st.warning("Isi nama panggilan.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.user_name = nama
                        st.rerun()
                else: st.error("Password salah.")
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("🔒 Belum punya akses premium? Sekali beli, berlaku seumur hidup")
        st.link_button("🛒 Beli Akses via Lynk.id", "https://lynk.id/hahastoresby", use_container_width=True)

# --- 6. DASHBOARD ---
def show_dashboard():
    st.markdown(f"### 👋 Halo Sobat <span style='color:#ff0000'>{st.session_state.user_name}</span>!", unsafe_allow_html=True)
    
    with st.expander("📖 3 Langkah Mudah Memakai Aplikasi Expert Stock Pro (Baca Ini Dulu)"):
        st.markdown("""
#### **3 Langkah Mudah Memakai Aplikasi "Expert Stock Pro"**

#### **1. Cara Mulai Analisa**
* Pilih menu di bawah. Masukkan kode saham (Contoh: `BBRI` atau `BBRI.JK`), lalu tekan ENTER.
#### **2. Klik tombol "Mulai Jalankan / Analisa" di bagian bawah.**
#### **3. Klik tombol "Menu Utama" di bagian atas Menu Analisa, untuk kembali ke Halaman Depan**
        """)
    
    # JUDUL MENCOLOK (EXPERT STOCK PRO)
    st.markdown("<h1 style='text-align: center; color: #ff0000; letter-spacing: 2px;'>📈 EXPERT STOCK PRO</h1>", unsafe_allow_html=True)
    st.write("Silakan pilih menu analisa:")
    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 Screening Harian", use_container_width=True):
            st.session_state.current_menu = "screening"; st.rerun()
    with c2:
        label = "⚡ Analisa Cepat" if mod_cepat else "⚡ Analisa Cepat (Rusak)"
        if st.button(label, use_container_width=True):
            if mod_cepat:
                st.session_state.current_menu = "analisa_cepat"; st.rerun()
            else:
                st.error("Modul analisa_cepat.py bermasalah.")

    c3, c4 = st.columns(2)
    with c3:
        if st.button("📈 Teknikal Pro", use_container_width=True):
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
        st.session_state.logged_in = False; st.session_state.user_name = ""; st.rerun()

# --- 7. MAIN ROUTER ---
def main_app():
    if st.session_state.current_menu == "Beranda":
        show_dashboard()
    else:
        col_back, _ = st.columns([1, 4])
        with col_back:
            st.markdown('<div class="back-btn-container">', unsafe_allow_html=True)
            if st.button("⬅️ Menu Utama"):
                st.session_state.current_menu = "Beranda"; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("---")

        try:
            m = st.session_state.current_menu
            if m == "screening" and mod_screening: mod_screening.run_screening()
            elif m == "analisa_cepat" and mod_cepat: mod_cepat.run_analisa_cepat()
            elif m == "teknikal" and mod_teknikal: mod_teknikal.run_teknikal()
            elif m == "fundamental" and mod_fundamental: mod_fundamental.run_fundamental()
            elif m == "dividen" and mod_dividen: mod_dividen.run_dividen()
            elif m == "perbandingan" and mod_perbandingan: mod_perbandingan.run_perbandingan()
            else: st.error("Modul tidak ditemukan di folder 'modules'.")
        except Exception as e:
            st.error(f"Error sistem saat memuat modul: {e}")
    
if __name__ == "__main__":
    if st.session_state.logged_in:
        main_app()
    else:
        login_page()







