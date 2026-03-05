import streamlit as st
import importlib.util
import sys
import pandas as pd
from datetime import datetime, timedelta
import pytz
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIG HALAMAN & SEO ---
st.set_page_config(
    page_title="Expert Stock Pro: Level Up Analisa Saham BEI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Menambahkan Meta Tags SEO ke dalam halaman HTML Streamlit
st.markdown("""
    <meta name="description" content="Berhenti menebak arah pasar! Aplikasi analisa saham BEI dengan 6 modul premium: teknikal, fundamental & screening otomatis. Klaim trial 14 hari Anda sekarang.">
    <meta name="keywords" content="analisa saham, screening saham, saham BEI, aplikasi saham, trading saham, expert stock pro, teknikal saham, fundamental saham, drs. Musa Tanaja, M.Si.">
    <meta name="author" content="drs. Musa Tanaja, M.Si.">
    
    <meta property="og:title" content="Expert Stock Pro: Level Up Analisa Saham BEI">
    <meta property="og:description" content="Berhenti menebak arah pasar! Aplikasi analisa saham BEI dengan 6 modul premium: teknikal, fundamental & screening otomatis. Klaim trial 14 hari Anda sekarang.">
    <meta property="og:type" content="website">
""", unsafe_allow_html=True)

# --- 2. IMPORT MODUL (LAZY LOADING) ---
def load_and_run_module(module_name, run_function_name):
    """Mencoba load modul dan langsung menjalankannya, lebih cepat dan hemat memori"""
    try:
        mod = importlib.import_module(f"modules.{module_name}")
        func = getattr(mod, run_function_name)
        func()
    except ImportError:
        st.error(f"⚠️ Gagal memuat file {module_name}.py. Pastikan file ada di folder 'modules'.")
    except AttributeError:
        st.error(f"⚠️ Fungsi '{run_function_name}' tidak ditemukan di dalam {module_name}.py.")
    except SyntaxError as e:
        st.error(f"⚠️ Error Pengetikan di {module_name}.py: {e}")
    except Exception as e:
        st.error(f"⚠️ Terjadi kesalahan saat menjalankan modul {module_name}: {e}")

def check_module_exists(module_name):
    try:
        importlib.util.find_spec(f"modules.{module_name}")
        return True
    except ModuleNotFoundError:
        return False

# --- 3. CSS CUSTOM (GABUNGAN DASHBOARD & LANDING PAGE) ---
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

    .landing-header {
        text-align: center; 
        padding: 30px; 
        background-color: #1E1E1E; 
        border-radius: 15px; 
        border: 1px solid #2ECC71;
        margin-bottom: 30px;
    }
    
    .promo-box {
        background-color: #2c3e50;
        padding: 12px;
        border-radius: 8px;
        border-left: 5px solid #3498db;
        margin-bottom: 15px;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# --- 4. SESSION STATE ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_name' not in st.session_state: st.session_state.user_name = ""
if 'user_wa' not in st.session_state: st.session_state.user_wa = ""
if 'current_menu' not in st.session_state: st.session_state.current_menu = "Beranda"
if 'is_trial' not in st.session_state: st.session_state.is_trial = False
if 'trial_expiry_date' not in st.session_state: st.session_state.trial_expiry_date = ""

# --- FUNGSI PEMBERSIH NOMOR WA ANTI-ERROR ---
def bersihkan_nomor_wa(wa_str):
    """Membuang 0, +62, spasi, strip, dan format float .0 agar akurat dicocokkan"""
    w = str(wa_str).strip().replace(" ", "").replace("-", "")
    if w.endswith(".0"): w = w[:-2] 
    if w.startswith("+62"): w = w[3:]
    if w.startswith("62"): w = w[2:]
    if w.startswith("0"): w = w[1:]
    return w

# --- FUNGSI PENCATATAN TRIAL KE GOOGLE SHEETS ---
def cek_dan_catat_trial(nama_user, wa_user):
    tz_wib = pytz.timezone('Asia/Jakarta')
    hari_ini = datetime.now(tz_wib).date()
    
    wa_user_bersih = bersihkan_nomor_wa(wa_user)

    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        s_creds = dict(st.secrets["gcp_service_account"])
        
        pk = str(s_creds.get("private_key", ""))
        pk = pk.replace("\\n", "\n").replace("\\r", "").strip('"').strip("'").strip()
        if "-----BEGIN PRIVATE KEY-----" not in pk: pk = "-----BEGIN PRIVATE KEY-----\n" + pk
        if "-----END PRIVATE KEY-----" not in pk: pk = pk + "\n-----END PRIVATE KEY-----\n"
        s_creds["private_key"] = pk
        
        creds = Credentials.from_service_account_info(s_creds, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open("Data_Trial_ExpertStockPro").sheet1
        records = sheet.get_all_records()
        
        if not records:
            sheet.append_row(["Nomor_WA", "Nama", "Tanggal_Mulai", "Tanggal_Expired"])
            df = pd.DataFrame(columns=["Nomor_WA", "Nama", "Tanggal_Mulai", "Tanggal_Expired"])
        else:
            df = pd.DataFrame(records)

    except Exception as e:
        st.error(f"⚠️ Error Asli: {e}")
        return False, "Koneksi Google Sheets Gagal."

    if 'Nomor_WA' in df.columns:
        df['Nomor_WA_Clean'] = df['Nomor_WA'].apply(bersihkan_nomor_wa)
        user_exist = df[df['Nomor_WA_Clean'] == wa_user_bersih]
    else:
        user_exist = pd.DataFrame()

    if not user_exist.empty:
        tgl_expired_str = str(user_exist.iloc[0]['Tanggal_Expired'])
        tgl_expired = datetime.strptime(tgl_expired_str, "%Y-%m-%d").date()
        
        if hari_ini <= tgl_expired:
            return True, tgl_expired_str 
        else:
            return False, "❌ Masa trial 14 hari Anda sudah habis. Silakan beli Akses Premium seumur hidup."
    else:
        tgl_expired = hari_ini + timedelta(days=14)
        tgl_expired_str = tgl_expired.strftime("%Y-%m-%d")
        
        try:
            wa_simpan = f"'{wa_user.strip()}"
            sheet.append_row([wa_simpan, nama_user.strip(), hari_ini.strftime("%Y-%m-%d"), tgl_expired_str])
            return True, tgl_expired_str
        except Exception as e:
            return False, "❌ Gagal menyimpan data trial. Coba beberapa saat lagi."

# --- 5. HALAMAN LOGIN (LANDING PAGE KONVERSI & TIMER PER-USER) ---
def login_page():
    kode_trial_tampil = st.secrets.get("TRIAL_CODE", "CUAN14HARI")

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
        * ✅ **Laporan PDF:** Hasil analisa bisa didownload dalam bentuk PDF.
        
        **Jangan biarkan peluang cuan lewat begitu saja hanya karena Anda kurang tools profesional.**
        """)

    with col_right:
        st.info("### 🔑 Masuk ke Sistem")
        
        st.markdown(f"""
        <div class="promo-box">
            💡 <b>Ingin mencoba aplikasi ini secara gratis?</b><br>
            Silakan gunakan Password Akses: <code style="color: #2ECC71; font-weight: bold; font-size: 1.2em;">{kode_trial_tampil}</code><br>
            <span style="font-size: 0.85em; color: #bdc3c7;">Berlaku untuk Free Trial selama 14 hari penuh.</span>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            nama = st.text_input("👤 Nama Panggilan", placeholder="Contoh: Sobat Cuan")
            wa = st.text_input("📱 Nomor WhatsApp", placeholder="Contoh: 08123456789")
            pw = st.text_input("🔑 Password Akses", type="password", placeholder="Masukkan kode akses / trial...")
            
            submit_button = st.form_submit_button("BUKA AKSES DASHBOARD", use_container_width=True)
            
            if submit_button:
                kode_permanen = st.secrets.get("PASSWORD_RAHASIA", "KODE_TIDAK_VALID_KARENA_BELUM_DISET_X99")
                kode_trial = st.secrets.get("TRIAL_CODE", "CUAN14HARI")
                
                # Cek dulu apakah wa mengandung karakter selain angka (mengabaikan +, -, dan spasi yang wajar)
                wa_cek_angka = wa.replace("+", "").replace("-", "").replace(" ", "").strip()
                
                if nama.strip() == "" or wa.strip() == "": 
                    st.warning("Mohon isi Nama dan Nomor WhatsApp terlebih dahulu.")
                elif not wa_cek_angka.isdigit():
                    st.warning("⚠️ Nomor WhatsApp hanya boleh berisi angka.")
                elif pw.strip() == kode_permanen:
                    st.session_state.logged_in = True
                    st.session_state.user_name = nama
                    st.session_state.user_wa = wa
                    st.session_state.is_trial = False
                    st.rerun()
                elif pw.strip() == kode_trial:
                    is_valid, pesan_atau_tanggal = cek_dan_catat_trial(nama, wa)
                    
                    if is_valid:
                        st.session_state.logged_in = True
                        st.session_state.user_name = nama
                        st.session_state.user_wa = wa
                        st.session_state.is_trial = True
                        st.session_state.trial_expiry_date = pesan_atau_tanggal
                        st.rerun()
                    else:
                        st.error(pesan_atau_tanggal)
                else: 
                    st.error("❌ Kode akses salah atau sudah kadaluwarsa.")
                    st.info(f"💡 Belum punya kode akses permanen? Anda bisa mencoba gratis selama 14 hari dengan menggunakan password: **{kode_trial}**")
        
        st.markdown("---")
        st.markdown("<p style='text-align: center; color: #A0A0A0;'>Belum punya akses premium seumur hidup?</p>", unsafe_allow_html=True)
        st.link_button("🛒 DAPATKAN KODE AKSES SEKARANG", "https://lynk.id/hahastoresby", use_container_width=True)
        st.markdown("<p style='text-align: center; font-size: 0.8em; color: #888; margin-top: 10px;'>💳 Aktivasi Instan via Lynk.id</p>", unsafe_allow_html=True)

# --- 6. DASHBOARD ---
def show_dashboard():
    st.markdown(f"### 👋 Halo Sobat <span style='color:#ff0000'>{st.session_state.user_name}</span>!", unsafe_allow_html=True)

    if st.session_state.is_trial:
        st.warning(f"⏳ **Mode Trial Aktif!** Akses gratis Anda akan berakhir pada **{st.session_state.trial_expiry_date}**. Jangan sampai kehilangan data analisa, [Beli Akses Permanen Di Sini](https://lynk.id/hahastoresby).")

    with st.expander("📖 3 Langkah Mudah Memakai Aplikasi Expert Stock Pro (Baca Ini Dulu)"):
        st.markdown("""
#### **1. Cara Mulai Analisa**
* Pilih menu Analisa yang mau dilakukan, lalu klik menu tersebut di Bawah ini.
#### **2. Masukkan Kode Saham (Contoh: BBRI atau BBRI.JK).**
* Setelah masukkan Kode Saham, lalu klik tombol "Mulai Analisa".
#### **3. Kembali ke "Menu Utama"**
* Bila sudah selesai analisa, klik tombol menu "Menu Utama" untuk kembali ke Beranda.
        """)
    
    st.markdown("<h1 style='text-align: center; color: #ff0000; letter-spacing: 2px;'>📈 EXPERT STOCK PRO</h1>", unsafe_allow_html=True)
    st.write("Silakan pilih menu analisa:")
    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 Screening Saham Harian Pro", use_container_width=True):
            st.session_state.current_menu = "screening"; st.rerun()
    with c2:
        if check_module_exists("analisa_cepat"):
            if st.button("⚡ Analisa Cepat Pro", use_container_width=True):
                st.session_state.current_menu = "analisa_cepat"; st.rerun()
        else:
            st.button("⚡ Analisa Cepat (Rusak)", use_container_width=True, disabled=True)

    c3, c4 = st.columns(2)
    with c3:
        if st.button("📈 Analisa Teknikal Pro", use_container_width=True):
            st.session_state.current_menu = "teknikal"; st.rerun()
    with c4:
        if st.button("📊 Analisa Fundamental Pro", use_container_width=True):
            st.session_state.current_menu = "fundamental"; st.rerun()

    c5, c6 = st.columns(2)
    with c5:
        if st.button("💰 Analisa Dividen Pro", use_container_width=True):
            st.session_state.current_menu = "dividen"; st.rerun()
    with c6:
        if st.button("⚖️ Perbandingan Saham Pro", use_container_width=True):
            st.session_state.current_menu = "perbandingan"; st.rerun()

    st.markdown("---")
    if st.button("Keluar / Logout"):
        st.session_state.logged_in = False
        st.session_state.user_name = ""
        st.session_state.user_wa = ""
        st.session_state.is_trial = False
        st.rerun()

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

        m = st.session_state.current_menu
        if m == "screening": load_and_run_module("screening", "run_screening")
        elif m == "analisa_cepat": load_and_run_module("analisa_cepat", "run_analisa_cepat")
        elif m == "teknikal": load_and_run_module("teknikal", "run_teknikal")
        elif m == "fundamental": load_and_run_module("fundamental", "run_fundamental")
        elif m == "dividen": load_and_run_module("dividen", "run_dividen")
        elif m == "perbandingan": load_and_run_module("perbandingan", "run_perbandingan")

if __name__ == "__main__":
    if st.session_state.logged_in:
        main_app()
    else:
        login_page()
