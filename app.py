import streamlit as st
# Memanggil modul-modul fitur dari folder modules
import modules.screening as screening
import modules.teknikal as teknikal
import modules.fundamental as fundamental
import modules.dividen as dividen
import modules.perbandingan as perbandingan

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="Expert Stock Pro", 
    page_icon="📈", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- KEAMANAN & LINK ---
try:
    PASSWORD_RAHASIA = st.secrets["PASSWORD_RAHASIA"]
except:
    PASSWORD_RAHASIA = "12345" # Cadangan jika lokal

LINK_LYNK_ID = "https://lynk.id/hahastoresby"

# ==========================================
# 2. LOGIKA LOGIN
# ==========================================
if 'status_login' not in st.session_state:
    st.session_state['status_login'] = False

if not st.session_state['status_login']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>📈 Expert Stock Pro</h1>", unsafe_allow_html=True)
        st.markdown("---")
        st.write("🔑 **Masukkan Kode Akses Premium:**")
        input_pass = st.text_input("Password", type="password", label_visibility="collapsed")
        
        if st.button("Buka Aplikasi", use_container_width=True):
            if input_pass == PASSWORD_RAHASIA:
                st.session_state['status_login'] = True
                st.rerun()
            else:
                st.error("Kode akses salah. Silakan coba lagi.")

        st.info("🔒 Aplikasi ini dikunci khusus untuk Member Premium.")
        st.link_button("🛒 Beli Kode Akses (Klik Di Sini)", LINK_LYNK_ID, use_container_width=True)
else:
    # ==========================================
    # 3. SIDEBAR & MENU NAVIGASI
    # ==========================================
    with st.sidebar:
        st.header("Expert Stock Pro")
        st.success("Status: Member Premium")
        st.markdown("---")
        
        # Urutan Menu sesuai permintaan Bapak
        pilihan_menu = st.radio(
            "Pilih Menu Fitur:",
            (
                "🏠 Beranda", 
                "🔍 1. Screening Harian", 
                "📈 2. Analisa Teknikal", 
                "📊 3. Analisa Fundamental",
                "💰 4. Analisa Dividen",
                "⚖️ 5. Perbandingan 2 Saham"
            )
        )
        
        st.markdown("---")
        if st.button("Log Out / Keluar"):
            st.session_state['status_login'] = False
            st.rerun()

    # ==========================================
    # 4. ROUTING HALAMAN (PEMANGGILAN MODUL)
    # ==========================================
    if pilihan_menu == "🏠 Beranda":
        st.title("Selamat Datang di Expert Stock Pro")
        st.markdown("---")
        st.write("Silakan pilih alat analisa di menu sebelah kiri untuk memulai.")
        
        # Ringkasan Fitur
        c1, c2 = st.columns(2)
        with c1:
            st.info("**Screener & Teknikal**\nCari peluang dengan sistem skor konfidensi dan bedah grafik harga secara detail.")
        with c2:
            st.info("**Fundamental & Dividen**\nCek kesehatan keuangan dan cari saham 'cash cow' untuk investasi jangka panjang.")

    elif pilihan_menu == "🔍 1. Screening Harian":
        screening.run_screening()
        
    elif pilihan_menu == "📈 2. Analisa Teknikal":
        teknikal.run_teknikal()
        
    elif pilihan_menu == "📊 3. Analisa Fundamental":
        fundamental.run_fundamental()
        
    elif pilihan_menu == "💰 4. Analisa Dividen":
        dividen.run_dividen()
        
    elif pilihan_menu == "⚖️ 5. Perbandingan 2 Saham":
        perbandingan.run_perbandingan()
