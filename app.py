import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import pytz

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="Expert Stock Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- KEAMANAN PASSWORD (SECRETS) ---
try:
    PASSWORD_RAHASIA = st.secrets["PASSWORD_RAHASIA"]
except FileNotFoundError:
    PASSWORD_RAHASIA = "12345" # Password cadangan lokal

# Link Pembelian (Updated)
LINK_LYNK_ID = "https://lynk.id/hahastoresby"

# ==========================================
# 2. CSS CUSTOM (TAMPILAN)
# ==========================================
def local_css():
    st.markdown("""
    <style>
    /* Tombol Beli Merah */
    a[href^="https://lynk.id"] {
        background-color: #ff4b4b;
        color: white;
        text-decoration: none;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        display: block;
        text-align: center;
        font-weight: bold;
        border: 1px solid #ff4b4b;
    }
    a[href^="https://lynk.id"]:hover {
        background-color: #cc0000;
        border-color: #cc0000;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. FUNGSI FITUR-FITUR
# ==========================================

# --- FITUR 1: SCREENING SAHAM (50 SAHAM + CONFIDENCE SCORE) ---
def fitur_screening():
    st.title("🔍 Screening Saham: Top 50 + Confidence Level")
    st.markdown("---")

    # A. SINKRONISASI WAKTU
    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(wib)
    jam_sekarang = now.strftime('%H:%M')
    tanggal_sekarang = now.strftime('%d %B %Y')

    if now.hour < 16:
        sesi_pasar = "LIVE MARKET (Fokus: Volatilitas Intraday)"
    else:
        sesi_pasar = "POST MARKET (Fokus: Analisa Penutupan)"

    st.info(f"""
    **📅 Waktu:** {tanggal_sekarang} - {jam_sekarang} WIB
    **🎯 Fokus:** 50 Saham Paling Likuid
    **⭐ Fitur Baru:** Skor Confidence (Tingkat Keyakinan)
    """)

    # B. KRITERIA SCREENING
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        * ✅ Trend: Harga > MA20 > MA50
        * ✅ Volume Spike (Ada Lonjakan)
        """)
    with col2:
        st.markdown("""
        * ✅ Value Transaksi > 10 Miliar
        * ✅ **MACD Confirmation** (Penambah Skor)
        """)

    tombol_scan = st.button("Mulai Screening (Proses ±60 Detik)")

    # C. DAFTAR 50 SAHAM
    saham_top50 = [
        "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BBTN.JK", "BRIS.JK", "ARTO.JK", "BFIN.JK",
        "BREN.JK", "TPIA.JK", "BRPT.JK", "PGEO.JK", "AMMN.JK",
        "TLKM.JK", "ISAT.JK", "EXCL.JK", "TOWR.JK", "MTEL.JK",
        "GOTO.JK", "BUKA.JK", "EMTK.JK",
        "ADRO.JK", "ANTM.JK", "MDKA.JK", "PTBA.JK", "INCO.JK", 
        "PGAS.JK", "MEDC.JK", "AKRA.JK", "HRUM.JK", "ITMG.JK", "TINS.JK", "MBMA.JK",
        "ICBP.JK", "INDF.JK", "UNVR.JK", "AMRT.JK", "CPIN.JK", "MYOR.JK", "ACES.JK", "MAPI.JK",
        "CTRA.JK", "SMRA.JK", "BSDE.JK", "PWON.JK", "PANI.JK",
        "ASII.JK", "UNTR.JK", "KLBF.JK", "JSMR.JK"
    ]

    # D. LOGIKA SCREENING
    if tombol_scan:
        hasil_lolos = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_saham = len(saham_top50)

        for i, ticker in enumerate(saham_top50):
            progress = (i + 1) / total_saham
            progress_bar.progress(progress)
            status_text.text(f"Menganalisa ({i+1}/{total_saham}): {ticker}...")

            try:
                stock = yf.Ticker(ticker)
                # Ambil data 6 bulan untuk perhitungan MACD yang akurat
                df = stock.history(period="6mo") 

                if len(df) < 55: continue

                current_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                volume_now = df['Volume'].iloc[-1]
                
                # --- HITUNG INDIKATOR ---
                df['MA20'] = df['Close'].rolling(window=20).mean()
                df['MA50'] = df['Close'].rolling(window=50).mean()
                df['VolMA20'] = df['Volume'].rolling(window=20).mean()

                ma20 = df['MA20'].iloc[-1]
                ma50 = df['MA50'].iloc[-1]
                vol_avg = df['VolMA20'].iloc[-1]
                
                # MACD Calculation
                exp12 = df['Close'].ewm(span=12, adjust=False).mean()
                exp26 = df['Close'].ewm(span=26, adjust=False).mean()
                macd = exp12 - exp26
                signal_line = macd.ewm(span=9, adjust=False).mean()
                
                macd_value = macd.iloc[-1]
                signal_value = signal_line.iloc[-1]
                is_macd_bullish = macd_value > signal_value

                transaksi_value = current_price * volume_now

                # --- FILTER WAJIB ---
                cond1 = current_price > 55
                cond2 = (current_price > ma20) and (ma20 > ma50) # Uptrend
                cond3 = transaksi_value > 10_000_000_000 # Liquid > 10M
                cond4 = volume_now > vol_avg # Volume Spike

                if cond1 and cond2 and cond3 and cond4:
                    support_level = df['Low'].tail(20).min()
                    resist_level = df['High'].tail(20).max()
                    
                    risk_pct = ((support_level - current_price) / current_price) * 100
                    reward_pct = ((resist_level - current_price) / current_price) * 100
                    chg_pct = ((current_price - prev_price) / prev_price) * 100

                    # --- SCORING SYSTEM ---
                    score = 50
                    if volume_now > (vol_avg * 1.5): score += 15
                    if is_macd_bullish: score += 20
                    risk_abs = abs(risk_pct)
                    if reward_pct > (risk_abs * 2): score += 15

                    if score >= 85: label_score = "⭐⭐⭐⭐⭐ (Sangat Kuat)"
                    elif score >= 70: label_score = "⭐⭐⭐⭐ (Kuat)"
                    else: label_score = "⭐⭐⭐ (Cukup)"

                    hasil_lolos.append({
                        "Ticker": ticker.replace(".JK", ""),
                        "Harga": current_price,
                        "Chg (%)": round(chg_pct, 2),
                        "Confidence": f"{score}%",
                        "Rating": label_score,
                        "Value (M)": round(transaksi_value / 1_000_000_000, 1),
                        "Support": support_level,
                        "Resist": resist_level,
                        "Risk (%)": round(risk_pct, 2),
                        "Reward (%)": round(reward_pct, 2),
                        "Raw_Score": score
                    })
            except Exception:
                continue 

        progress_bar.empty()
        status_text.empty()

        if len(hasil_lolos) > 0:
            hasil_lolos.sort(key=lambda x: x['Raw_Score'], reverse=True)
            st.success(f"Ditemukan {len(hasil_lolos)} saham potensial!")
            
            df_hasil = pd.DataFrame(hasil_lolos)
            st.dataframe(df_hasil[["Ticker", "Rating", "Harga",
