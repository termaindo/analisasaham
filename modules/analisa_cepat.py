import streamlit as st
from modules.data_loader import get_full_stock_data, hitung_div_yield

def run_analisa_cepat():
    st.title("⚡ Analisa Cepat (8 Poin)")
    st.markdown("---")

    ticker_input = st.text_input("Kode Saham (Quick):", value="BBCA").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button("⚡ Jalankan Analisa Kilat"):
        data = get_full_stock_data(ticker)
        info = data["info"]
        df = data["history"]
        
        if df.empty:
            st.error("Data tidak ditemukan. Coba lagi nanti.")
            return

        curr_price = df['Close'].iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        div_yield = hitung_div_yield(info)
        
        # Scoring Sederhana
        f_score = 8 if info.get('returnOnEquity', 0) > 0.15 else 6
        t_score = 8 if curr_price > ma20 else 4
        
        # Output 8 Poin tanpa spasi di awal baris (Anti-Code-Block)
        html_output = f"""
<div style="background-color:#1e2b3e; padding:20px; border-radius:10px; border-left:8px solid #ff0000; color:white;">
    <h2 style="margin-top:0;">REKOMENDASI: {'BUY' if t_score > 5 else 'HOLD'}</h2>
    <ul style="line-height:1.6;">
        <li><b>1. Fundamental Score (1-10):</b> {f_score}/10 (ROE Sehat)</li>
        <li><b>2. Technical Score (1-10):</b> {t_score}/10 ({'Uptrend' if t_score > 5 else 'Downtrend'})</li>
        <li><b>3. Sentiment Pasar:</b> {'Bullish' if curr_price > ma20 else 'Bearish'}</li>
        <li><b>4. 3 Alasan BUY:</b> Fundamental kuat, Dominasi Sektor, Yield Dividen {div_yield:.1f}%</li>
        <li><b>5. 3 Risiko Utama:</b> Volatilitas pasar, Suku bunga, Profit taking</li>
        <li><b>6. Rekomendasi Final:</b> {'ACCUMULATE BUY' if f_score > 7 else 'WAIT & SEE'}</li>
        <li><b>7. Target & Stop Loss:</b> TP: {curr_price*1.1:,.0f} | SL: {curr_price*0.92:,.0f}</li>
        <li><b>8. Investasi:</b> {'Jangka Panjang' if f_score > 7 else 'Jangka Pendek'}</li>
    </ul>
</div>
"""
        st.markdown(html_output, unsafe_allow_html=True)
