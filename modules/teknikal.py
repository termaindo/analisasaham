import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import base64
from datetime import datetime
import os
import pdfkit

# --- MENGGUNAKAN RELATIVE IMPORT SEBAGAI PENGAMAN ---
try:
    from modules.data_loader import get_full_stock_data
    from modules.universe import is_syariah
except ModuleNotFoundError:
    # Fallback jika dipanggil dari internal folder
    from .data_loader import get_full_stock_data
    from .universe import is_syariah

def translate_sector(sector_en):
    """Menerjemahkan sektor ke Bahasa Indonesia"""
    mapping = {
        "Financial Services": "Jasa Keuangan",
        "Basic Materials": "Bahan Baku & Tambang",
        "Energy": "Energi",
        "Communication Services": "Telekomunikasi",
        "Consumer Cyclical": "Konsumsi Siklikal",
        "Consumer Defensive": "Konsumsi Non-Siklikal",
        "Healthcare": "Kesehatan",
        "Industrials": "Industri",
        "Real Estate": "Properti",
        "Technology": "Teknologi",
        "Utilities": "Utilitas"
    }
    return mapping.get(sector_en, sector_en)

# --- FUNGSI ANALISA TEKNIKAL MENDALAM ---
def calculate_technical_pro(df):
    # 1. Moving Averages
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA50'] = df['Close'].rolling(50).mean()
    df['MA200'] = df['Close'].rolling(200).mean()
    
    # 2. RSI (Relative Strength Index)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain/loss)))
    
    # 3. MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal_Line']
    
    # 4. Bollinger Bands
    df['BB_Mid'] = df['MA20']
    df['BB_Std'] = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_Mid'] + (2 * df['BB_Std'])
    df['BB_Lower'] = df['BB_Mid'] - (2 * df['BB_Std'])

    # 5. ATR (Average True Range)
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    df['ATR'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1).rolling(14).mean()
    
    # --- TAMBAHAN INDIKATOR UNTUK SCORING 100 POIN ---
    df['Vol_MA20'] = df['Volume'].rolling(20).mean()
    df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP_20'] = (df['Typical_Price'] * df['Volume']).rolling(20).sum() / df['Volume'].rolling(20).sum()
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['Value'] = df['Close'] * df['Volume']
    
    return df

# --- FUNGSI UNTUK GENERATE PDF ---
def generate_pdf_report(html_content):
    """Menghasilkan file PDF dari HTML string menggunakan pdfkit."""
    try:
        # Konfigurasi opsi pdfkit untuk tampilan A4 dan margin
        options = {
            'page-size': 'A4',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': "UTF-8",
            'no-outline': None,
            'enable-local-file-access': None
        }
        
        # Coba generate PDF (pastikan wkhtmltopdf terinstall di sistem/server)
        pdf = pdfkit.from_string(html_content, False, options=options)
        return pdf
    except Exception as e:
        st.error(f"Gagal membuat PDF: {e}. Pastikan 'wkhtmltopdf' terinstall di server.")
        return None

def run_teknikal():
    st.title("📈 Analisa Teknikal Pro (5 Dimensi Lengkap)")
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham:", value="BBRI").upper()
    ticker = ticker_input if ticker_input.endswith(".JK") else f"{ticker_input}.JK"

    if st.button(f"Jalankan Analisa Lengkap {ticker_input}"):
        with st.spinner("Mengevaluasi tren, indikator, dan pola..."):
            # --- STANDAR ANTI-ERROR ---
            data = get_full_stock_data(ticker)
            df = data['history']
            info = data.get('info', {})
            
            if df.empty or len(df) < 200:
                st.error("Data tidak mencukupi untuk analisa MA200. Mohon coba saham lain.")
                return

            # --- PERSIAPAN DATA TEKNIKAL AWAL ---
            df = calculate_technical_pro(df)
            last = df.iloc[-1]
            prev_1 = df.iloc[-2] # Untuk perbandingan harian
            prev_5 = df.iloc[-5] # Untuk cek momentum 1 minggu lalu
            curr_price = last['Close']
            atr = last['ATR']

            # ==========================================
            # LOGIKA SCORING KOMPREHENSIF (100 POIN)
            # ==========================================
            score = 0
            
            # i) Tren Utama (Trend Alignment) — Bobot: 30 Poin
            if curr_price > last['MA200']: score += 10
            if curr_price > last['MA50']: score += 10
            if curr_price > last['MA20']: score += 10
            
            # ii) Konfirmasi Volume & Likuiditas (Smart Money) — Bobot: 20 Poin
            curr_vol = last['Volume'] if not pd.isna(last['Volume']) else 0
            avg_vol_20 = last['Vol_MA20'] if not pd.isna(last['Vol_MA20']) else 0
            vwap_val = last['VWAP_20'] if not pd.isna(last['VWAP_20']) else curr_price
            
            if curr_vol > avg_vol_20: score += 10
            if curr_price > vwap_val: score += 10
            
            # iii) Kekuatan Momentum (Momentum & Oscillator) — Bobot: 20 Poin
            if 50 <= last['RSI'] <= 70: score += 5
            if last['RSI'] > prev_1['RSI']: score += 5 # RSI Trend Naik
            if last['MACD'] > last['Signal_Line']: score += 10
                
            # iv) Agresivitas Aksi Harga (Price Action) — Bobot: 20 Poin
            if last['EMA9'] > last['EMA21']: score += 10
            if curr_price > prev_1['Close']: score += 10
            
            # v) Volatilitas & Risiko (Risk Parameters) — Bobot: 10 Poin
            if (curr_price > last['MA20']) and (curr_price <= last['BB_Upper']): score += 10

            # vi) Mapping Rekomendasi
            if score >= 80:
                signal = "STRONG BUY"
                confidence = "Sangat Tinggi (Target Operasi Utama)"
                warna_sinyal = "#4ade80" # Hijau terang
            elif score >= 60:
                signal = "BUY / ACCUMULATE"
                confidence = "Tinggi (Menunggu Konfirmasi Penuh)"
                warna_sinyal = "#3b82f6" # Biru
            elif score >= 40:
                signal = "HOLD / WAIT"
                confidence = "Menengah (Sideways / Transisi)"
                warna_sinyal = "#facc15" # Kuning
            else:
                signal = "SELL / AVOID"
                confidence = "Rendah (Hancur Lebur Secara Teknikal)"
                warna_sinyal = "#ef4444" # Merah

            # ==========================================
            # TAMPILAN HEADER
            # ==========================================
            clean_ticker = ticker_input.replace(".JK", "")
            nama_perusahaan = info.get('longName', clean_ticker)
            sektor_mentah = info.get('sector', 'Sektor Tidak Diketahui')
            sektor_id = translate_sector(sektor_mentah)
            status_syariah = "✅ Syariah" if is_syariah(clean_ticker) else "✖️ Non-Syariah"

            st.markdown(f"<h2 style='text-align: center; color: #4ade80;'>🏢 {clean_ticker} - {nama_perusahaan}</h2>", unsafe_allow_html=True)
            st.markdown(f"<h5 style='text-align: center; margin-top: -15px; color: #a3a3a3;'>Sektor: {sektor_id} | {status_syariah}</h5>", unsafe_allow_html=True)
            st.write("")
            
            st.header("🏆 SKOR TEKNIKAL")
            st.progress(score / 100.0)
            
            teks_hasil = f"**Skor: {score}/100** — Sinyal: **{signal}** ({confidence})"
            if score >= 80: st.success(teks_hasil)
            elif score >= 60: st.info(teks_hasil)
            elif score >= 40: st.warning(teks_hasil)
            else: st.error(teks_hasil)
            
            st.markdown("---")

            # --- 1. TREND ANALYSIS (Timeframe Check) ---
            main_trend = "UPTREND" if curr_price > last['MA200'] else "DOWNTREND"
            weekly_trend = "Bullish" if last['MA50'] > prev_5['MA50'] else "Bearish"
            res_level = df['High'].tail(20).max()
            sup_level = df['Low'].tail(20).min()

            # --- 2. INDIKATOR TEKNIKAL & 3. PATTERN ---
            is_div = "Terdeteksi (Bullish)" if (curr_price < prev_5['Close'] and last['RSI'] > prev_5['RSI']) else "Tidak Terdeteksi"
            
            # ==========================================
            # PEMBUATAN TRADING PLAN SESUAI ATURAN BARU
            # ==========================================
            # 1. Rentang Entry (Support Dinamis)
            # Entry Atas: Harga saat ini
            entry_atas = curr_price
            # Entry Bawah: Maksimal turun 4% dari harga saat ini ATAU EMA9
            diskon_4_persen = curr_price * 0.96
            ema9_sekarang = last['EMA9']
            # Pilih yang lebih aman (lebih dekat ke harga, namun dibatasi max diskon 4%)
            entry_bawah = max(ema9_sekarang, diskon_4_persen)
            
            # Hitung rata-rata harga entry untuk kalkulasi SL dan TP
            avg_entry = (entry_atas + entry_bawah) / 2

            # 2. Stop Loss (Maksimal 8% atau 2.5x ATR)
            sl_atr = avg_entry - (2.5 * atr)
            sl_hard = avg_entry * 0.92  # Max turun 8%
            sl_final = max(sl_atr, sl_hard) # Pilih stop loss yang lebih sempit (ketat) untuk membatasi resiko

            # 3. Target Profit (RRR 1:2, Target Gain ~15-16%)
            # Risk Nominal
            risk_nominal = avg_entry - sl_final
            # RRR 1:2 -> Target Profit adalah 2x lipat dari Risk Nominal
            tp_nominal = avg_entry + (risk_nominal * 2)
            
            # Cek Persentase Target, pastikan sekitar 15-16%
            target_gain_pct = ((tp_nominal - avg_entry) / avg_entry) * 100
            
            # Jika Target berdasarkan RRR kurang dari 15%, kita set manual ke 15% 
            # (opsional, tergantung preferensi, tapi di sini kita ikuti RRR 1:2 sebagai prioritas)
            tp_final = tp_nominal

            # Kalkulasi riil untuk ditampilkan
            risk_pct_riil = ((avg_entry - sl_final) / avg_entry) * 100
            tp_pct_riil = ((tp_final - avg_entry) / avg_entry) * 100
            rrr_riil = round(tp_pct_riil / risk_pct_riil, 1) if risk_pct_riil > 0 else 0

            # --- VISUALISASI CHART ---
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])
            
            # Chart Utama (MA20 KUNING)
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='yellow', width=2), name="MA20 (Kuning)"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['MA200'], line=dict(color='purple', width=2), name="MA200"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], line=dict(color='rgba(173, 216, 230, 0.2)'), name="BB Upper"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], line=dict(color='rgba(173, 216, 230, 0.2)'), fill='tonexty', name="BB Lower"), row=1, col=1)

            # MACD & RSI
            fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], name="MACD Hist"), row=2, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], line=dict(color='white'), name="RSI"), row=3, col=1)
            
            fig.update_layout(height=900, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- PENYAJIAN DATA 5 POIN ---
            st.markdown("---")
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("1. TREND ANALYSIS")
                st.write(f"• **Trend Utama (Daily):** {main_trend}")
                st.write(f"• **Trend Weekly/Monthly:** {weekly_trend}")
                st.write(f"• **Support/Resist:** Rp {sup_level:,.0f} / Rp {res_level:,.0f}")
                
                st.subheader("2. INDIKATOR TEKNIKAL")
                st.write(f"• **Posisi MA:** Harga {'di atas' if curr_price > last['MA20'] else 'di bawah'} MA20 Kuning")
                arah_rsi = "↗️ Naik" if last['RSI'] > prev_1['RSI'] else "↘️ Turun"
                st.write(f"• **RSI:** {last['RSI']:.1f} ({arah_rsi} | {'Overbought' if last['RSI']>70 else 'Oversold' if last['RSI']<30 else 'Neutral'})")
                st.write(f"• **MACD:** {'Bullish Cross' if last['MACD'] > last['Signal_Line'] else 'Bearish'}")
                st.write(f"• **Volatilitas:** {'Tinggi' if (last['BB_Upper']-last['BB_Lower']) > (df['BB_Upper']-df['BB_Lower']).mean() else 'Rendah'}")

            with c2:
                st.subheader("3. PATTERN RECOGNITION")
                pattern = "Doji" if abs(last['Open']-last['Close']) < (last['High']-last['Low'])*0.1 else "Normal"
                st.write(f"• **Candlestick:** {pattern}")
                st.write(f"• **Chart Pattern:** Potensi Konsolidasi / Channeling")
                st.write(f"• **Divergence:** {is_div}")

                st.subheader("4. MOMENTUM & STRENGTH")
                st.write(f"• **Momentum:** {'Kuat' if last['RSI'] > 50 else 'Lemah'}")
                st.write(f"• **Pressure:** {'Buying Pressure' if last['Close'] > last['Open'] else 'Selling Pressure'}")

            st.markdown("---")
            st.subheader("5. TRADING SIGNAL & PLAN")
            s1, s2, s3 = st.columns(3)
            with s1:
                st.metric("AREA ENTRY", f"Rp {int(entry_bawah):,.0f} - {int(entry_atas):,.0f}")
                st.caption("Max Koreksi 4% / EMA9")
            with s2:
                st.error(f"**STOP LOSS**\n\n**Rp {int(sl_final):,.0f} (-{risk_pct_riil:.1f}%)**")
                st.caption("Max Risk 8% / 2.5x ATR")
            with s3:
                st.success(f"**TARGET PROFIT**\n\n**Rp {int(tp_final):,.0f} (+{tp_pct_riil:.1f}%)**")
                st.caption(f"Risk/Reward Ratio 1 : {rrr_riil}")

            st.markdown("---")

            # ==========================================
            # PERSIAPAN KONTEN PDF (HTML)
            # ==========================================
            tanggal_hari_ini = datetime.now().strftime("%d %B %Y")
            
            html_pdf_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; line-height: 1.6; margin: 0; padding: 20px; }}
                    .header {{ text-align: center; border-bottom: 2px solid #2563eb; padding-bottom: 20px; margin-bottom: 30px; }}
                    .app-title {{ color: #2563eb; font-size: 28px; font-weight: bold; margin: 0; text-transform: uppercase; letter-spacing: 2px; }}
                    .module-title {{ color: #64748b; font-size: 18px; margin: 5px 0 15px 0; }}
                    .stock-info {{ font-size: 24px; font-weight: bold; background-color: #f1f5f9; padding: 10px; border-radius: 5px; display: inline-block; }}
                    .meta-info {{ color: #64748b; font-size: 14px; margin-top: 10px; }}
                    .score-box {{ background-color: {warna_sinyal}22; border-left: 5px solid {warna_sinyal}; padding: 15px; margin-bottom: 25px; border-radius: 4px; }}
                    .score-value {{ font-size: 20px; font-weight: bold; color: {warna_sinyal}; }}
                    h3 {{ color: #1e293b; border-bottom: 1px solid #cbd5e1; padding-bottom: 5px; margin-top: 25px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                    th, td {{ border: 1px solid #e2e8f0; padding: 10px; text-align: left; }}
                    th {{ background-color: #f8fafc; font-weight: bold; width: 40%; }}
                    .trading-plan {{ background-color: #f8fafc; border: 1px solid #cbd5e1; padding: 15px; border-radius: 5px; margin-top: 20px; }}
                    .plan-grid {{ display: flex; justify-content: space-between; margin-top: 10px; }}
                    .plan-item {{ text-align: center; padding: 10px; background: white; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); width: 30%; }}
                    .disclaimer {{ font-size: 10px; color: #94a3b8; text-align: justify; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1 class="app-title">EXPERT STOCK PRO</h1>
                    <p class="module-title">Laporan Analisa Teknikal (5 Dimensi)</p>
                    <div class="stock-info">{clean_ticker} - {nama_perusahaan}</div>
                    <p class="meta-info">Sektor: {sektor_id} | {status_syariah}<br>Tanggal Analisa: {tanggal_hari_ini} | Harga Terakhir: Rp {curr_price:,.0f}</p>
                </div>

                <div class="score-box">
                    <div class="score-value">SKOR TEKNIKAL: {score}/100</div>
                    <div style="font-size: 16px; font-weight: bold;">Rekomendasi Sinyal: {signal}</div>
                    <div style="font-size: 14px; margin-top: 5px;">Kategori: {confidence}</div>
                </div>

                <h3>1. Peta Tren & Momentum</h3>
                <table>
                    <tr><th>Trend Jangka Panjang (Daily)</th><td>{main_trend} (Posisi thd MA200)</td></tr>
                    <tr><th>Trend Jangka Menengah (Weekly)</th><td>{weekly_trend} (Arah MA50)</td></tr>
                    <tr><th>Kekuatan Momentum (RSI)</th><td>{last['RSI']:.1f} ({arah_rsi})</td></tr>
                    <tr><th>Arah Arus Dana (MACD)</th><td>{'Bullish Cross' if last['MACD'] > last['Signal_Line'] else 'Bearish'}</td></tr>
                </table>

                <h3>2. Volatilitas & Konfirmasi Smart Money</h3>
                <table>
                    <tr><th>Level Support Terdekat</th><td>Rp {sup_level:,.0f}</td></tr>
                    <tr><th>Level Resisten Terdekat</th><td>Rp {res_level:,.0f}</td></tr>
                    <tr><th>Status Volume Transaksi</th><td>{'Tinggi (Melewati MA20)' if curr_vol > avg_vol_20 else 'Normal/Rendah'}</td></tr>
                    <tr><th>Posisi Harga thd Bandar (VWAP)</th><td>{'Di Atas VWAP (Bullish)' if curr_price > vwap_val else 'Di Bawah VWAP (Bearish)'}</td></tr>
                </table>

                <h3>3. Rekomendasi Trading Plan (Swing Trading)</h3>
                <div class="trading-plan">
                    <p style="margin: 0 0 10px 0; font-weight: bold; color: #334155;">Strategi Eksekusi Terukur (RRR 1:{rrr_riil})</p>
                    <div class="plan-grid">
                        <div class="plan-item">
                            <div style="font-size: 12px; color: #64748b;">ENTRY ZONE</div>
                            <div style="font-size: 16px; font-weight: bold; color: #1e293b;">Rp {int(entry_bawah):,.0f} - {int(entry_atas):,.0f}</div>
                        </div>
                        <div class="plan-item">
                            <div style="font-size: 12px; color: #ef4444;">STOP LOSS MAX</div>
                            <div style="font-size: 16px; font-weight: bold; color: #ef4444;">Rp {int(sl_final):,.0f} (-{risk_pct_riil:.1f}%)</div>
                        </div>
                        <div class="plan-item">
                            <div style="font-size: 12px; color: #22c55e;">TARGET PROFIT</div>
                            <div style="font-size: 16px; font-weight: bold; color: #22c55e;">Rp {int(tp_final):,.0f} (+{tp_pct_riil:.1f}%)</div>
                        </div>
                    </div>
                </div>

                <div class="disclaimer">
                    <strong>DISCLAIMER:</strong> Laporan ini dihasilkan secara otomatis oleh sistem algoritma Expert Stock Pro berdasarkan data historis pasar. Semua informasi, analisa teknikal, dan sinyal trading yang disediakan hanya untuk tujuan edukasi dan referensi semata. Ini bukan merupakan rekomendasi mutlak, ajakan, atau nasihat keuangan untuk membeli atau menjual saham tertentu. Segala keputusan investasi dan risiko kerugian sepenuhnya berada di tangan investor. Kinerja masa lalu tidak menjamin hasil di masa depan. Harap lakukan riset Anda sendiri (Do Your Own Research).
                </div>
            </body>
            </html>
            """

            # ==========================================
            # TOMBOL DOWNLOAD PDF
            # ==========================================
            pdf_bytes = generate_pdf_report(html_pdf_content)
            
            if pdf_bytes:
                st.download_button(
                    label="📄 Unduh Laporan Analisa (PDF)",
                    data=pdf_bytes,
                    file_name=f"Expert_Stock_Pro_Teknikal_{clean_ticker}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            # --- DISCLAIMER (UI) ---
            st.markdown("---")
            st.warning("""
            **DISCLAIMER:** Semua informasi, analisa teknikal, dan sinyal trading yang disediakan di modul ini hanya untuk tujuan edukasi dan informasi. Ini bukan merupakan rekomendasi, ajakan, atau nasihat keuangan untuk membeli atau menjual saham tertentu. Keputusan investasi sepenuhnya berada di tangan Anda. Harap lakukan riset Anda sendiri (*Do Your Own Research*) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.
            """)
