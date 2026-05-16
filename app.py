
Aplikasi Saham
/

import streamlit as st import importlib.util import sys import pandas as pd from datetime import datetime, timedelta import pytz import gspread from google.oauth2.service_account import Credentials import io # --- 1. CONFIG HALAMAN & SEO --- st.set_page_config( page_title="Expert St

pasted


""" screening.py ============ Modul Screening Day Trade & Swing Trade. Universe saham: dibaca dari liquid_stocks.csv (prioritas) atau pre_liquid_stocks.csv (fallback) via get_liquid_stocks() / load_universe(). Tidak ada lagi dependency ke Google Drive API atau universe.py. """ import str

pasted

waktu saya jalankan aplikasi saham ini, kenapa keluar error "Gagal memuat file screening.py.py. Pastikan file ada di folder 'modules'." dan error ini ternyata terjadi di semua modul screening dan analisa.
berikut kode app.py untuk kamu cek. sekalian cek apakah modul screening.py juga sudah menjalankan alur data yang terbaru?

11.57
Dua bug langsung terlihat dari kode app.py.

Bug 1 — Double .py di nama modul

Di main_app(), kamu memanggil:

python
load_and_run_module("screening.py", "run_screening")
Tapi di dalam load_and_run_module(), nama itu dipakai sebagai:

python
importlib.import_module(f"modules.{module_name}")
Hasilnya: modules.screening.py — Python mencari file screening.py.py. Itu sebab error-nya berbunyi persis "screening.py.py".

Fix: Hilangkan ekstensi .py dari semua pemanggilan di main_app():

python
if m == "screening":      load_and_run_module("screening",     "run_screening")
elif m == "analisa_cepat": load_and_run_module("analisa_cepat", "run_analisa_cepat")
elif m == "teknikal":      load_and_run_module("teknikal",      "run_teknikal")
elif m == "fundamental":   load_and_run_module("fundamental",   "run_fundamental")
elif m == "dividen":       load_and_run_module("dividen",       "run_dividen")
elif m == "perbandingan":  load_and_run_module("perbandingan",  "run_perbandingan")
Bug 2 — check_module_exists() juga pakai nama dengan .py

python
# Baris ini juga akan gagal karena nama modul-nya salah
if check_module_exists("analisa_cepat"):
Di sini tidak ada .py — tapi cek check_module_exists di show_dashboard() sudah benar. Yang bermasalah hanya blok main_app().

Soal alur data screening.py — ada 3 masalah:

Masalah 1 — st.set_page_config() di dalam run_screening()

python
def run_screening() -> None:
    st.set_page_config(page_title="🔍 Screening Saham Harian", layout="wide")
set_page_config() hanya boleh dipanggil sekali, di awal, sebelum elemen Streamlit lain. app.py sudah memanggilnya lebih dulu. Saat run_screening() dipanggil, ini akan crash. Hapus baris itu dari screening.py.

Masalah 2 — Import hitung_div_yield_normal yang tidak ada di spesifikasi

python
from data_loader import (
    ...
    hitung_div_yield_normal,
    ...
)
Fungsi ini tidak ada di ALUR_DATA.md maupun MODUL_SPEC.md. Jika data_loader.py tidak mengekspornya, seluruh modul screening.py gagal diimpor dengan ImportError — bahkan sebelum ada satu baris yang dieksekusi.

Masalah 3 — Alur data sudah benar, tapi ada inkonsistensi nama kolom

load_universe() melakukan rename kolom MktCap → Mkt Cap (dengan spasi):

python
elif c in ("mktcap", "mkt cap", "market cap", "market_cap"):
    rename_map[col] = "Mkt Cap"
Tapi STANDAR_KODING.md menetapkan nama kolom yang benar adalah MktCap (tanpa spasi). Kalau ada filter sidebar berdasarkan market cap, lookup-nya akan gagal karena nama kolomnya tidak cocok dengan liquid_stocks.csv.

Ringkasan fix yang harus dilakukan:

app.py → hapus .py dari semua argumen load_and_run_module() di main_app()
screening.py → hapus st.set_page_config() dari run_screening()
screening.py → hapus hitung_div_yield_normal dari import, cek apakah fungsi itu memang ada di data_loader.py
screening.py → ganti "Mkt Cap" → "MktCap" di _normalize_universe_columns()
langsung lakukan koreksi secara lengkap di modul app.py dan screening.py agar bisa langsung saya copas keseluruhan ke masing-masing modul

12.00

Read project spec files
Read project spec files
Sekarang tulis kedua file lengkap:


Created 2 files
Created 2 files

app.py — fix double .py bug di load_and_run_module dan semua pemanggilan modul
app.py

screening.py — fix semua bug: hapus set_page_config, hapus import hitung_div_yield_normal, fix nama kolom MktCap, perbaiki import path data_loader dari utils
screening.py
Done





Claude is AI and can make mistakes. Please double-check responses.
App · PY
Copy

import streamlit as st
import importlib.util
import sys
import pandas as pd
from datetime import datetime, timedelta
import pytz
import gspread
from google.oauth2.service_account import Credentials
import io
 
# --- 1. CONFIG HALAMAN & SEO ---
st.set_page_config(
    page_title="Expert Stock Pro: Level Up Analisa Saham BEI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)
 
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
    """Lazy-load dan jalankan fungsi entry-point dari modul di folder modules/."""
    # module_name sudah tanpa ekstensi .py — cukup nama modul saja
    try:
        mod  = importlib.import_module(f"modules.{module_name}")
        func = getattr(mod, run_function_name)
        func()
    except ImportError as e:
        st.error(
            f"⚠️ Gagal memuat modul `{module_name}`. "
            f"Pastikan file `modules/{module_name}.py` ada di repository.\n\nDetail: {e}"
        )
    except AttributeError:
        st.error(
            f"⚠️ Fungsi `{run_function_name}` tidak ditemukan di dalam "
            f"`modules/{module_name}.py`."
        )
    except SyntaxError as e:
        st.error(f"⚠️ Syntax error di `modules/{module_name}.py`: {e}")
    except Exception as e:
        st.error(f"⚠️ Terjadi kesalahan saat menjalankan modul `{module_name}`: {e}")
 
 
def check_module_exists(module_name):
    """Cek apakah modul tersedia tanpa menjalankannya."""
    spec = importlib.util.find_spec(f"modules.{module_name}")
    return spec is not None
 
 
# --- 3. CSS CUSTOM ---
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
 
    .admin-panel {
        background-color: #1a1a2e;
        border: 2px solid #e74c3c;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 25px;
    }
 
    .admin-badge {
        background-color: #e74c3c;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: bold;
        margin-left: 10px;
    }
</style>
""", unsafe_allow_html=True)
 
# --- 4. SESSION STATE ---
if 'logged_in'          not in st.session_state: st.session_state.logged_in          = False
if 'user_name'          not in st.session_state: st.session_state.user_name          = ""
if 'user_wa'            not in st.session_state: st.session_state.user_wa            = ""
if 'current_menu'       not in st.session_state: st.session_state.current_menu       = "Beranda"
if 'is_trial'           not in st.session_state: st.session_state.is_trial           = False
if 'trial_expiry_date'  not in st.session_state: st.session_state.trial_expiry_date  = ""
if 'is_admin'           not in st.session_state: st.session_state.is_admin           = False
 
 
# --- FUNGSI PEMBERSIH NOMOR WA ---
def bersihkan_nomor_wa(wa_str):
    """Normalisasi nomor WA ke format tanpa awalan 0/62/+62."""
    w = str(wa_str).strip().replace(" ", "").replace("-", "")
    if w.endswith(".0"):  w = w[:-2]
    if w.startswith("+62"): w = w[3:]
    if w.startswith("62"):  w = w[2:]
    if w.startswith("0"):   w = w[1:]
    return w
 
 
# --- FUNGSI CEK LOGIN ADMIN ---
def is_admin_login(nama, wa, pw):
    """Validasi kredensial admin (nama + WA + password)."""
    nama_admin_valid = nama.strip().lower() == "musa"
    wa_bersih        = bersihkan_nomor_wa(wa)
    wa_admin_bersih  = bersihkan_nomor_wa("0818337457")
    wa_admin_valid   = (wa_bersih == wa_admin_bersih)
    pw_admin         = st.secrets.get("ADMIN_PASSWORD", "ADMIN_KODE_TIDAK_VALID_X99")
    pw_valid         = (pw.strip() == pw_admin)
    return nama_admin_valid and wa_admin_valid and pw_valid
 
 
# --- GOOGLE DRIVE: KONSTANTA FOLDER ---
GDRIVE_FOLDER_NAME = "ExpertStockPro_Data"
 
 
def _get_drive_service():
    """Buat Drive API service yang sudah terotentikasi."""
    from googleapiclient.discovery import build
    from google.oauth2.service_account import Credentials as SACredentials
 
    scopes  = ['https://www.googleapis.com/auth/drive']
    s_creds = dict(st.secrets["gcp_service_account"])
    pk = str(s_creds.get("private_key", ""))
    pk = pk.replace("\\n", "\n").replace("\\r", "").strip('"').strip("'").strip()
    if "-----BEGIN PRIVATE KEY-----" not in pk:
        pk = "-----BEGIN PRIVATE KEY-----\n" + pk
    if "-----END PRIVATE KEY-----" not in pk:
        pk = pk + "\n-----END PRIVATE KEY-----\n"
    s_creds["private_key"] = pk
    creds = SACredentials.from_service_account_info(s_creds, scopes=scopes)
    return build('drive', 'v3', credentials=creds)
 
 
def _get_folder_id(service, folder_name: str):
    """Cari folder ID berdasarkan nama folder di Google Drive."""
    results = service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        spaces='drive',
        fields='files(id, name)'
    ).execute()
    items = results.get('files', [])
    return items[0]['id'] if items else None
 
 
def ambil_csv_dari_gdrive(nama_file: str):
    """Ambil file CSV dari Google Drive berdasarkan nama file."""
    try:
        from googleapiclient.http import MediaIoBaseDownload
        service = _get_drive_service()
 
        # DEBUG: tampilkan semua file yang terlihat oleh service account
        all_files = service.files().list(
            q="trashed=false",
            spaces='drive',
            fields='files(id, name, mimeType)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        semua = all_files.get('files', [])
        if semua:
            st.info(f"📂 File yang terlihat oleh service account ({len(semua)} file):")
            for f in semua:
                st.code(f"nama: {f['name']} | mimeType: {f['mimeType']} | id: {f['id']}")
        else:
            st.warning(
                "⚠️ Service account tidak melihat file APAPUN di Google Drive. "
                "Artinya tidak ada file/folder yang di-share ke service account ini."
            )
 
        results = service.files().list(
            q=f"name='{nama_file}' and trashed=false",
            spaces='drive',
            fields='files(id, name, mimeType)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        items = results.get('files', [])
 
        if not items:
            st.error(
                f"⚠️ File '{nama_file}' tidak ditemukan di Google Drive. "
                f"Pastikan file sudah di-share ke: "
                f"`{st.secrets['gcp_service_account']['client_email']}`"
            )
            return None
 
        file_id = items[0]['id']
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        return pd.read_csv(fh)
 
    except Exception as e:
        st.error(f"⚠️ Gagal mengambil file dari Google Drive: {e}")
        return None
 
 
def simpan_csv_ke_gdrive(df: pd.DataFrame, nama_file: str) -> bool:
    """Simpan DataFrame sebagai CSV ke Google Drive (overwrite jika sudah ada)."""
    try:
        from googleapiclient.http import MediaIoBaseUpload
        service = _get_drive_service()
 
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_bytes = io.BytesIO(csv_buffer.getvalue().encode('utf-8'))
        media = MediaIoBaseUpload(csv_bytes, mimetype='text/csv', resumable=True)
 
        results = service.files().list(
            q=f"name='{nama_file}' and trashed=false",
            spaces='drive',
            fields='files(id, name, mimeType)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        items = results.get('files', [])
 
        if items:
            service.files().update(
                fileId=items[0]['id'],
                media_body=media,
                supportsAllDrives=True
            ).execute()
        else:
            file_metadata = {'name': nama_file, 'mimeType': 'text/csv'}
            service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id',
                supportsAllDrives=True
            ).execute()
 
        return True
 
    except Exception as e:
        st.error(f"⚠️ Gagal menyimpan file ke Google Drive: {e}")
        return False
 
 
# --- FUNGSI PENCATATAN TRIAL KE GOOGLE SHEETS ---
def cek_dan_catat_trial(nama_user, wa_user):
    """Cek masa trial user di Google Sheets; daftarkan jika belum ada."""
    tz_wib        = pytz.timezone('Asia/Jakarta')
    hari_ini      = datetime.now(tz_wib).date()
    wa_user_bersih = bersihkan_nomor_wa(wa_user)
 
    try:
        scopes  = ['https://www.googleapis.com/auth/spreadsheets',
                   'https://www.googleapis.com/auth/drive']
        s_creds = dict(st.secrets["gcp_service_account"])
        pk = str(s_creds.get("private_key", ""))
        pk = pk.replace("\\n", "\n").replace("\\r", "").strip('"').strip("'").strip()
        if "-----BEGIN PRIVATE KEY-----" not in pk: pk = "-----BEGIN PRIVATE KEY-----\n" + pk
        if "-----END PRIVATE KEY-----" not in pk:   pk = pk + "\n-----END PRIVATE KEY-----\n"
        s_creds["private_key"] = pk
        creds  = Credentials.from_service_account_info(s_creds, scopes=scopes)
        client = gspread.authorize(creds)
        sheet  = client.open("Data_Trial_ExpertStockPro").sheet1
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
        tgl_expired     = datetime.strptime(tgl_expired_str, "%Y-%m-%d").date()
        if hari_ini <= tgl_expired:
            return True, tgl_expired_str
        else:
            return False, "❌ Masa trial 14 hari Anda sudah habis. Silakan beli Akses Premium seumur hidup."
    else:
        tgl_expired     = hari_ini + timedelta(days=14)
        tgl_expired_str = tgl_expired.strftime("%Y-%m-%d")
        try:
            wa_simpan = f"'{wa_user.strip()}"
            sheet.append_row([wa_simpan, nama_user.strip(),
                               hari_ini.strftime("%Y-%m-%d"), tgl_expired_str])
            return True, tgl_expired_str
        except Exception:
            return False, "❌ Gagal menyimpan data trial. Coba beberapa saat lagi."
 
 
# --- 5. HALAMAN LOGIN ---
def login_page():
    """Tampilkan halaman login / landing page."""
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
            wa   = st.text_input("📱 Nomor WhatsApp",  placeholder="Contoh: 08123456789")
            pw   = st.text_input("🔑 Password Akses",  type="password",
                                  placeholder="Masukkan kode akses / trial...")
 
            submit_button = st.form_submit_button("BUKA AKSES DASHBOARD", use_container_width=True)
 
            if submit_button:
                kode_permanen  = st.secrets.get("PASSWORD_RAHASIA", "KODE_TIDAK_VALID_KARENA_BELUM_DISET_X99")
                kode_trial     = st.secrets.get("TRIAL_CODE", "CUAN14HARI")
                wa_cek_angka   = wa.replace("+", "").replace("-", "").replace(" ", "").strip()
 
                if nama.strip() == "" or wa.strip() == "":
                    st.warning("Mohon isi Nama dan Nomor WhatsApp terlebih dahulu.")
                elif not wa_cek_angka.isdigit():
                    st.warning("⚠️ Nomor WhatsApp hanya boleh berisi angka.")
                elif len(wa_cek_angka) < 10:
                    st.warning("⚠️ Nomor WhatsApp tidak valid. Harap isi No WA lengkap.")
                elif is_admin_login(nama, wa, pw):
                    st.session_state.logged_in         = True
                    st.session_state.user_name         = nama.strip()
                    st.session_state.user_wa           = wa.strip()
                    st.session_state.is_trial          = False
                    st.session_state.is_admin          = True
                    st.rerun()
                elif pw.strip() == kode_permanen:
                    st.session_state.logged_in         = True
                    st.session_state.user_name         = nama
                    st.session_state.user_wa           = wa
                    st.session_state.is_trial          = False
                    st.session_state.is_admin          = False
                    st.rerun()
                elif pw.strip() == kode_trial:
                    is_valid, pesan_atau_tanggal = cek_dan_catat_trial(nama, wa)
                    if is_valid:
                        st.session_state.logged_in         = True
                        st.session_state.user_name         = nama
                        st.session_state.user_wa           = wa
                        st.session_state.is_trial          = True
                        st.session_state.is_admin          = False
                        st.session_state.trial_expiry_date = pesan_atau_tanggal
                        st.rerun()
                    else:
                        st.error(pesan_atau_tanggal)
                else:
                    st.error("❌ Kode akses salah atau sudah kadaluwarsa.")
                    st.info(
                        f"💡 Belum punya kode akses permanen? "
                        f"Anda bisa mencoba gratis selama 14 hari dengan menggunakan password: "
                        f"**{kode_trial}**"
                    )
 
        st.markdown("---")
        st.markdown(
            "<p style='text-align: center; color: #A0A0A0;'>Belum punya akses premium seumur hidup?</p>",
            unsafe_allow_html=True
        )
        st.link_button(
            "🛒 DAPATKAN KODE AKSES SEKARANG",
            "https://lynk.id/hahastoresby",
            use_container_width=True
        )
        st.markdown(
            "<p style='text-align: center; font-size: 0.8em; color: #888; margin-top: 10px;'>"
            "💳 Aktivasi Instan via Lynk.id</p>",
            unsafe_allow_html=True
        )
 
 
# --- 6A. PANEL ADMIN: KELOLA DATA LIQUID STOCKS ---
def show_admin_data_panel():
    """Panel admin untuk enrichment pre_liquid → liquid_stocks."""
    st.markdown("""
    <div class="admin-panel">
        <h3 style="color: #e74c3c; margin-bottom: 5px;">
            🛠️ Panel Admin — Kelola Data Liquid Stocks
        </h3>
        <p style="color: #bdc3c7; font-size: 0.9em; margin-bottom: 0;">
            Tarik <code>pre_liquid_stocks.csv</code> dari repo lokal → Proses via
            <code>data_loader.py</code> → Simpan sebagai <code>liquid_stocks.csv</code>
        </p>
    </div>
    """, unsafe_allow_html=True)
 
    col_a, col_b, col_c = st.columns(3)
 
    with col_a:
        st.markdown("**📥 Step 1: Tarik Data Sumber**")
        if st.button("Ambil pre_liquid_stocks.csv\ndari repo lokal",
                     use_container_width=True, key="btn_ambil"):
            try:
                df_pre = pd.read_csv("data/pre_liquid_stocks.csv", sep=None, engine='python')
                st.session_state['df_pre_liquid'] = df_pre
                st.success(f"✅ Berhasil! {len(df_pre)} baris, {len(df_pre.columns)} kolom dimuat.")
                st.dataframe(df_pre.head(5), use_container_width=True)
            except FileNotFoundError:
                st.error(
                    "❌ File `data/pre_liquid_stocks.csv` tidak ditemukan. "
                    "Pastikan file ada di folder `data/` sejajar dengan `app.py`."
                )
            except Exception as e:
                st.error(f"❌ Gagal membaca file: {e}")
 
    with col_b:
        st.markdown("**⚙️ Step 2: Proses Data**")
        df_pre_ada = (
            'df_pre_liquid' in st.session_state
            and st.session_state['df_pre_liquid'] is not None
        )
 
        if st.button("Proses via data_loader.py",
                     use_container_width=True, key="btn_proses", disabled=not df_pre_ada):
            if df_pre_ada:
                with st.spinner("Memproses data… ini bisa memakan beberapa menit."):
                    try:
                        # data_loader.py ada di /utils — pastikan path-nya di sys.path
                        import importlib
                        loader = importlib.import_module("utils.data_loader")
 
                        if hasattr(loader, 'process_liquid_stocks'):
                            df_hasil = loader.process_liquid_stocks(
                                st.session_state['df_pre_liquid'].copy()
                            )
                        else:
                            st.error(
                                "⚠️ Fungsi `process_liquid_stocks` tidak ditemukan "
                                "di `utils/data_loader.py`."
                            )
                            df_hasil = None
 
                        if df_hasil is not None:
                            st.session_state['df_liquid_hasil'] = df_hasil
                            st.success(f"✅ Proses selesai! {len(df_hasil)} baris siap disimpan.")
                            st.dataframe(df_hasil.head(5), use_container_width=True)
 
                    except ImportError as e:
                        st.error(f"⚠️ Modul `utils/data_loader.py` tidak ditemukan: {e}")
                    except Exception as e:
                        st.error(f"⚠️ Error saat memproses: {e}")
            else:
                st.warning("Ambil data sumber terlebih dahulu di Step 1.")
 
    with col_c:
        st.markdown("**💾 Step 3: Simpan ke Google Drive**")
        df_hasil_ada = (
            'df_liquid_hasil' in st.session_state
            and st.session_state['df_liquid_hasil'] is not None
        )
 
        if st.button("Simpan sebagai liquid_stocks.csv\nke Google Drive",
                     use_container_width=True, key="btn_simpan", disabled=not df_hasil_ada):
            if df_hasil_ada:
                with st.spinner("Menyimpan ke Google Drive…"):
                    berhasil = simpan_csv_ke_gdrive(
                        st.session_state['df_liquid_hasil'], "liquid_stocks.csv"
                    )
                if berhasil:
                    st.success("✅ `liquid_stocks.csv` berhasil disimpan ke Google Drive!")
                    try:
                        from utils.data_loader import clear_liquid_stocks_cache
                        clear_liquid_stocks_cache()
                        st.info("🔄 Cache diperbarui — semua user akan memakai data terbaru.")
                    except Exception as e:
                        st.warning(f"⚠️ Cache tidak bisa dihapus otomatis: {e}")
                    del st.session_state['df_pre_liquid']
                    del st.session_state['df_liquid_hasil']
                else:
                    st.error("❌ Gagal menyimpan. Coba lagi.")
            else:
                st.warning("Proses data terlebih dahulu di Step 2.")
 
    st.markdown("---")
 
 
# --- 6B. DASHBOARD UTAMA ---
def show_dashboard():
    """Tampilkan dashboard utama setelah login."""
    if st.session_state.is_admin:
        st.markdown(
            f"### 👋 Halo <span style='color:#ff0000'>{st.session_state.user_name}</span> "
            f"<span class='admin-badge'>🔐 ADMIN</span>",
            unsafe_allow_html=True
        )
        show_admin_data_panel()
    else:
        st.markdown(
            f"### 👋 Halo Sobat <span style='color:#ff0000'>"
            f"{st.session_state.user_name}</span>!",
            unsafe_allow_html=True
        )
 
    if st.session_state.is_trial:
        st.warning(
            f"⏳ **Mode Trial Aktif!** Akses gratis Anda akan berakhir pada "
            f"**{st.session_state.trial_expiry_date}**. "
            f"Jangan sampai kehilangan data analisa, "
            f"[Beli Akses Permanen Di Sini](https://lynk.id/hahastoresby)."
        )
 
    with st.expander("📖 3 Langkah Mudah Memakai Aplikasi Expert Stock Pro (Baca Ini Dulu)"):
        st.markdown("""
#### **1. Cara Mulai Analisa**
* Pilih menu Analisa yang mau dilakukan, lalu klik menu tersebut di bawah ini.
#### **2. Masukkan Kode Saham (Contoh: BBRI atau BBRI.JK).**
* Setelah masukkan Kode Saham, lalu klik tombol "Mulai Analisa".
#### **3. Kembali ke "Menu Utama"**
* Bila sudah selesai analisa, klik tombol menu "Menu Utama" untuk kembali ke Beranda.
        """)
 
    st.markdown(
        "<h1 style='text-align: center; color: #ff0000; letter-spacing: 2px;'>"
        "📈 EXPERT STOCK PRO</h1>",
        unsafe_allow_html=True
    )
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
            st.button("⚡ Analisa Cepat (Belum Tersedia)", use_container_width=True, disabled=True)
 
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
        for key in ('logged_in', 'user_name', 'user_wa', 'is_trial',
                    'is_admin', 'trial_expiry_date', 'current_menu'):
            st.session_state[key] = (
                "Beranda" if key == "current_menu" else
                False     if key in ('logged_in', 'is_trial', 'is_admin') else
                ""
            )
        st.rerun()
 
 
# --- 7. MAIN ROUTER ---
def main_app():
    """Router utama — mengarahkan ke modul yang dipilih user."""
    if st.session_state.current_menu == "Beranda":
        show_dashboard()
        return
 
    # Tombol kembali
    col_back, _ = st.columns([1, 4])
    with col_back:
        st.markdown('<div class="back-btn-container">', unsafe_allow_html=True)
        if st.button("⬅️ Menu Utama"):
            st.session_state.current_menu = "Beranda"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("---")
 
    m = st.session_state.current_menu
 
    # ── PENTING: nama modul tanpa ekstensi .py ──
    if   m == "screening":    load_and_run_module("screening",    "run_screening")
    elif m == "analisa_cepat":load_and_run_module("analisa_cepat","run_analisa_cepat")
    elif m == "teknikal":     load_and_run_module("teknikal",     "run_teknikal")
    elif m == "fundamental":  load_and_run_module("fundamental",  "run_fundamental")
    elif m == "dividen":      load_and_run_module("dividen",      "run_dividen")
    elif m == "perbandingan": load_and_run_module("perbandingan", "run_perbandingan")
    else:
        st.error(f"⚠️ Menu `{m}` tidak dikenal.")
        st.session_state.current_menu = "Beranda"
        st.rerun()
 
 
# --- ENTRY POINT ---
if __name__ == "__main__":
    if st.session_state.logged_in:
        main_app()
    else:
        login_page()
 






