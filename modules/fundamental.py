import streamlit as st
import pandas as pd
from modules.data_loader import ambil_data_fundamental_lengkap, ambil_data_history

# --- DATABASE SEKTOR & BENCHMARK (RULE-BASED AI) ---
def get_sector_benchmarks(sector):
    """Menentukan PER/PBV wajar dan Outlook berdasarkan Sektor"""
    
    # Default (General)
    data = {
        "PER_Wajar": 15.0, "PBV_Wajar": 1.5,
        "Outlook": "Mengikuti pertumbuhan ekonomi makro (GDP).",
        "Katalis": "Efisiensi operasional dan ekspansi pasar.",
        "Risiko": "Inflasi dan pelemahan daya beli."
    }

    if "Financial" in sector or "Bank" in sector:
        data = {
            "PER_Wajar": 12.0, "PBV_Wajar": 2.0, # Bank biasanya PBV tinggi tapi PER rendah
            "Outlook": "Stabil seiring kebijakan suku bunga BI dan pertumbuhan kredit.",
            "Katalis": "Kenaikan Net Interest Margin (NIM) dan digital banking.",
            "Risiko": "Kredit macet (NPL) dan pengetatan likuiditas."
        }
    elif "Energy" in sector or "Mining" in sector or "Basic Material" in sector:
        data = {
            "PER_Wajar": 10.0, "PBV_Wajar": 1.2, # Komoditas sikkikal valuasi rendah
            "Outlook": "Sangat bergantung pada harga komoditas global.",
            "Katalis": "Kenaikan harga acuan (Coal/Oil/Nickel) & Hilirisasi.",
            "Risiko": "Fluktuasi harga komoditas dan regulasi lingkungan (ESG)."
        }
    elif "Consumer" in sector or "Food" in sector:
        data = {
            "PER_Wajar": 18.0, "PBV_Wajar": 3.0, # Consumer goods premium
            "Outlook": "Defensif dan tangguh terhadap resesi.",
            "Katalis": "Kenaikan UMR/Daya beli dan momen hari raya.",
            "Risiko": "Kenaikan harga bahan baku (Gandum/Gula) dan cukai."
        }
    elif "Technology" in sector:
        data = {
            "PER_Wajar": 25.0, "PBV_Wajar": 4.0, # Tech growth stock
            "Outlook": "Fokus pada pertumbuhan user base dan monetisasi.",
            "Katalis": "Adopsi AI dan ekonomi digital.",
            "Risiko": "Suku bunga tinggi (Tech Winter) dan persaingan ketat."
        }
    elif "Property" in sector or "Real Estate" in sector:
        data = {
            "PER_Wajar": 13.0, "PBV_Wajar": 0.8, # Properti sering undervalued secara PBV
            "Outlook": "Sensitif terhadap suku bunga KPR.",
            "Katalis": "Insentif PPN DTP dan pembangunan infrastruktur.",
            "Risiko": "Kenaikan suku bunga dan daya beli properti melemah."
        }
    
    return data

def format_idr(value):
    if value is None or value == 0: return "-"
    if abs(value) >= 1e12: return f"{value/1e12:.2f} T"
    if abs(value) >= 1e9: return f"{value/1e9:.2f} M"
    return f"{value:,.0f}"

# --- PROGRAM UTAMA ---
def run_fundamental():
    st.title("📊 Analisa Fundamental Pro (Sektoral)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="BBRI").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Bedah {ticker_input} (5 Bab Lengkap)"):
        with st.spinner("Menggali data & mencocokkan sektor..."):
            # 1. AMBIL DATA (Pakai Loader Anti-Error)
            info, financials, balance = ambil_data_fundamental_lengkap(ticker)
            df_hist = ambil_data_history(ticker, period="1mo")

            if df_hist.empty:
                st.error("Data saham tidak ditemukan.")
                return
            
            # 2. PERSIAPAN VARIABEL
            curr_price = info.get('currentPrice', df_hist['Close'].iloc[-1])
            market_cap = info.get('marketCap', 0)
            sector = info.get('sector', 'General')
            industry = info.get('industry', '-')
            
            # AMBIL DATA CERDAS BERDASARKAN SEKTOR
            sector_data = get_sector_benchmarks(sector)

            # --- HEADER ---
            st.subheader(f"🏢 {info.get('longName', ticker_input)}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Harga", f"Rp {curr_price:,.0f}")
            c2.metric("Market Cap", format_idr(market_cap))
            c3.metric("Sektor", sector)

            # ==========================================
            # BAB 1: OVERVIEW PERUSAHAAN
            # ==========================================
            st.markdown("---")
            st.header("1. OVERVIEW & POSISI")
            
            # Analisa Posisi (Leader/Challenger)
            if market_cap > 100e12: posisi = "Market Leader (Big Cap 🦍)"
            elif market_cap > 10e12: posisi = "Challenger (Mid Cap 🐅)"
            else: posisi = "Niche Player (Small Cap 🐈)"
            
            st.write(f"**Bisnis Utama:** {info.get('longBusinessSummary', 'N/A')[:400]}...")
            st.info(f"**Posisi Industri:** {posisi} | **Industri:** {industry}")
            st.write(f"**Competitive Advantage:** Brand kuat di sektor {sector} dengan skala kapitalisasi {format_idr(market_cap)}.")

            # ==========================================
            # BAB 2: ANALISA KEUANGAN (TREND)
            # ==========================================
            st.header("2. KESEHATAN KEUANGAN (3-4 TAHUN)")
            
            if not financials.empty:
                try:
                    # Coba ambil data Revenue & Net Income
                    rev = financials.loc['Total Revenue'] if 'Total Revenue' in financials.index else financials.iloc[0]
                    ni = financials.loc['Net Income'] if 'Net Income' in financials.index else financials.iloc[-1]
                    
                    # Tampilkan Tabel Trend
                    years = rev.index.year
                    df_trend = pd.DataFrame({
                        "Revenue": [format_idr(x) for x in rev.head(4)],
                        "Net Income": [format_idr(x) for x in ni.head(4)],
                        "Net Margin": [f"{(n/r)*100:.1f}%" if r!=0 else "-" for n, r in zip(ni.head(4), rev.head(4))]
                    }, index=years)
                    st.table(df_trend)

                    # Analisa Pertumbuhan (EPS Growth & Revenue)
                    rev_grow = ((rev.iloc[0] - rev.iloc[1])/rev.iloc[1])*100
                    eps_grow = info.get('earningsGrowth', 0) * 100
                    st.write(f"📈 **Revenue Growth (YoY):** {rev_grow:+.1f}% | **EPS Growth:** {eps_grow:+.1f}%")
                except:
                    st.warning("Format laporan keuangan tidak standar.")
            else:
                st.warning("Data historis keuangan tidak tersedia.")

            # Rasio Kesehatan
            c_k1, c_k2, c_k3 = st.columns(3)
            c_k1.metric("ROE", f"{info.get('returnOnEquity', 0)*100:.1f}%")
            c_k2.metric("DER (Utang)", f"{info.get('debtToEquity', 0):.2f}x")
            c_k3.metric("Current Ratio", f"{info.get('currentRatio', 0):.2f}x")

            # ==========================================
            # BAB 3: VALUASI (KOMPARASI SEKTORAL)
            # ==========================================
            st.header("3. VALUASI WAJAR")
            
            # Ambil Data Real
            eps = info.get('trailingEps', 0)
            if eps == 0 and 'sharesOutstanding' in info: # Hitung manual jika EPS 0
                 eps = info.get('netIncomeToCommon', 0) / info['sharesOutstanding']
                 
            bvps = info.get('bookValue', 0)
            
            pe = info.get('trailingPE', curr_price/eps if eps > 0 else 0)
            pbv = info.get('priceToBook', curr_price/bvps if bvps > 0 else 0)
            div_yield = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0

            # Ambil Benchmark Sektor
            pe_wajar = sector_data["PER_Wajar"]
            pbv_wajar = sector_data["PBV_Wajar"]

            # Tabel Komparasi
            val_df = pd.DataFrame({
                "Metode": ["PER (Laba)", "PBV (Buku)", "Div. Yield"],
                "Saham Ini": [f"{pe:.2f}x", f"{pbv:.2f}x", f"{div_yield:.2f}%"],
                f"Wajar ({sector})": [f"{pe_wajar}x", f"{pbv_wajar}x", "> 4%"],
                "Status": ["MURAH" if pe < pe_wajar else "MAHAL", 
                           "MURAH" if pbv < pbv_wajar else "MAHAL", 
                           "BAGUS" if div_yield > 4 else "KECIL"]
            })
            st.table(val_df.set_index("Metode"))

            # Hitung Harga Wajar (Modified Graham untuk Sektor)
            if eps > 0 and bvps > 0:
                fair_price = ((eps * pe_wajar) + (bvps * pbv_wajar)) / 2
                mos = ((fair_price - curr_price) / fair_price) * 100
                st.success(f"💰 **Harga Wajar (Estimasi Sektoral): Rp {fair_price:,.0f}**")
                st.metric("Margin of Safety (MoS)", f"{mos:.1f}%")
            else:
                st.warning("Perusahaan Rugi (EPS Negatif). Tidak bisa divaluasi dengan metode PER.")
                fair_price = curr_price
                mos = -99

            # ==========================================
            # BAB 4: PROSPEK BISNIS (DINAMIS)
            # ==========================================
            st.header("4. PROSPEK BISNIS")
            st.info(f"**Outlook Industri:** {sector_data['Outlook']}")
            
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.write("✅ **Growth Catalyst:**")
                st.write(f"- {sector_data['Katalis']}")
                st.write("- Potensi pemulihan ekonomi domestik.")
            with col_p2:
                st.write("⚠️ **Risk Factors:**")
                st.write(f"- {sector_data['Risiko']}")
                st.write("- Volatilitas pasar global.")

            # ==========================================
            # BAB 5: REKOMENDASI FINAL
            # ==========================================
            st.header("5. REKOMENDASI ACTION")
            
            # Logic Rekomendasi
            roe = info.get('returnOnEquity', 0)
            if mos > 15 and roe > 0.08:
                rec = "BUY / ACCUMULATE"
                color = "green"
                reason = f"Sangat Undervalued (MoS {mos:.0f}%) & Profitable (ROE {roe*100:.1f}%)."
            elif mos > -5:
                rec = "HOLD"
                color = "orange"
                reason = "Harga Wajar (Fair Value). Hold untuk Dividen/Trend."
            else:
                rec = "SELL / WAIT"
                color = "red"
                reason = f"Overvalued (Mahal). Harga pasar > Harga wajar sektoral."

            # Tampilkan Kartu Rekomendasi
            st.markdown(f"""
            <div style="background-color:#1e2b3e; padding:20px; border-radius:10px; border-left:10px solid {color};">
                <h2 style="color:{color}; margin-top:0;">{rec}</h2>
                <p><b>Alasan:</b> {reason}</p>
                <hr>
                <div style="display:flex; justify-content:space-between;">
                    <div>🎯 <b>TP Pendek (3-6 Bln):</b><br>Rp {curr_price*1.1:,.0f}</div>
                    <div>🏆 <b>TP Panjang (Fair):</b><br>Rp {fair_price:,.0f}</div>
                    <div>🛑 <b>Stop Loss:</b><br>Rp {curr_price*0.92:,.0f}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
