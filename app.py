import streamlit as st
import modules.screening as screening
# Tambahkan import lainnya jika file sudah ada di folder modules

# 1. KONFIGURASI
st.set_page_config(page_title="Expert Stock Pro", page_icon="📈", layout="wide")

# --- KEAMANAN & LINK ---
try:
    PASSWORD_RAHASIA = st.secrets["PASSWORD_RAHASIA"]
except:
    PASSWORD_RAHASIA = "12345"

LINK_LYNK_ID = "https://lynk.id/hahastoresby"

if 'status_login' not in st.session_state:
    st.session_state['status_login'] = False

# 2. LOGIKA LOGIN
if not st.session_state['status_login']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>📈 Expert Stock Pro</h1>", unsafe_allow_html=True)
        st.markdown("---")
        input_pass = st.text_input("Password Premium", type="password")
        if st.button("Masuk Aplikasi", use_container_width=True):
            if input_pass == PASSWORD_RAHASIA:
                st.session_state['status_login'] = True
                st.rerun()
            else: st.error("Password Salah.")
        st.link_button("🛒 Beli Akses Premium", LINK_LYNK_ID, use_container_width=True)
else:
    # 3. SIDEBAR NAVIGASI
    with st.sidebar:
        st.header("Expert Stock Pro")
        pilihan = st.radio("Pilih Menu:", (
            "🏠 Beranda", 
            "🔍 1. Screening Harian", 
            "📈 2. Analisa Teknikal", 
            "📊 3. Analisa Fundamental",
            "💰 4. Analisa Dividen",
            "⚖️ 5. Perbandingan 2 Saham"
        ))
        if st.button("Keluar"):
            st.session_state['status_login'] = False
            st.rerun()

    # 4. ROUTING
    if pilihan == "🏠 Beranda":
        st.title("Selamat Datang di Expert Stock Pro")
        st.write("Silakan pilih fitur di sidebar untuk memulai analisa.")
    elif pilihan == "🔍 1. Screening Harian":
        screening.run_screening()
    else:
        st.info(f"Fitur {pilihan} sedang disiapkan.")
