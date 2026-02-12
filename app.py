import streamlit as st
# Pastikan semua file ini ada di dalam folder modules Bapak
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
    PASSWORD_RAHASIA = "12345"

LINK_LYNK_ID = "https://lynk.id/hahastoresby"

# --- CSS CUSTOM (Tampilan Tombol Merah & Layout) ---
st.markdown("""
<style>
    /* CSS yang sudah ada untuk tombol merah (Biarkan saja) */
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

    /* --- TAMBAHAN BARU UNTUK SIDEBAR --- */
    /* 1. Menyembunyikan ikon panah/segitiga bawaan Streamlit */
    button[kind="header"] > svg {
        display: none !important;
    }

    /* 2. Menambahkan ikon Hamburger (☰) dan tulisan "MENU" */
    button[kind="header"]::before {
        content: "☰ MENU";  /* Unicode untuk tiga garis + teks */
        font-size: 1.1rem;
        font-weight: 700;  /* Bold */
        color: white;      /* Warna teks putih agar kontras dengan background gelap */
        margin-right: 10px;
    }

    /* 3. (Opsional) Mengubah warna tombol saat disorot mouse agar lebih interaktif */
    button[kind="header"]:hover {
        color: #ff0000 !important; /* Berubah merah saat di-hover */
    }
    button[kind="header"]:hover::before {
         color: #ff0000 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. LOGIKA LOGIN (GERBANG DEPAN)
# ==========================================
if 'status_login' not in st.session_state:
    st.session_state['status_login'] = False

if not st.session_state['status_login']:
    # Layout Tengah seperti hal awal aplikasisehat.jpeg
    _, col_login, _ = st.columns([1, 2, 1])
    
    with col_login:
        st.markdown("<h1 style='font-size: 50px;'>📈 Expert <br> Stock Pro</h1>", unsafe_allow_html=True)
        st.write("Selamat datang di Aplikasi Analisa Saham & Trading.")
        st.markdown("---")
        
        st.write("🔑 **Masukkan Kode Akses Premium:**")
        input_pass = st.text_input("Ketik kode akses Anda di sini...", type="password", label_visibility="collapsed")
        
        if st.button("Buka Aplikasi", use_container_width=True):
            if input_pass == PASSWORD_RAHASIA:
                st.session_state['status_login'] = True
                st.rerun()
            else:
                st.error("Kode akses salah. Silakan coba lagi.")

        st.info("🔒 Aplikasi ini dikunci khusus untuk Member Premium.")
        st.markdown("<br>", unsafe_allow_html=True)
        st.write("**Belum punya Kode Akses?** Dapatkan panduan trading lengkap, sinyal harian, dan akses aplikasi seumur hidup dengan biaya terjangkau.")
        st.link_button("🛒 Beli Manual dan Kode Akses (Klik Di Sini)", LINK_LYNK_ID, use_container_width=True)

else:
    # ==========================================
    # 3. SIDEBAR & NAVIGASI 5 MENU
    # ==========================================
    with st.sidebar:
        st.header("Expert Stock Pro")
        st.success("Status: Member Premium")
        st.markdown("---")
        
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
    # 4. ROUTING HALAMAN
    # ==========================================
    if pilihan_menu == "🏠 Beranda":
        st.title("🏠 Dashboard Utama")
        st.write(f"Selamat datang, Pak Musa. Silakan pilih fitur di sidebar.")
        # Visual bantuan untuk Bapak
        st.info("**Tips:** Mulailah dengan Screening Harian untuk mencari peluang, lalu bedah secara teknikal.")

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

