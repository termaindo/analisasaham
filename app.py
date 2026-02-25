import streamlit as st
import importlib.util
import sys
import pandas as pd
import os
from datetime import datetime, timedelta
import pytz

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
    
    /* Kotak Info Promo Trial */
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

# --- FUNGSI PENCATATAN TRIAL (SISTEM DATABASE CSV LOKAL) ---
def cek_dan_catat_trial(nama_user, wa_user):
    FILE_TRIAL = "data_trial.csv"
    tz_wib = pytz.timezone('Asia/Jakarta')
    hari_ini = datetime.now(tz_wib).date()
    
    # Bersihkan input WA agar seragam
    wa_user_bersih = str(wa_user).strip().replace(" ", "").replace("-", "")

    # Buat file CSV jika belum ada (baru pertama kali ada yang trial)
    if not os.path.exists(FILE_TRIAL):
        df = pd.DataFrame(columns=["Nomor_WA", "Nama", "Tanggal_Mulai", "Tanggal_Expired"])
        df.to_csv(FILE_TRIAL, index=False)
    
    # Baca data, pastikan Nomor_WA dibaca sebagai string
    df = pd.read_csv(FILE_TRIAL, dtype={'Nomor_WA': str})
    
    # Cek apakah user (berdasarkan Nomor WA) ini sudah pernah login sebelumnya
    user_exist = df[df['Nomor_WA'] == wa_user_bersih]
    
    if not user_exist.empty:
        # USER LAMA: Cek apakah masih dalam masa 14 hari
        tgl_expired_str = str(user_exist.iloc[0]['Tanggal_Expired'])
        tgl_expired = datetime.strptime(tgl_expired_str, "%Y-%m-%d").date()
        
        if hari_ini <= tgl_expired:
            return True, tgl_expired_str # Masih valid
        else:
            return False, "❌ Masa trial 14 hari Anda sudah habis. Silakan beli Akses Premium seumur hidup."
    else:
        # USER BARU: Berikan 14 hari dari hari ini, lalu simpan datanya
        tgl_expired = hari_ini + timedelta(days=14)
        tgl_expired_str = tgl_expired.strftime("%Y-%m-%d")
        
        df_baru = pd.DataFrame({
            "Nomor_WA": [wa_user_bersih],
            "Nama": [nama_user.strip()], 
            "Tanggal_Mulai": [hari_ini.strftime("%Y-%m-%d")], 
            "Tanggal_Expired": [tgl_expired_str]
        })
        df = pd.concat([df, df_baru], ignore_index=True)
        df.to_csv(FILE_TRIAL, index=False)
        
        return True, tgl_expired_str

# --- 5. HALAMAN LOGIN (LANDING PAGE KONVERSI & TIMER PER-USER) ---
def login_page():
    # Mengambil kode trial untuk ditampilkan di banner promosi
    try: 
        kode_trial_tampil = st.secrets["TRIAL_CODE"]
    except: 
        kode_trial_tampil = "CUAN14HARI"

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
        * ✅ **Laporan PDF:** Hasil analisa bisa didownload dalam bentuk PDF.
        
        **Jangan biarkan peluang cuan lewat begitu saja hanya karena Anda kurang tools profesional.**
        """)

    with col_right:
        st.info("### 🔑 Masuk ke Sistem")
        
        # MENAMPILKAN KODE TRIAL UNTUK PENGUNJUNG WALK-IN
        st.markdown(f"""
        <div class="promo-box">
            💡 <b>Ingin mencoba aplikasi ini secara gratis?</b><br>
            Silakan gunakan Password Akses: <code style="color: #2ECC71; font-weight: bold; font-size: 1.2em;">{kode_trial_tampil}</code><br>
            <span style="font-size: 0.85em; color: #bdc3c7;">Berlaku untuk Free Trial selama 14 hari penuh.</span>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            nama = st.text_input("👤 Nama Panggilan", placeholder="Contoh: Sobat Musa")
            wa = st.text_input("📱 Nomor WhatsApp", placeholder="Contoh: 08123456789")
            pw = st.text_input("🔑 Password Akses", type="password", placeholder="Masukkan kode akses / trial...")
            
            submit_button = st.form_submit_button("BUKA AKSES DASHBOARD", use_container_width=True)
            
            if submit_button:
                # Mengambil password dari st.secrets untuk keamanan validasi
                try: 
                    kode_permanen = st.secrets["PASSWORD_RAHASIA"]
                    kode_trial = st.secrets["TRIAL_CODE"]
                except: 
                    kode_permanen = "12345" # Fallback jika secrets belum diset di Streamlit Cloud
                    kode_trial = "CUAN14HARI"
                
                if nama.strip() == "" or wa.strip() == "": 
                    st.warning("Mohon isi Nama dan Nomor WhatsApp terlebih dahulu.")
                elif pw.strip() == kode_permanen:
                    # AKSES PREMIUM PERMANEN
                    st.session_state.logged_in = True
                    st.session_state.user_name = nama
                    st.session_state.user_wa = wa
                    st.session_state.is_trial = False
                    st.rerun()
                elif pw.strip() == kode_trial:
                    # AKSES TRIAL (Pencatatan by Nomor WA agar unik)
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
                    st.error("Kode akses salah atau sudah kadaluwarsa.")
        
        # Link Pembelian di bawah form
        st.markdown("---")
        st.markdown("<p style='text-align: center; color: #A0A0A0;'>Belum punya akses premium seumur hidup?</p>", unsafe_allow_html=True)
        st.link_button("🛒 DAPATKAN KODE AKSES SEKARANG", "https://lynk.id/hahastoresby", use_container_width=True)
        st.markdown("<p style='text-align: center; font-size: 0.8em; color: #888; margin-top: 10px;'>💳 Aktivasi Instan via Lynk.id</p>", unsafe_allow_html=True)

# --- 6. DASHBOARD ---
def show_dashboard():
    # Sapaan menggunakan Nama saja, tanpa memunculkan WA
    st.markdown(f"### 👋 Halo Sobat <span style='color:#ff0000'>{st.session_state.user_name}</span>!", unsafe_allow_html=True)

    # --- BANNER PENGINGAT TRIAL (Hanya muncul jika is_trial == True) ---
    if st.session_state.is_trial:
        st.warning(f"⏳ **Mode Trial Aktif!** Akses gratis Anda akan berakhir pada **{st.session_state.trial_expiry_date}**. Jangan sampai kehilangan data analisa, [Beli Akses Permanen Di Sini](https://lynk.id/hahastoresby).")

    # Langsung ke menu dropdown expander (bagi yang premium, notif trial di atas otomatis tidak muncul)
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
        if st.button("🔍 Screening Saham Harian Pro", use_container_width=True):
            st.session_state.current_menu = "screening"; st.rerun()
    with c2:
        label = "⚡ Analisa Cepat Pro" if mod_cepat else "⚡ Analisa Cepat (Rusak)"
        if st.button(label, use_container_width=True):
            if mod_cepat:
                st.session_state.current_menu = "analisa_cepat"; st.rerun()
            else:
                st.error("Modul analisa_cepat.py bermasalah.")

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

