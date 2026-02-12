import streamlit as st
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_analisa_cepat():
    st.title("⚡ Analisa Cepat Pro (8 Poin Inti)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Cepat):", value="BBCA").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button("🚀 Mulai Analisa Kilat"):
        data = get_full_stock_data(ticker)
        info = data["info"]
        df = data["history"]
        
        if df.empty or not info:
            st.error("Gagal mengambil data. Server mungkin sedang sibuk.")
            return

        curr_price = df['Close'].iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        div_yield = hitung_div_yield_normal(info)
        
        # Skor Sederhana
        f_score = 8 if info.get('returnOnEquity', 0) > 0.15 else 6
        t_score = 8 if curr_price > ma20 else 4
        
        # Output Bahasa Indonesia (Tanpa indentasi agar tidak jadi code block)
        html_output = f"""
<div style="background-color:#1e2b3e; padding:20px; border-radius:12px; border-left:8px solid #ff0000; color:white;">
    <h3 style="margin-top:0;">{info.get('longName', ticker)}</h3>
    <ul style="line-height:1.7; font-size:15px;">
        <li><b>1. Skor Fundamental:</b> {f_score}/10 (Kinerja Keuangan)</li>
        <li><b>2. Skor Teknikal:</b> {t_score}/10 (Tren Harga Saat Ini)</li>
        <li><b>3. Sentimen Pasar:</b> {'Optimis (Bullish)' if curr_price > ma20 else 'Lesu (Bearish)'}</li>
        <li><b>4. Alasan Utama BELI:</b> Valuasi atraktif, Efisiensi tinggi, Yield Dividen {div_yield:.1f}%</li>
        <li><b>5. Risiko Utama:</b> Volatilitas sektor, Risiko pasar global, Aksi ambil untung</li>
        <li><b>6. Rekomendasi Akhir:</b> {'AKUMULASI BELI' if f_score > 7 else 'TAHAN / WAIT & SEE'}</li>
        <li><b>7. Target & Proteksi:</b> Target: Rp {curr_price*1.1:,.0f} | Stop Loss: Rp {curr_price*0.93:,.0f}</li>
        <li><b>8. Gaya Investasi:</b> {'Cocok untuk Jangka Panjang' if f_score > 7 else 'Cocok untuk Trading Pendek'}</li>
    </ul>
</div>
"""
        st.markdown(html_output, unsafe_allow_html=True)
