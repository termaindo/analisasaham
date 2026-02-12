import streamlit as st
import pandas as pd
import numpy as np
from modules.data_loader import get_full_stock_data

def run_screening():
    st.title("🔔 High Prob. Take Profit Screener (Max Loss 8%)")
    st.markdown("---")

    if st.button("Mulai Screening (RRR > 1.3x)"):
        saham_list = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "ASII.JK", "TLKM.JK", "UNTR.JK", "ADRO.JK", "ITMG.JK", "PTBA.JK", "ANTM.JK", "MDKA.JK", "INCO.JK"] # Daftar bisa ditambah
        hasil_lolos = []
        progress_bar = st.progress(0)

        for i, ticker in enumerate(saham_list):
            progress_bar.progress((i + 1) / len(saham_list))
            try:
                data = get_full_stock_data(ticker)
                df = data['history']
                if df.empty or len(df) < 30: continue

                curr = df['Close'].iloc[-1]
                # Kalkulasi ATR
                tr = (df['High'] - df['Low']).tail(14).mean()
                
                # --- LOGIKA SL 8% ---
                sl_atr = curr - (1.5 * tr)
                sl_final = max(sl_atr, curr * 0.92) # Kunci di 8%
                risk_pct = ((curr - sl_final) / curr) * 100
                
                tp_final = curr + (curr - sl_final) * 2 # Target RRR 1:2
                rrr = (tp_final - curr) / (curr - sl_final)

                # Scoring Momentum
                rsi_val = 100 - (100 / (1 + (df['Close'].diff().where(df['Close'].diff() > 0, 0).tail(14).mean() / -df['Close'].diff().where(df['Close'].diff() < 0, 0).tail(14).mean())))
                
                if 50 < rsi_val < 70 and rrr >= 1.3:
                    hasil_lolos.append({
                        "Ticker": ticker.replace(".JK", ""),
                        "Harga": int(curr),
                        "RSI": round(rsi_val, 1),
                        "Stop Loss": int(sl_final),
                        "Take Profit": int(tp_final),
                        "Risk_Pct": f"{risk_pct:.1f}%",
                        "RRR": f"{rrr:.1f}x"
                    })
            except: continue

        progress_bar.empty()
        if hasil_lolos:
            st.success(f"Ditemukan {len(hasil_lolos)} saham potensial.")
            st.dataframe(pd.DataFrame(hasil_lolos), use_container_width=True)
        else:
            st.warning("Tidak ada saham yang memenuhi kriteria risiko di bawah 8% saat ini.")
