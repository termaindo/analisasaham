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

# --- 3. CSS CUSTOM (GABUNGAN DASHBOARD & LANDING PAGE) ---
st.markdown("""
<style>
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    [data-testid="stSidebar"] {display: none;}
    footer {visibility: hidden;}
    
    /* Style Tombol Menu Dashboard */
    div.stButton > button {
        width: 100%; border-radius: 12px; height: 85px;
        font-weight: bold; font-size: 18px;
        background-color: #1e2b3e; color: white; border: 1px solid #4a4a4a;
        margin-bottom: 10px;
    }
    div.stButton > button:hover {
        background-color: #ff0000; border-color: #ff0000; color: white;
    }
    
    /* Style Tombol Beli (Lynk.id) */
    [data-testid="stLinkButton"] a {
        background-color: #2ECC71 !important;
        color: white !important;
        border-radius: 12px !important;
        border: none !important;
        font-weight: bold !important;
        height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
        text-decoration: none !important;
        font-size: 1.1em !important;
    }
    [data-testid="stLinkButton"] a:hover {
        background-color: #27ae60 !important;
        box-shadow: 0 4px 15px rgba(46, 204, 113, 0.4);
    }

    .back-btn-container button {
        height: 40px !important; background-color: #444 !important; font-size: 14px !important;
    }

    /* Style Landing Page Header */
    .landing-header {
        text-align: center; 
        padding: 30px; 
        background-color: #1E1E1E; 
        border-radius: 15px; 
        border: 1px solid #2ECC71;
        margin-bottom: 30px;
    }
</style>
""", unsafe_allow_html=True)

# --- 4. SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_name' not in st.session_state: st.session_state.user_name = ""
if 'current_menu' not in st.session_state: st.session_state.current_menu = "Beranda"

# --- 5. HALAMAN LOGIN (LANDING PAGE KONVERSI) ---
def login_page():
    # Header Landing Page
    st.markdown("""
        <div class="landing-header">
            <h1 style="color: #2ECC71; margin-bottom: 10px;">🚀 Level Up Analisa Saham Anda ke Standar Institusi!</h1>
            <p style="font-size: 1.2em; color: #FFFFFF;">Berhenti menebak arah pasar. Gunakan data, bukan perasaan.</p>
        </div>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns([1.2, 1], gap="large")

    with col_left:
        st.markdown("""
        ### 🧐 Mengapa Expert Stock Pro?
        Banyak trader rugi karena **telat entry** atau **salah pilih emiten** akibat data yang berantakan. Kami menyatukan semuanya untuk Anda:
        
        * ✅ **6 Modul Analisa Premium:** Dari Teknikal Pro hingga Kalkulator Dividen.
        * ✅ **Screening Otomatis:** Temukan saham *undervalued* dalam hitungan detik.
        * ✅ **Risk Management:** Fitur Stop Loss & Target Price otomatis di setiap analisa.
        * ✅ **Data Real-Time:** Akses langsung ke data pasar Bursa Efek Indonesia.
        
        **Jangan biarkan peluang cuan lewat begitu saja hanya karena Anda kurang tools profesional.**
        """)

    with col_right:
        st.info("### 🔑 Masuk ke Sistem")
        with st.form("login_form"):
            nama = st.text_input("👤 Nama Panggilan", placeholder="Contoh: Sobat Musa")
            pw = st.text_input("🔑 Password Akses", type="password", placeholder="Masukkan kode akses...")
            
            submit_button = st.form_submit_button("BUKA AKSES DASHBOARD", use_container_width=True)
            
            if submit_button:
                try: 
                    correct = st.secrets["PASSWORD_RAHASIA"]
                except: 
                    correct = "12345" # Fallback jika secrets belum diset
                
                if pw.strip() == correct:
                    if nama.strip() == "": 
                        st.warning("Isi nama panggilan terlebih dahulu.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.user_name = nama
                        st.rerun()
                else: 
                    st.error("Kode akses salah atau sudah kadaluwarsa.")
        
        st.markdown("---")
        st.markdown("<p style='text-align: center; color: #A0A0A0;'>Belum punya akses premium seumur hidup?</p>", unsafe_allow_html=True)
        st.link_button("🛒 DAPATKAN KODE AKSES SEKARANG", "https://lynk.id/musa_tanaja", use_container_width=True)
        st.markdown("<p style='text-align: center; font-size: 0.8em; color: #888; margin-top: 10px;'>💳 Aktivasi Instan via Lynk.id</p>", unsafe_allow_html=True)

# --- 6. DASHBOARD (SESUAI ASLINYA) ---
def show_dashboard():
    st.markdown(f"### 👋 Halo Sobat <span style='color:#ff0000'>{st.session_state.user_name}</span>!", unsafe_allow_html=True)
    
    with st.expander("📖 3 Langkah Mudah Memakai Aplikasi Expert Stock Pro (Baca Ini Dulu)"):
        st.markdown("""
#### **1. Cara Mulai Analisa**
* Pilih menu Analisa yang mau dilakukan, lalu klik menu tersebut di Bawah ini.
#### **2. Masukkan Kode Saham (Contoh: BBRI atau BBRI.JK).**
* Setelah masukkan Kode Saham, lalu klik tombol "Mulai Analisa".
#### **3. Kembali ke "Menu Utama"**
* Bila sudah selesai analisa, klik tombol menu "Menu Utama" untuk kembali ke Beranda.
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

# --- 7. MAIN ROUTER (SESUAI ASLINYA) ---
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
            st.error(f"Terjadi kesalahan sistem: {e}")

if __name__ == "__main__":
    if st.session_state.logged_in:
        main_app()
    else:
        login_page()
