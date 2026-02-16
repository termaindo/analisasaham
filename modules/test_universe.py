import yfinance as yf
from universe import get_all_tickers
import time

def test_connectivity():
    tickers = get_all_tickers()
    total = len(tickers)
    success = 0
    failed = []

    print(f"🚀 Memulai verifikasi {total} saham di Yahoo Finance...")
    print("-" * 50)

    for i, ticker in enumerate(tickers, 1):
        # Tambahkan suffix .JK untuk Bursa Efek Indonesia
        yf_ticker = f"{ticker}.JK"
        
        try:
            # Mengambil data harga terakhir (period 1d) untuk tes cepat
            data = yf.Ticker(yf_ticker).history(period="1d")
            
            if not data.empty:
                print(f"[{i}/{total}] ✅ {yf_ticker}: Berhasil")
                success += 1
            else:
                print(f"[{i}/{total}] ⚠️  {yf_ticker}: Data Kosong")
                failed.append(ticker)
        
        except Exception as e:
            print(f"[{i}/{total}] ❌ {yf_ticker}: Error ({str(e)})")
            failed.append(ticker)
        
        # Jeda singkat agar tidak terkena limit oleh Yahoo Finance
        time.sleep(0.1)

    print("-" * 50)
    print(f"📊 HASIL VERIFIKASI:")
    print(f"✅ Berhasil: {success}")
    print(f"❌ Gagal   : {len(failed)}")
    
    if failed:
        print(f"🔍 Cek kembali ticker ini: {', '.join(failed)}")
    else:
        print("🎉 Semua ticker dalam universe siap digunakan!")

if __name__ == "__main__":
    test_connectivity()
