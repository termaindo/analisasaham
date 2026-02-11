import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import pytz

def run_screening():
    st.title("🔍 Screening Saham: Top 50 + RSI & MACD")
    st.markdown("---")

    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.datetime.now(wib)
    
    st.info(f"**📅 Data Per:** {now.strftime('%d %B %Y - %H:%M')} WIB")

    if st.button("Mulai Screening (Proses ±60 Detik)"):
        saham_top50 = [
            "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "BBTN.JK", "BRIS.JK", "ARTO.JK", "BFIN.JK",
            "BREN.JK", "TPIA.JK", "BRPT.JK", "PGEO.JK", "AMMN.JK", "TLKM.JK", "ISAT.JK", "EXCL.JK", 
            "GOTO.JK", "ADRO.JK", "ANTM.JK", "MDKA.JK", "PTBA.JK", "INCO.JK", "MEDC.JK", "PANI.JK",
            "ASII.JK", "UNTR.JK", "CTRA.JK", "SMRA.JK", "ACES.JK", "MAPI.JK" # Tambahkan hingga 50
        ]

        hasil_lolos = []
        progress = st.progress(0)
        
        for i, ticker in enumerate(saham_top50):
            progress.progress((i + 1) / len(saham_top50))
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period="6mo")
                if len(df) < 50: continue

                curr = df['Close'].iloc[-1]
                vol = df['Volume'].iloc[-1]
                
                # Indikator
                df['MA20'] = df['Close'].rolling(20).mean()
                df['MA50'] = df['Close'].rolling(50).mean()
                
                # RSI
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rsi = 100 - (100 / (1 + (gain/loss)))
                curr_rsi = rsi.iloc[-1]

                # Filter: Uptrend & Liquid
                if curr > 55 and curr > df['MA20'].iloc[-1] > df['MA50'].iloc[-1] and (curr*vol) > 10_000_000_000:
                    # Hitung Score (Logika yang sama)
                    score = 60
                    if 50 <= curr_rsi <= 68: score += 20
                    
                    hasil_lolos.append({
                        "Ticker": ticker.replace(".JK", ""),
                        "Harga": curr,
                        "RSI": round(curr_rsi, 1),
                        "Confidence": f"{score}%",
                        "Rating": "⭐⭐⭐⭐" if score > 70 else "⭐⭐⭐",
                        "Value (M)": round((curr*vol)/1e9, 1),
                        "Raw_Score": score
                    })
            except: continue

        if hasil_lolos:
            hasil_lolos.sort(key=lambda x: x['Raw_Score'], reverse=True)
            df_final = pd.DataFrame(hasil_lolos)
            # PASTIKAN KOLOM RSI ADA DI SINI
            st.dataframe(df_final[["Ticker", "Rating", "Harga", "RSI", "Confidence", "Value (M)"]], use_container_width=True)
        else:
            st.warning("Tidak ada saham terjaring.")
