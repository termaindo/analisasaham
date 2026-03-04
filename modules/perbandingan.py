import streamlit as st
import pandas as pd
import os
import base64
from fpdf import FPDF
from datetime import datetime
from modules.data_loader import get_full_stock_data, hitung_div_yield_normal

# --- FUNGSI PDF MENGGUNAKAN FPDF ---
def generate_pdf_fpdf(data, logo_path="logo_expert_stock_pro.png"):
    """Membangun PDF dari awal menggunakan fpdf dengan Header Box Hitam elegan"""
    pdf = FPDF()
    pdf.add_page()
    
    # --- 1. HEADER BOX HITAM ---
    pdf.set_fill_color(20, 20, 20)  # Warna Hitam (Almost Black)
    pdf.rect(0, 0, 210, 25, 'F')    # Lebar A4 = 210mm
    
    # Cari lokasi logo jika dipanggil dari sub-folder
    if not os.path.exists(logo_path):
        if os.path.exists("../logo_expert_stock_pro.png"):
            logo_path = "../logo_expert_stock_pro.png"

    # a) LOGO dengan Bingkai Emas
    if os.path.exists(logo_path):
        pdf.set_fill_color(218, 165, 32) # Goldenrod color
        pdf.rect(10, 3, 19, 19, 'F')
        pdf.image(logo_path, x=10.5, y=3.5, w=18, h=18)
    
    # b) & c) NAMA APLIKASI & MODUL (Teks Putih)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    pdf.set_xy(35, 8) 
    pdf.cell(0, 10, "Expert Stock Pro - Perbandingan Saham Pro", ln=True)
    
    # Reset posisi Y ke bawah kotak hitam
    pdf.set_y(28)
    
    # --- 2. HYPERLINK SUMBER ---
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(0, 0, 255)  # Warna Biru
    pdf.cell(0, 5, "Sumber: https://bit.ly/sahampintar", ln=True, align='C', link="https://bit.ly/sahampintar")
    pdf.ln(2)
    
    # --- 3. JUDUL PERBANDINGAN (CENTER) ---
    pdf.set_text_color(0, 0, 0) # Kembali ke Hitam
    pdf.set_font("Arial", 'B', 20)
    tk1, tk2 = data['tk1'], data['tk2']
    pdf.cell(0, 8, f"{tk1} vs {tk2}", ln=True, align='C')
    pdf.ln(2)
    
    # --- 4. INFO TANGGAL (RATA KANAN) ---
    pdf.set_font("Arial", 'B', 10)
    waktu_analisa = datetime.now().strftime("%d-%m-%Y %H:%M")
    pdf.cell(0, 5, f"Waktu Analisa: {waktu_analisa}", ln=True, align='R')
    
    # Garis Bawah Header
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y()+2, 200, pdf.get_y()+2)
    pdf.ln(6)

    # --- 5. TABEL PERBANDINGAN ---
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(60, 8, "Kriteria", border=1, align='C')
    pdf.cell(65, 8, tk1, border=1, align='C')
    pdf.cell(65, 8, tk2, border=1, align='C')
    pdf.ln()

    pdf.set_font("Arial", '', 10)
    comp_data = data['comparison_data']
    for i in range(len(comp_data['Kriteria'])):
        # Menghapus emoji secara manual untuk menghindari error FPDF (Latin-1)
        val1 = str(comp_data[tk1][i]).replace("🐂", "").replace("🐻", "").strip()
        val2 = str(comp_data[tk2][i]).replace("🐂", "").replace("🐻", "").strip()
        
        pdf.cell(60, 8, str(comp_data['Kriteria'][i]), border=1)
        pdf.cell(65, 8, val1, border=1, align='C')
        pdf.cell(65, 8, val2, border=1, align='C')
        pdf.ln()

    pdf.ln(5)

    # --- 6. KESIMPULAN & REKOMENDASI ---
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "KESIMPULAN & REKOMENDASI", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(0, 6, f"Pilihan #1: {data['p1']} - {data['r1']}")
    pdf.multi_cell(0, 6, f"Pilihan #2: {data['p2']} - {data['r2']}")
    pdf.ln(3)

    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, "Saham mana yang paling worth it untuk dibeli SEKARANG?", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(0, 6, f"JAWABAN: {data['best']}\nALASAN: {data['reason']}")
    pdf.ln(10)

    # --- 7. DISCLAIMER ---
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(0, 5, "DISCLAIMER:", ln=True)
    pdf.set_font("Arial", 'I', 8)
    disclaimer_text = (
        "Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma indikator teknikal "
        "dan fundamental. Seluruh informasi yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau "
        "paksaan untuk membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi tanggung "
        "jawab pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik dan Do Your Own "
        "Research (DYOR) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal."
    )
    pdf.multi_cell(0, 5, disclaimer_text)

    # Return bytes dari string output
    return pdf.output(dest="S").encode('latin1', errors='replace')


def run_perbandingan():
    # --- TAMPILAN WEB ---
    logo_file = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_file):
        logo_file = "../logo_expert_stock_pro.png"
        
    # Tampilkan Logo di Web bagian TENGAH (CENTER) dengan ukuran 150px
    if os.path.exists(logo_file):
        with open(logo_file, "rb") as f:
            data = f.read()
            encoded_img = base64.b64encode(data).decode()
        
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; margin-bottom: 10px;">
                <img src="data:image/png;base64,{encoded_img}" width="150">
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown("<h1 style='text-align: center;'>⚖️ Perbandingan Saham Pro (Head to Head)</h1>", unsafe_allow_html=True)
    else:
        st.markdown("<h1 style='text-align: center;'>⚖️ Perbandingan Saham Pro (Head to Head)</h1>", unsafe_allow_html=True)
        st.warning("⚠️ File logo belum ditemukan.")

    st.markdown("---")

    c_input1, c_input2 = st.columns(2)
    with c_input1:
        tk1 = st.text_input("Kode Saham 1:", value="BBCA").upper()
    with c_input2:
        tk2 = st.text_input("Kode Saham 2:", value="BBRI").upper()

    if st.button(f"Bandingkan {tk1} vs {tk2}"):
        with st.spinner(f"Mengadu data {tk1} dan {tk2}..."):
            # --- STANDAR ANTI-ERROR ---
            t1 = tk1 if tk1.endswith(".JK") else f"{tk1}.JK"
            t2 = tk2 if tk2.endswith(".JK") else f"{tk2}.JK"
            
            data1 = get_full_stock_data(t1)
            data2 = get_full_stock_data(t2)
            
            if not data1['info'] or not data2['info']:
                st.error("Gagal mengambil data salah satu saham. Cek koneksi atau kode ticker.")
                return

            i1, i2 = data1['info'], data2['info']
            h1, h2 = data1['history'], data2['history']

            # --- KALKULASI TEKNIKAL & SL 8% ---
            def get_tech_status(df):
                curr = df['Close'].iloc[-1]
                ma200 = df['Close'].rolling(200).mean().iloc[-1]
                return "Bullish 🐂" if curr > ma200 else "Bearish 🐻"

            def get_sl_cap(df):
                curr = df['Close'].iloc[-1]
                atr = (df['High'] - df['Low']).tail(14).mean()
                sl_atr = curr - (1.5 * atr)
                return max(sl_atr, curr * 0.92) # LOCK 8%

            # --- KONSTRUKSI TABEL PERBANDINGAN ---
            comparison_data = {
                "Kriteria": [
                    "Market Cap", "PER", "PBV", "ROE", "Debt/Equity", 
                    "Revenue Growth", "Profit Margin", "Dividend Yield", "Technical Trend", "Stop Loss (Max 8%)"
                ],
                tk1: [
                    f"Rp {i1.get('marketCap', 0)/1e12:,.1f} T",
                    f"{i1.get('trailingPE', 0):.2f}x",
                    f"{i1.get('priceToBook', 0):.2f}x",
                    f"{i1.get('returnOnEquity', 0)*100:.1f}%",
                    f"{i1.get('debtToEquity', 0):.2f}x",
                    f"{i1.get('revenueGrowth', 0)*100:.1f}%",
                    f"{i1.get('profitMargins', 0)*100:.1f}%",
                    f"{hitung_div_yield_normal(i1):.2f}%",
                    get_tech_status(h1),
                    f"Rp {get_sl_cap(h1):,.0f}"
                ],
                tk2: [
                    f"Rp {i2.get('marketCap', 0)/1e12:,.1f} T",
                    f"{i2.get('trailingPE', 0):.2f}x",
                    f"{i2.get('priceToBook', 0):.2f}x",
                    f"{i2.get('returnOnEquity', 0)*100:.1f}%",
                    f"{i2.get('debtToEquity', 0):.2f}x",
                    f"{i2.get('revenueGrowth', 0)*100:.1f}%",
                    f"{i2.get('profitMargins', 0)*100:.1f}%",
                    f"{hitung_div_yield_normal(i2):.2f}%",
                    get_tech_status(h2),
                    f"Rp {get_sl_cap(h2):,.0f}"
                ]
            }

            st.table(pd.DataFrame(comparison_data).set_index("Kriteria"))

            # --- KESIMPULAN & REKOMENDASI ---
            st.markdown("---")
            st.header("💡 KESIMPULAN")
            
            # Logika penentuan Pilihan #1
            if i1.get('returnOnEquity', 0) > i2.get('returnOnEquity', 0):
                p1, p2 = tk1, tk2
                r1 = "Efisiensi mencetak laba (ROE) lebih tinggi."
                r2 = "Valuasi mungkin lebih murah namun efisiensi di bawah Pilihan #1."
            else:
                p1, p2 = tk2, tk1
                r1 = "Efisiensi mencetak laba (ROE) lebih unggul."
                r2 = "Posisi sebagai penantang dengan valuasi berbeda."

            st.write(f"**Pilihan #1: {p1}** - {r1}")
            st.write(f"**Pilihan #2: {p2}** - {r2}")

            st.markdown("---")
            st.subheader(f"Saham mana yang paling worth it untuk dibeli SEKARANG?")
            
            # Logika "Worth It" (Valuasi + Trend)
            if get_tech_status(h1) == "Bullish 🐂" and i1.get('trailingPE', 99) < 20:
                best = tk1
                reason = f"{tk1} sedang dalam fase Bullish dengan valuasi PER yang masih masuk akal."
            elif get_tech_status(h2) == "Bullish 🐂" and i2.get('trailingPE', 99) < 20:
                best = tk2
                reason = f"{tk2} memiliki momentum teknikal kuat didukung fundamental solid."
            else:
                best = p1
                reason = f"{p1} secara keseluruhan memiliki skor kualitas (ROE & Margin) terbaik."

            st.success(f"**JAWABAN:** {best}. **ALASAN:** {reason}")

            # --- TRADING PLAN (DAY TRADE) DENGAN KONTRAS WARNA ---
            def render_trading_plan(ticker, df):
                curr = df['Close'].iloc[-1]
                # Proksi VWAP harian sederhana menggunakan Typical Price
                vwap = (df['High'].iloc[-1] + df['Low'].iloc[-1] + df['Close'].iloc[-1]) / 3
                
                # Kalkulasi Entry Bawah (Maksimal turun 1.5% atau VWAP, ambil yang tertinggi)
                batas_bawah = curr * 0.985
                entry_bawah = max(batas_bawah, vwap)
                
                # Kalkulasi Harga SL & TP berdasarkan Entry Bawah
                harga_sl = entry_bawah * 0.97        # Turun 3%
                harga_tp_bawah = entry_bawah * 1.045 # Naik 4.5%
                harga_tp_atas = entry_bawah * 1.05   # Naik 5%
                
                # Menggunakan HTML/CSS untuk memaksakan background biru tua dan font putih
                st.markdown(f"""
                <div style="background-color: #0c2b4b; padding: 15px; border-radius: 8px; color: #ffffff; margin-bottom: 15px;">
                    <h4 style="color: #ffffff; margin-top: 0;">🎯 Trading Plan {ticker}</h4>
                    <ul style="color: #ffffff; margin-bottom: 0;">
                        <li><b>Harga Saat Ini:</b> Rp {curr:,.0f}</li>
                        <li><b>Rentang Entry (Support Dinamis):</b> dengan Entry Bawah di kisaran <b>Rp {entry_bawah:,.0f}</b> <i>(Maksimal turun 1.5% dari harga saat ini atau di garis VWAP, ambil mana yang lebih tinggi agar tidak menawar terlalu bawah).</i></li>
                        <li><b>SL:</b> <b>Rp {harga_sl:,.0f}</b> <i>(Maksimal turun 3% dari harga beli).</i></li>
                        <li><b>Target (TP):</b> <b>Rp {harga_tp_bawah:,.0f} - Rp {harga_tp_atas:,.0f}</b> <i>(RRR 1:1.5 / Profit sekitar 4.5% - 5%).</i></li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)

            # Menentukan data history untuk saham rekomendasi dan alternatif
            best_history = h1 if best == tk1 else h2
            second_ticker = tk2 if best == tk1 else tk1
            second_history = h2 if best == tk1 else h1

            st.markdown("<br>", unsafe_allow_html=True)
            st.write(f"Untuk saham **{best}** yang disarankan di atas, berikut adalah Trading Plan untuk mode Day Trade:")
            render_trading_plan(best, best_history)

            st.write(f"Bila Anda juga tetap mempertimbangkan saham yang kedua (**{second_ticker}**), maka berikut trading plan untuk mode Day Trading:")
            render_trading_plan(second_ticker, second_history)

            # --- PEMBUATAN PDF & TOMBOL DOWNLOAD ---
            pdf_data = {
                'tk1': tk1,
                'tk2': tk2,
                'comparison_data': comparison_data,
                'p1': p1,
                'p2': p2,
                'r1': r1,
                'r2': r2,
                'best': best,
                'reason': reason
            }
            pdf_bytes = generate_pdf_fpdf(pdf_data)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if pdf_bytes:
                st.download_button(
                    label="📄 Unduh Laporan Analisa Perbandingan Saham Pro (PDF)",
                    data=pdf_bytes,
                    file_name=f"ExpertStockPro_Perbandingan_{tk1}_vs_{tk2}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            # --- PERNYATAAN DISCLAIMER ---
            st.markdown("<br>", unsafe_allow_html=True)
            st.divider()
            st.caption(f"⚠️ **DISCLAIMER:** Laporan analisa ini dihasilkan secara otomatis menggunakan perhitungan algoritma indikator teknikal dan fundamental. Seluruh informasi yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi tanggung jawab pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik dan *Do Your Own Research* (DYOR) dan pertimbangkan profil risiko sebelum mengambil keputusan di pasar modal.")
