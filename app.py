import streamlit as st
import importlib.util
import sys

# --- 1. CONFIG HALAMAN ---
st.set_page_config(
    page_title="Expert Stock Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. SISTEM AKSES (GERBANG KONVERSI) ---
# Ganti 'RAHASIA123' dengan sistem validasi Bapak atau input dari Lynk.id
KODE_AKSES_BENAR = "2026" 

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

def check_access():
    if st.session_state['input_kode'] == KODE_AKSES_BENAR:
        st.session_state['authenticated'] = True
        st.success("Akses Diterima! Membuka Dashboard...")
        st.rerun()
    else:
        st.error("Kode akses salah atau sudah kadaluwarsa.")

# --- TAMPILAN HALAMAN JUALAN (KONTEN KONVERSI) ---
if not st.session_state['authenticated']:
    st.markdown("""
        <div style="text-align: center; padding: 20px; background-color: #1E1E1E; border-radius: 15px; border: 1px solid #2ECC71;">
            <h1 style="color: #2ECC71; margin-bottom: 10px;">🚀 Level Up Analisa Saham Anda ke Standar Institusi!</h1>
            <p style="font-size: 1.2em; color: #FFFFFF;">Berhenti menebak arah pasar. Gunakan data, bukan perasaan.</p>
        </div>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("""
        ### 🧐 Mengapa Expert Stock Pro?
        Banyak trader rugi karena **telat entry** atau **salah pilih emiten** akibat data yang berantakan. Kami menyatukan semuanya untuk Anda:
        
        * ✅ **6 Modul Analisa Premium:** Dari Teknikal Pro hingga Kalkulator Dividen.
        * ✅ **Screening Otomatis:** Temukan saham *undervalued* dalam hitungan detik.
        * ✅ **Risk Management:** Fitur Stop Loss & Target Price otomatis di setiap analisa.
        * ✅ **Data Real-Time:** Akses langsung ke data pasar Bursa Efek Indonesia.
        
        **Jangan biarkan peluang cuan lewat begitu saja hanya karena Anda kurang tools.**
        """)

    with col_right:
        st.info("### 🔑 Masukkan Kode Akses")
        st.text_input("Kode unik Anda:", type="password", key="input_kode")
        st.button("Buka Akses Dashboard", on_click=check_access, use_container_width=True)
        
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center;">
            <p style="color: #A0A0A0;">Belum punya kode akses?</p>
            <a href="https://lynk.id/musa_tanaja" target="_blank">
                <button style="background-color: #2ECC71; color: white; padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; width: 100%; font-weight: bold; font-size: 1.1em;">
                    DAPATKAN KODE AKSES SEKARANG (PROMO TERBATAS)
                </button>
            </a>
            <p style="font-size: 0.8em; color: #888; margin-top: 10px;">💳 Aktivasi Instan via Lynk.id</p>
        </div>
        """, unsafe_allow_html=True)
    st.stop() # Hentikan eksekusi kode di bawah jika belum login

# --- 3. LANJUT KE LOAD MODUL (HANYA JIKA SUDAH LOGIN) ---
def load_module(module_name):
    try:
        return importlib.import_module(f"modules.{module_name}")
    except ImportError as e:
        st.error(f"🚨 Gagal memuat {module_name}.py. Error: {e}")
        return None

mod_screening = load_module("screening")
mod_cepat = load_module("analisa_cepat")
mod_teknikal = load_module("teknikal")
mod_fundamental = load_module("fundamental")
mod_dividen = load_module("dividen")
mod_perbandingan = load_module("perbandingan")

# --- 4. NAVIGATION SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Expert Stock Pro")
    menu = st.radio("Pilih Menu Analisa:", 
                   ["Dashboard", "Screening Saham", "Analisa Cepat", "Teknikal Pro", "Fundamental Depth", "Dividen Hunter", "Bandingkan Emiten"])
    
    if st.button("Log Out"):
        st.session_state['authenticated'] = False
        st.rerun()

# Logika navigasi menu selanjutnya...
if menu == "Screening Saham":
    mod_screening.run_screening()
# ... (lanjutkan untuk menu lainnya)
