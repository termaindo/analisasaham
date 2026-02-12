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
            nama = st.text_input("👤 Nama Panggilan", placeholder="Contoh: Sobat Musa")
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
    
    with st.expander("📖 Panduan Penggunaan & Istilah (Baca Ini Dulu)"):
        st.markdown("""
        #### **1. Cara Mulai Analisa**
        * Pilih menu di bawah. Masukkan kode saham (Contoh: `BBRI` atau `BBRI.JK`).
        #### **2. Memahami Grafik**
        * 🟡 **MA20 Kuning:** Tren pendek. 🟣 **MA200 Ungu:** Tren panjang.
        #### **3. Strategi ATR**
        * SL & TP dihitung otomatis berdasarkan volatilitas, dengan **batas risiko maksimal 8%**.
        #### **4. Tips Anti-Error**
