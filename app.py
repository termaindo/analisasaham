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

# --- 2. SISTEM KEAMANAN (STREAMLIT SECRETS) ---
# Diasumsikan Bapak menyimpan kode di Secrets dengan nama: ACCESS_CODE
KODE_AKSES_VALID = st.secrets["ACCESS_CODE"]

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

def check_access():
    if st.session_state.input_user_kode == KODE_AKSES_VALID:
        st.session_state['authenticated'] = True
    else:
        st.error("⚠️ Kode akses salah. Pastikan Anda menyalin kode dengan benar dari Lynk.id.")

# --- 3. HALAMAN GERBANG (HIGH CONVERSION COPYWRITING) ---
if not st.session_state['authenticated']:
    # Centering content with CSS
    st.markdown("""
        <style>
        .main-container {
            text-align: center;
            padding: 3rem;
            border-radius: 15px;
            background: linear-gradient(145deg, #1e1e1e, #252525);
            border: 1px solid #2ECC71;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
        .cta-button {
            background-color: #2ECC71 !important;
            color: white !important;
            font-weight: bold !important;
            padding: 15px 30px !important;
            text-decoration: none !important;
            border-radius: 8px !important;
            display: inline-block;
            margin-top: 20px;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="main-container">
            <h1 style="color: #2ECC71;">💰 Berhenti Menebak, Mulai Menang.</h1>
            <p style="font-size: 1.3em; color: #ecf0f1;">
                Ubah cara Anda menganalisa pasar dengan <b>Expert Stock Pro</b>.<br>
                Satu dashboard untuk keputusan investasi yang presisi, cepat, dan objektif.
            </p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.markdown("### 🛠️ Apa yang Anda Dapatkan?")
        st.markdown("""
        * 🚀 **Screening Instant:** Temukan saham 'salah harga' sebelum bandar bergerak.
        * 📊 **Teknikal Pro:** Indikator otomatis yang sudah dikalibrasi untuk market IHSG.
        * 💎 **Dividend Hunter:** Kalkulator proyeksi passive income yang akurat.
        * 🛡️ **Risk Manager:** Level Stop Loss & Target Price yang dihitung secara matematis.
        
        *Didisain khusus untuk investor yang ingin hasil profesional tanpa harus pusing melihat ratusan tab browser.*
        """)

    with col2:
        st.write("### 🔑 Akses Dashboard")
        st.text_input("Masukkan Kode Akses Anda:", type="password", key="input_user_kode", placeholder="Paste kode di sini...")
        st.button("Buka Akses Sekarang", on_click=check_access, use_container_width=True)
        
        st.markdown("---")
        st.markdown("""
            <div style="text-align: center;">
                <p style="margin-bottom: 10px;">Belum punya kode akses atau masa aktif habis?</p>
                <a href="https://lynk.id/musa_tanaja" target="_blank" class="cta-button">
                    DAPATKAN KODE AKSES INSTAN DI SINI
                </a>
                <p style="font-size: 0.8em; color: #95a5a6; margin-top: 15px;">
                    ⚡ Pembayaran otomatis & kode dikirim detik ini juga via Lynk.id
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    st.stop() # Mengunci semua fitur di bawah agar tidak dimuat sebelum login

# --- 4. IMPORT MODUL (HANYA JIKA SUDAH AUTHENTICATED) ---
def load_module(module_name):
    try:
        return importlib.import_module(f"modules.{module_name}")
    except ImportError as e:
        st.error(f"🚨 Gagal memuat {module_name}.py. Error: {e}")
        return None

# Load semua modul
mod_screening = load_module("screening")
mod_cepat = load_module("analisa_cepat")
mod_teknikal = load_module("teknikal")
mod_fundamental = load_module("fundamental")
mod_dividen = load_module("dividen")
mod_perbandingan = load_module("perbandingan")

# --- 5. LOGIKA MENU (LANJUTAN KODE BAPAK) ---
st.sidebar.title("🛡️ Expert Stock Pro")
# ... Tambahkan navigasi menu di sini ...
