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

# --- 3. CSS CUSTOM (GABUNGAN PROFESIONAL & DASHBOARD) ---
st.markdown("""
<style>
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    footer {visibility: hidden;}
    
    /* Style Halaman Gerbang */
    .gate-container {
        text-align: center;
        padding: 2.5rem;
        border-radius: 15px;
        background: linear-gradient(145deg, #1e1e1e, #252525);
        border: 1px solid #2ECC71;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        margin-bottom: 25px;
    }
    
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
    
    /* Style Tombol Link Beli */
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
</style>
""", unsafe_allow_html=True)

# --- 4. SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_name' not in st.session_state: st.session_state.user_name = ""
if 'current_menu' not in st.session_state: st.session_state.current_menu = "Beranda"

# --- 5. HALAMAN LOGIN (GERBANG KONVERSI) ---
def login_page():
    # Header Gate
    st.markdown("""
        <div class="gate-container">
            <h1 style="color: #2ECC71; margin-bottom: 0;">💰 Berhenti Menebak, Mulai Menang.</h1>
            <p style="font-size: 1.2em; color: #ecf0f1; margin-top: 10px;">
                Ubah cara Anda menganalisa pasar dengan <b>Expert Stock Pro</b>.<br>
                Satu dashboard untuk keputusan investasi yang presisi dan objektif.
            </p>
        </div>
    """, unsafe_allow_html=True)

    col_info, col_login = st.columns([1.2, 1], gap="large")

    with col_info:
        st.markdown("### 🛠️ Apa yang Anda Dapatkan?")
        st.markdown("""
        * 🚀 **Screening Instant:** Temukan saham 'salah harga' dalam hitungan detik.
        * 📊 **Teknikal Pro:** Indikator otomatis yang sudah terkalibrasi market IHSG.
        * 💎 **Dividend Hunter:** Proyeksi passive income untuk masa pensiun tenang.
        * 🛡️ **Risk Manager:** Level Stop Loss & TP otomatis (Maksimal Risiko 8%).
        
        <p style="color: #A0A0A0; font-style: italic; margin-top: 15px;">
        "Didesain khusus untuk investor yang ingin hasil profesional tanpa pusing melihat ratusan data mentah."
        </p>
        """, unsafe_allow_html=True)

    with col_login:
        st.markdown("### 🔑 Masuk Dashboard")
        with st.form("login_form"):
            nama = st.text_input("👤 Nama Panggilan", placeholder="Contoh: Sobat Musa")
            pw = st.text_input("🔑 Kode Akses Premium", type="password", placeholder="Masukkan kode akses...")
            
            submit = st.form_submit_button("BUKA AKSES SEKARANG", use_container_width=True)
            
            if submit:
                # Mengambil kode dari secrets dengan fallback
                try: 
                    correct_pw = st.secrets["ACCESS_CODE"]
                except: 
                    correct_pw = "12345" # Fallback jika secrets belum diatur
                
                if pw.strip() == correct_pw:
                    if nama.strip() == "": 
                        st.warning("Silakan isi nama panggilan Anda.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.user_name = nama
                        st.rerun()
                else: 
                    st.error("Kode akses salah atau sudah kadaluwarsa.")
        
        st.markdown("<p style='text-align: center; color: #888;'>Belum punya kode akses seumur hidup?</p>", unsafe_allow_html=True)
        st.link_button("🛒 DAPATKAN KODE AKSES INSTAN", "https://lynk.id/musa_tanaja", use_container_width=True)
        st.markdown("<p style='text-align: center; font-size: 0.8em; color: #555;'>⚡ Aktivasi otomatis via Lynk.id</p>", unsafe_allow_html=True)

# --- 6. DASHBOARD (SAMA DENGAN KODE ASLI BAPAK) ---
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
* Jika data tidak muncul, tunggu 1 menit lalu gunakan tombol **Clear Cache** di pojok kanan atas.
        """)
    
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

# --- 7. MAIN ROUTER (SAMA DENGAN KODE ASLI BAPAK) ---
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
