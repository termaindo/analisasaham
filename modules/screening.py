import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import pytz

def run_screening():
    st.title("🔍 Screening Saham Harian")
    
    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(wib)
    st.info(f"📅 Data Per: {now.strftime('%d %B %Y - %H:%M')} WIB")

    if st.button("Mulai Screening (Proses ±60 Detik)"):
        # Daftar 50 Saham (Singkatan untuk contoh)
        saham_list = ["BBCA.JK", "BBRI.JK", "TLKM.JK", "ASII.JK", "GOTO.JK", "BMRI.JK", "BBNI.JK", "BRIS.JK", "ADRO.JK", "ANTM.JK", "PGEO.JK", "MAPI.JK", "BBTN.JK", "TINS.JK"] 
        
        hasil = []
        prog = st.progress(0)
        
        for i, ticker in enumerate(saham_list):
            prog.progress((i + 1) / len(saham_list))
            try:
                data = yf.Ticker(ticker).history(period="6mo")
                if len(data) < 50: continue
                
                curr = data['Close'].iloc[-1]
                # Hitung RSI 14
                delta = data['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rsi = 100 - (100 / (1 + (gain/loss)))
                curr_rsi = rsi.iloc[-1]
                
                # Logika Skor (Sederhana)
                score = 70 if curr_rsi > 50 else 50
                
                hasil.append({
                    "Ticker": ticker.replace(".JK", ""),
                    "Rating": "⭐⭐⭐⭐" if score >= 70 else "⭐⭐⭐",
                    "Harga": int(curr),
                    "RSI": round(curr_rsi, 1),
                    "Confidence": f"{score}%",
                    "Value (M)": round((curr * data['Volume'].iloc[-1]) / 1e9, 1),
                    "Raw_Score": score
                })
            except: continue

        if hasil:
            hasil.sort(key=lambda x: x['Raw_Score'], reverse=True)
            df = pd.DataFrame(hasil)
            # BAGIAN PENTING: Menampilkan kolom RSI & Confidence
            st.dataframe(df[["Ticker", "Rating", "Harga", "RSI", "Confidence", "Value (M)"]], use_container_width=True)
        else:
            st.warning("Tidak ada saham terjaring.")
