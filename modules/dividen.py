import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from fpdf import FPDF
from datetime import datetime
import os
import base64

from utils.data_loader import (
    get_full_stock_data,
    get_liquid_stocks,
    is_ticker_liquid,
    get_ticker_row,
    hitung_div_yield_normal,
    PRE_LIQUID_PATH,
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _safe_latin1(text: str) -> str:
    """Transliterasi karakter non-latin1 agar aman untuk FPDF."""
    _MAP = {
        "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2022": "*", "\u2026": "...",
        "\u00e9": "e", "\u00e8": "e", "\u00ea": "e", "\u00e0": "a",
        "\u00e2": "a", "\u00f4": "o", "\u00fb": "u", "\u00ee": "i",
        "\u00e7": "c", "\u00fc": "u", "\u00f6": "o", "\u00e4": "a",
    }
    if not isinstance(text, str):
        text = str(text)
    result = []
    for ch in text:
        if ch in _MAP:
            result.append(_MAP[ch])
        else:
            try:
                ch.encode("latin-1")
                result.append(ch)
            except UnicodeEncodeError:
                result.append("?")
    return "".join(result)


def _get_identitas(ticker_bersih: str, liquid_df: pd.DataFrame) -> dict:
    """
    Ambil Sektor dan Syariah mengikuti fallback chain:
      1. liquid_stocks.csv
      2. pre_liquid_stocks.csv
      3. yfinance info (Sektor saja; Syariah tidak tersedia dari yfinance)
    """
    result = {"sektor": "Tidak Diketahui", "syariah": "Tidak Diketahui"}

    # Lapis 1 — liquid_stocks.csv
    if is_ticker_liquid(ticker_bersih, liquid_df):
        row = get_ticker_row(ticker_bersih, liquid_df)
        if row is not None:
            result["sektor"]  = str(row.get("Sektor", "Tidak Diketahui"))
            result["syariah"] = str(row.get("Syariah", "Tidak Diketahui"))
            return result

    # Lapis 2 — pre_liquid_stocks.csv
    try:
        df_pre = pd.read_csv(PRE_LIQUID_PATH)
        row_pre = get_ticker_row(ticker_bersih, df_pre)
        if row_pre is not None:
            result["sektor"]  = str(row_pre.get("Sektor", "Tidak Diketahui"))
            result["syariah"] = str(row_pre.get("Syariah", "Tidak Diketahui"))
            return result
    except Exception:
        pass

    # Lapis 3 — yfinance (Syariah tetap "Tidak Diketahui" karena tidak ada di yfinance)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# GENERATE PDF
# ─────────────────────────────────────────────────────────────────────────────

def generate_pdf_report(ticker, company, sector, syariah_status,
                        score, score_status, conf_label, conf_pct,
                        yield_val, payout, konsistensi, cagr,
                        eps_growth, roe, fcf, der,
                        est_dps, curr_price, sl_final, entry_price, status_final):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Header box hitam
    pdf.set_fill_color(20, 20, 20)
    pdf.rect(0, 0, 210, 25, "F")

    logo_path = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_path):
        logo_path = "../logo_expert_stock_pro.png"

    if os.path.exists(logo_path):
        pdf.set_fill_color(218, 165, 32)
        pdf.rect(10, 3, 19, 19, "F")
        pdf.image(logo_path, x=10.5, y=3.5, w=18, h=18)

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 16)
    pdf.set_xy(35, 8)
    pdf.cell(0, 10, "Expert Stock Pro - Analisa Dividen Pro", ln=True)
    pdf.set_y(28)

    pdf.set_font("Arial", "I", 10)
    pdf.set_text_color(0, 0, 255)
    pdf.cell(0, 5, "Sumber: https://s.id/pintarsaham", ln=True, align="C",
             link="https://s.id/pintarsaham")
    pdf.ln(2)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 8, _safe_latin1(f"{ticker} - {company}"), ln=True, align="C")

    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, _safe_latin1(f"Sektor: {sector} | Status: {syariah_status}"),
             ln=True, align="C")
    pdf.ln(2)

    pdf.set_font("Arial", "B", 10)
    waktu_analisa = datetime.now().strftime("%d-%m-%Y %H:%M")
    pdf.cell(0, 5, _safe_latin1(f"Analisa: {waktu_analisa} | Harga: Rp {curr_price:,.0f}"),
             ln=True, align="R")

    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
    pdf.ln(5)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, _safe_latin1(f"Skor Kelayakan Dividen: {score}/100 ({score_status})"), ln=1)
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 6, _safe_latin1(
        f"Tingkat Kepercayaan Data: {conf_label} ({conf_pct:.0f}% metrik tersedia)"), ln=1)
    pdf.ln(5)

    sections = [
        ("1. History & Pertumbuhan Dividen", [
            f"- Dividend Yield: {yield_val:.2f}%",
            f"- Payout Ratio: {payout:.1f}%",
            f"- Konsistensi: {konsistensi}/5 Tahun",
            f"- Growth (CAGR): {cagr * 100:.1f}%",
        ]),
        ("2. Kinerja Bisnis", [
            f"- EPS Growth (YoY): {eps_growth:.1f}%",
            f"- Return on Equity (ROE): {roe:.1f}%",
        ]),
        ("3. Kesehatan Finansial", [
            f"- Kualitas Kas (FCF): {'Positif (Aman)' if fcf > 0 else 'Negatif (Berisiko)'}",
            f"- Debt to Equity Ratio (DER): {der:.2f}x",
        ]),
        ("4. Proyeksi & Proteksi", [
            f"- Estimasi DPS Mendatang: Rp {est_dps:,.0f} / Lembar",
            f"- Potential Yield: {(est_dps / curr_price * 100) if curr_price > 0 else 0:.2f}%",
            f"- Stop Loss Level (Lock 8%): Rp {sl_final:,.0f}",
        ]),
        ("5. Rekomendasi", [
            f"Status: {status_final}",
            f"Harga wajar bila dividen setara deposito (5%): Rp {entry_price:,.0f}",
        ]),
    ]

    for title, lines in sections:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, title, ln=1)
        pdf.set_font("Arial", "", 11)
        for line in lines:
            pdf.cell(0, 6, _safe_latin1(line), ln=1)
        pdf.ln(3)

    pdf.ln(5)
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(100, 100, 100)
    disclaimer = (
        "DISCLAIMER: Laporan analisa ini dihasilkan secara otomatis menggunakan "
        "perhitungan algoritma indikator teknikal dan fundamental. Seluruh informasi "
        "yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk "
        "membeli/menjual saham. Keputusan investasi sepenuhnya menjadi tanggung jawab "
        "pribadi masing-masing investor. Selalu terapkan manajemen risiko yang baik "
        "dan Do Your Own Research (DYOR) dan pertimbangkan profil risiko sebelum "
        "mengambil keputusan di pasar modal."
    )
    pdf.multi_cell(0, 5, _safe_latin1(disclaimer))

    try:
        out = pdf.output(dest="S")
        return out.encode("latin-1") if isinstance(out, str) else bytes(out)
    except Exception:
        return bytes(pdf.output())


# ─────────────────────────────────────────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def run_dividen():
    # Logo & judul
    logo_file = "logo_expert_stock_pro.png"
    if not os.path.exists(logo_file):
        logo_file = "../logo_expert_stock_pro.png"

    if os.path.exists(logo_file):
        with open(logo_file, "rb") as f:
            encoded_img = base64.b64encode(f.read()).decode()
        st.markdown(
            f'<div style="display:flex;justify-content:center;margin-bottom:10px;">'
            f'<img src="data:image/png;base64,{encoded_img}" width="150"></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<h1 style='text-align:center;'>💰 Analisa Dividen Pro</h1>",
                unsafe_allow_html=True)
    st.markdown("---")

    col_inp, _ = st.columns([1, 2])
    with col_inp:
        ticker_input = st.text_input("Kode Saham (Contoh: ADRO):", value="ADRO").upper()

    ticker_bersih = ticker_input.strip().upper().replace(".JK", "")
    ticker_jk     = ticker_bersih + ".JK"

    if not st.button(f"Jalankan Analisa Lengkap {ticker_bersih}"):
        return

    with st.spinner(f"Mengambil data untuk {ticker_jk}..."):
        # ── Fallback chain data identitas ────────────────────────────────────
        liquid_df = get_liquid_stocks()
        identitas = _get_identitas(ticker_bersih, liquid_df)
        sector    = identitas["sektor"]
        syariah   = identitas["syariah"]          # "Ya" / "Tidak" / "Tidak Diketahui"

        if not is_ticker_liquid(ticker_bersih, liquid_df):
            st.info(
                "ℹ️ Analisa menggunakan data langsung dari yfinance."
            )

        # ── Data live dari yfinance ──────────────────────────────────────────
        data    = get_full_stock_data(ticker_jk)
        info    = data.get("info", {})
        divs    = data.get("dividends")
        history = data.get("history")

    if divs is None or len(divs) == 0:
        st.error("Data dividen tidak ditemukan atau emiten tidak membagikan dividen.")
        return

    if history is None or history.empty:
        st.warning("⚠️ Data harga tidak tersedia untuk ticker ini. Coba ticker lain.")
        return

    # ── Harga sekarang ───────────────────────────────────────────────────────
    curr_price = info.get("currentPrice")
    if not curr_price:
        curr_price = history["Close"].iloc[-1]
    curr_price = float(curr_price or 0)

    # ── Metrik fundamental ───────────────────────────────────────────────────
    yield_val    = hitung_div_yield_normal(info)
    payout       = (info.get("payoutRatio") or 0) * 100
    fcf          = info.get("freeCashflow") or 0
    roe          = (info.get("returnOnEquity") or 0) * 100
    der          = (info.get("debtToEquity") or 0) / 100
    eps_growth   = (info.get("earningsGrowth") or 0) * 100
    trailing_eps = info.get("trailingEps") or 0

    # ── Histori dividen tahunan ──────────────────────────────────────────────
    df_div        = divs.to_frame(name="Dividends")
    df_div.index  = pd.to_datetime(df_div.index).tz_localize(None)
    df_div_annual = df_div.resample("YE").sum().tail(5)
    konsistensi   = len(df_div_annual)
    cagr = 0.0
    if konsistensi >= 2:
        awal, akhir = (df_div_annual["Dividends"].iloc[0],
                       df_div_annual["Dividends"].iloc[-1])
        if awal > 0:
            cagr = ((akhir / awal) ** (1 / (konsistensi - 1))) - 1

    # ── Scoring ──────────────────────────────────────────────────────────────
    total_score = 0
    if fcf > 0:                                    total_score += 20
    if konsistensi == 5 and cagr > 0.05:           total_score += 20
    elif konsistensi == 5 and cagr > 0:            total_score += 15
    elif yield_val >= 8:                           total_score += 20
    elif yield_val >= 6:                           total_score += 15
    if der < 1.0:                                  total_score += 15
    if 30 <= payout <= 70:                         total_score += 15
    if roe > 15 and eps_growth > 0:                total_score += 10

    score_status = (
        "Sangat Layak"        if total_score >= 80 else
        "Layak dengan Pantauan" if total_score >= 60 else
        "Risiko Tinggi"
    )

    # ── Konfidensi data ──────────────────────────────────────────────────────
    metrik_kunci = ["payoutRatio", "returnOnEquity", "freeCashflow",
                    "debtToEquity", "earningsGrowth", "trailingEps"]
    tersedia          = sum(1 for m in metrik_kunci if info.get(m) is not None)
    konfidensi_persen = (tersedia / len(metrik_kunci)) * 100
    conf_color        = "🟢" if konfidensi_persen >= 100 else "🟡" if konfidensi_persen >= 70 else "🔴"
    conf_label        = "Tinggi" if konfidensi_persen >= 100 else "Sedang" if konfidensi_persen >= 70 else "Rendah"

    # ── Label Syariah untuk tampilan ─────────────────────────────────────────
    syariah_label = (
        "✅ Syariah"      if syariah == "Ya"   else
        "❌ Non-Syariah"  if syariah == "Tidak" else
        "❓ Status tidak diketahui"
    )
    company_name = info.get("longName") or ticker_bersih

    # ── Header summary ───────────────────────────────────────────────────────
    st.markdown(f"""
        <div style="text-align:center;padding:20px;background-color:#1E1E1E;
                    border-radius:10px;border:1px solid #333;">
            <h1 style="color:#2ECC71;margin-bottom:5px;font-size:2.5em;">
                🏢 {ticker_bersih} - {company_name}
            </h1>
            <p style="color:#A0A0A0;font-size:1.2em;margin-bottom:15px;">
                Sektor: {sector} | <span style="color:white;">{syariah_label}</span>
            </p>
            <h3 style="color:white;margin-bottom:5px;">🏆 SKOR KELAYAKAN DIVIDEN</h3>
            <div style="background-color:#333;border-radius:5px;height:10px;margin-bottom:10px;">
                <div style="background-color:#2ECC71;width:{total_score}%;
                            height:10px;border-radius:5px;"></div>
            </div>
            <div style="background-color:#2E3317;padding:10px;border-radius:5px;
                        border-left:5px solid #2ECC71;margin-bottom:10px;">
                <p style="color:#D4E157;margin:0;font-weight:bold;font-size:1.1em;">
                    Skor: {total_score}/100 — {score_status}
                </p>
            </div>
            <p style="color:#A0A0A0;font-size:0.9em;margin:0;">
                Tingkat Kepercayaan Data: {conf_color} {conf_label}
                ({konfidensi_persen:.0f}% metrik tersedia)
            </p>
        </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Seksi 1: History & Pertumbuhan Dividen ───────────────────────────────
    st.header("1. History & Pertumbuhan Dividen")
    st.bar_chart(df_div_annual["Dividends"])
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Dividend Yield", f"{yield_val:.2f}%")
    m2.metric("Payout Ratio",   f"{payout:.1f}%")
    m3.metric("Konsistensi",    f"{konsistensi}/5 Thn")
    m4.metric("Growth (CAGR)", f"{cagr * 100:.1f}%")

    # ── Seksi 2: Kinerja Bisnis ──────────────────────────────────────────────
    st.header("2. Kinerja Bisnis")
    col_biz1, col_biz2 = st.columns(2)
    with col_biz1:
        st.write("**EPS Growth (YoY):**")
        st.success(f"📈 {eps_growth:.1f}%") if eps_growth > 0 else st.error(f"📉 {eps_growth:.1f}%")
    with col_biz2:
        st.write("**Return on Equity (ROE):**")
        if roe > 15:   st.success(f"💎 {roe:.1f}%")
        elif roe > 8:  st.info(f"👍 {roe:.1f}%")
        else:          st.warning(f"⚠️ {roe:.1f}%")

    # ── Seksi 3: Kesehatan Finansial ─────────────────────────────────────────
    st.header("3. Kesehatan Finansial")
    col_fin1, col_fin2 = st.columns(2)
    with col_fin1:
        st.write("**Kualitas Kas (FCF):**")
        st.success("✅ Positif (Dana Aman)") if fcf > 0 else st.error("❌ Negatif (Risiko Kas)")
    with col_fin2:
        st.write("**Debt to Equity Ratio (DER):**")
        st.success(f"✅ {der:.2f}x") if der < 1.0 else st.warning(f"⚠️ {der:.2f}x")

    # ── Seksi 4: Proyeksi & Proteksi ─────────────────────────────────────────
    st.header("4. Proyeksi & Proteksi")
    est_dps = trailing_eps * (payout / 100)

    try:
        atr = float((history["High"] - history["Low"]).tail(14).mean())
        if np.isnan(atr):
            atr = 0.0
    except Exception:
        atr = 0.0

    sl_final = max(curr_price - (1.5 * atr), curr_price * 0.92)

    p1, p2 = st.columns(2)
    with p1:
        st.info(f"**Estimasi DPS Mendatang:**\n\nRp {est_dps:,.0f} / Lembar")
        pot_yield = (est_dps / curr_price * 100) if curr_price > 0 else 0.0
        st.write(f"**Potential Yield:** {pot_yield:.2f}%")
    with p2:
        st.error(f"**Stop Loss Level (Lock 8%):**\n\nRp {sl_final:,.0f}")

    # ── Seksi 5: Rekomendasi ─────────────────────────────────────────────────
    st.header("5. Rekomendasi")
    entry_price = (est_dps / 0.05) if est_dps > 0 else 0.0
    status_final = (
        "SANGAT LAYAK" if (curr_price < entry_price and total_score >= 80)
        else "TUNGGU KOREKSI"
    )
    st.subheader(f"Status: {status_final}")
    st.write(f"**Harga wajar (Yield 5%):** Rp {entry_price:,.0f}")
    st.write(f"**Harga Saat Ini:** Rp {curr_price:,.0f}")

    # ── Export PDF ───────────────────────────────────────────────────────────
    st.markdown("---")
    pdf_bytes = generate_pdf_report(
        ticker_bersih, company_name, sector, syariah,
        total_score, score_status, conf_label, konfidensi_persen,
        yield_val, payout, konsistensi, cagr,
        eps_growth, roe, fcf, der,
        est_dps, curr_price, sl_final, entry_price, status_final,
    )
    st.download_button(
        label="📄 Simpan sebagai PDF",
        data=pdf_bytes,
        file_name=f"ExpertStockPro_Dividen_{ticker_bersih}_{datetime.now().strftime('%Y%m%d')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    st.markdown("---")
    st.caption(
        "⚠️ **DISCLAIMER:** Laporan analisa ini dihasilkan secara otomatis menggunakan "
        "perhitungan algoritma indikator teknikal dan fundamental. Seluruh informasi "
        "yang disajikan bukan merupakan ajakan, rekomendasi pasti, atau paksaan untuk "
        "membeli/menjual saham. Keputusan investasi dan trading sepenuhnya menjadi "
        "tanggung jawab pribadi masing-masing investor. Selalu terapkan manajemen "
        "risiko yang baik dan *Do Your Own Research* (DYOR) dan pertimbangkan profil "
        "risiko sebelum mengambil keputusan di pasar modal."
    )
