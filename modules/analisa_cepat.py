import streamlit as st
from modules.data_loader import get_full_stock_data

def run_analisa_cepat():
    st.title("⚡ Analisa Cepat Pro (8 Poin Inti)")
    ticker_input = st.text_input("Kode Saham:", value="BBCA").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button("Jalankan Analisa"):
        data = get_full_stock_data(ticker)
        df, info = data["history"], data["info"]
        if df.empty: return

        curr = df['Close'].iloc[-1]
        atr = (df['High'] - df['Low']).tail(14).mean()
        
        # Logika SL 8%
        sl_raw = curr - (1.5 * atr)
        sl_final = max(sl_raw, curr * 0.92)
        tp_final = curr + (curr - sl_final) * 2

        html_output = f"""
<div style="background-color:#1e2b3e; padding:20px; border-radius:10px; border-left:8px solid #ff0000; color:white;">
    <h3 style="margin-top:0;">{info.get('longName', ticker)}</h3>
    <ul style="line-height:1.7;">
        <li><b>1. Skor Fundamental:</b> {8 if info.get('returnOnEquity', 0) > 0.15 else 6}/10</li>
        <li><b>2. Skor Teknikal:</b> {7 if curr > df['Close'].rolling(20).mean().iloc[-1] else 4}/10</li>
        <li><b>3. Sentimen:</b> {'Bullish' if curr > df['Close'].rolling(20).mean().iloc[-1] else 'Bearish'}</li>
        <li><b>4. Alasan BUY:</b> Valuasi atraktif & Momentum teknikal terjaga.</li>
        <li><b>5. Risiko Utama:</b> Perubahan suku bunga & Batas Stop Loss 8%.</li>
        <li><b>6. Rekomendasi:</b> {'AKUMULASI BELI' if curr > sl_final else 'TAHAN'}</li>
        <li><b>7. Target & Stop Loss:</b> <br>🎯 TP: Rp {tp_final:,.0f} | 🛑 SL: Rp {sl_final:,.0f}</li>
        <li><b>8. Gaya Investasi:</b> Swing Trading (RRR 1:2)</li>
    </ul>
</div>
"""
        st.markdown(html_output, unsafe_allow_html=True)
