import streamlit as st
import modules.screening as screening

# 1. KONFIGURASI HALAMAN
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
    PASSWORD_RAHASIA = "12345"

LINK_LYNK_ID = "https://lynk.id/hahastoresby"

# --- CSS CUSTOM (Agar Tombol Berwarna Merah & Tampilan Rapih) ---
st.markdown("""
    <style>
    /* Mengubah warna tombol Link menjadi Merah */
    div.stLinkButton > a {
        background-color: #ff0000 !important;
        color: white !important;
        border: none !important;
        font-weight: bold !important;
    }
    div.stLinkButton > a:hover {
        background-color: #cc0000 !important;
        color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. LOGIKA LOGIN (GERBANG DEPAN)
if 'status_login' not in st.session_state:
    st.session_state['status_login'] = False

if not st.session_state['status_login']:
    # Struktur Layout Tengah
    _, col_login, _ = st.columns([1, 2, 1])
    
    with col_login:
        # Judul & Logo (Struktur sesuai hal awal aplikasisehat.jpeg)
        st.markdown("<h1 style='font-size: 50px;'>📈 Expert <br> Stock Pro</h1>", unsafe_allow_html=True)
        st.write("Selamat datang di Aplikasi Analisa Saham & Trading.")
        st.markdown("---")
        
        # Input Password
        st.write("🔑 **Masukkan Kode Akses Premium:**")
        input_pass = st.text_input("Ketik kode akses Anda di sini...", type="password", label_visibility="collapsed")
        
        if st.button("Buka Aplikasi", use_container_width=True):
            if input_pass == PASSWORD_RAHASIA:
                st.session_state['status_login'] = True
                st.rerun()
            else:
                st.error("Kode akses salah. Silakan coba lagi.")

        # Kotak Info Biru
        st.info("🔒 Aplikasi ini dikunci khusus untuk Member Premium.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Penawaran & Tombol Merah
        st.write("**Belum punya Kode Akses?** Dapatkan panduan trading lengkap, sinyal harian, dan akses aplikasi seumur hidup dengan biaya terjangkau.")
        st.link_button("🛒 Beli Manual dan Kode Akses (Klik Di Sini)", LINK_LYNK_ID, use_container_width=True)

else:
    # 3. SIDEBAR & NAVIGASI (Jika sudah login)
    with st.sidebar:
        st.header("Expert Stock Pro")
        st.success("Status: Member Premium")
        st.markdown("---")
        pilihan_menu = st.radio("Pilih Menu Fitur:", (
            "🏠 Beranda", 
            "🔍 1. Screening Harian", 
            "📈 2. Analisa Teknikal"
        ))
        if st.button("Keluar"):
            st.session_state['status_login'] = False
            st.rerun()

    # 4. ROUTING HALAMAN
    if pilihan_menu == "🏠 Beranda":
        st.title("Selamat Datang di Expert Stock Pro")
        st.write("Gunakan fitur di sidebar untuk memulai analisa.")
    elif pilihan_menu == "🔍 1. Screening Harian":
        screening.run_screening()
    else:
        st.info(f"Fitur {pilihan_menu} sedang disiapkan.")
