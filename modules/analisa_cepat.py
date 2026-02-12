import streamlit as st
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

def run_analisa_cepat():
    st.title("⚡ Analisa Cepat (8 Poin Inti)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Quick):", value="BBCA").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button("⚡ Jalankan Analisa"):
        data = get_full_stock_data(ticker)
        info = data["info"]
        df = data["history"]
        
        if df.empty or not info:
            st.error("Gagal memuat data. Mohon tunggu sejenak.")
            return

        curr_price = df['Close'].iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        div_yield = hitung_div_yield_normal(info)
        
        f_score = 8 if info.get('returnOnEquity', 0) > 0.15 else 6
        t_score = 8 if curr_price > ma20 else 4
        
        # Tampilan 8 Poin (Dihapus indentasi agar tidak jadi code block)
        html_output = f"""
<div style="background-color:#1e2b3e; padding:20px; border-radius:10px; border-left:8px solid #ff0000; color:white;">
    <h3 style="margin-top:0;">{info.get('longName', ticker)}</h3>
    <ul style="line-height:1.6; font-size:15px;">
        <li><b>1. Fundamental Score:</b> {f_score}/10 (ROE & Profitabilitas)</li>
        <li><b>2. Technical Score:</b> {t_score}/10 (Tren vs MA20)</li>
        <li><b>3. Sentiment:</b> {'Bullish' if curr_price > ma20 else 'Bearish'}</li>
        <li><b>4. Alasan BUY:</b> Valuasi Wajar, Market Leader, Yield {div_yield:.1f}%</li>
        <li><b>5. Risiko Utama:</b> Profit taking, Suku bunga, Global risk</li>
        <li><b>6. Rekomendasi:</b> {'ACCUMULATE BUY' if f_score > 7 else 'HOLD'}</li>
        <li><b>7. Target & SL:</b> TP: {curr_price*1.1:,.0f} | SL: {curr_price*0.93:,.0f}</li>
        <li><b>8. Investasi:</b> {'Jangka Panjang' if f_score > 7 else 'Jangka Pendek'}</li>
    </ul>
</div>
"""
        st.markdown(html_output, unsafe_allow_html=True)
