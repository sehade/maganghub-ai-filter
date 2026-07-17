import streamlit as st
import time
import pandas as pd
from playwright.sync_api import sync_playwright

# ==========================================
# KONFIGURASI URL
# ==========================================
URL_MAGANGHUB = "https://maganghub.kemnaker.go.id/magang-nasional/lowongan"
URL_AI = "https://chatgpt.com/"

st.set_page_config(page_title="Pencari Loker AI", layout="wide")

st.title("🤖 Automasi Pencari Magang & Filter AI")
st.markdown("Aplikasi ini menggunakan Playwright UI Automation untuk scraping web Kemnaker dan memfilternya via ChatGPT tanpa API Key.")

# Form Input CV
cv_default = """
Mahasiswa aktif Teknik Informatika. Memiliki pemahaman kuat dalam pengembangan sistem 
klasifikasi menggunakan model YOLOv8 dan arsitektur CNN. Berpengalaman membangun 
multi-source web scraper yang robust dengan implementasi error handling dan logging. 
Menguasai bahasa pemrograman Python dan familiar dengan automation testing.
"""
cv_input = st.text_area("Masukkan Profil / CV Kamu (Pastikan relevan dengan loker yang dicari):", value=cv_default.strip(), height=150)

# Setting Parameter
col1, col2 = st.columns(2)
with col1:
    max_loker = st.number_input("Jumlah lowongan yang ingin di-scrape", min_value=1, max_value=20, value=3)
with col2:
    login_wait = st.number_input("Jeda waktu login manual ChatGPT (detik)", min_value=10, max_value=120, value=30)

def jalankan_otomasi(cv_text, max_items, wait_time):
    hasil_akhir = []
    
    with sync_playwright() as p:
        # Setup Browser
        browser = p.chromium.launch_persistent_context(
            user_data_dir="./sesi_otomasi_browser",
            headless=False,
            args=["--start-maximized"],
            no_viewport=True
        )

        # FLOW 1: Scraping Maganghub
        st.info(f"Membuka web Maganghub Kemnaker: {URL_MAGANGHUB}")
        page_magang = browser.new_page()
        page_magang.goto(URL_MAGANGHUB, timeout=60000)
        page_magang.wait_for_load_state("networkidle")
        time.sleep(5) 

        # Ambil elemen lowongan. (Selector mungkin berubah jika UI Maganghub diupdate)
        job_elements = page_magang.query_selector_all("div.card")
        daftar_loker = []
        for card in job_elements[:max_items]:
            teks_loker = card.inner_text().strip()
            if teks_loker and len(teks_loker) > 20:
                daftar_loker.append(teks_loker)
        
        st.success(f"Berhasil mengumpulkan {len(daftar_loker)} lowongan. Beralih ke ChatGPT...")

        # FLOW 2: Interaksi UI AI (Bypass API)
        page_ai = browser.new_page()
        page_ai.goto(URL_AI, timeout=60000)
        
        # Jeda untuk memastikan sesi login aktif (verifikasi Cloudflare dll)
        warning_placeholder = st.warning(f"Menunggu {wait_time} detik. Silakan login manual ke ChatGPT di browser yang terbuka jika kamu belum login!")
        time.sleep(wait_time)
        warning_placeholder.empty()

        progress_bar = st.progress(0)
        status_text = st.empty()

        for index, loker in enumerate(daftar_loker):
            status_text.text(f"Memproses lowongan ke-{index + 1} dari {len(daftar_loker)}...")
            
            prompt = (
                f"Tindaklah sebagai AI Rekruter. Berdasarkan CV saya berikut:\n{cv_text}\n\n"
                f"Apakah deskripsi lowongan pekerjaan ini cocok untuk saya?\n{loker}\n\n"
                f"Wajib jawab dengan format baku:\nSTATUS: [COCOK / TIDAK COCOK]\nALASAN: (Berikan alasan singkat dalam 2 kalimat saja)"
            )
            
            try:
                # Mengisi textarea ChatGPT (Selector ini spesifik untuk UI ChatGPT saat ini)
                page_ai.fill("textarea#prompt-textarea", prompt)
                time.sleep(1)
                page_ai.click("button[data-testid='send-button']")
                
                # Tunggu proses generasi teks selesai (tombol kirim muncul lagi)
                page_ai.wait_for_selector("button[data-testid='send-button']", timeout=60000)
                time.sleep(3) 
                
                # Ambil balasan AI terakhir
                jawaban_elemen = page_ai.locator("div.markdown").last
                hasil_ai = jawaban_elemen.inner_text()
                
                hasil_akhir.append({
                    "Lowongan": loker[:150].replace('\n', ' ') + "...",
                    "Analisis AI": hasil_ai
                })
                
                # Jeda agar tidak terkena limit aktivitas
                time.sleep(5) 
            except Exception as e:
                st.error(f"Gagal memproses UI AI pada loker ke-{index + 1}: {e}")

            progress_bar.progress((index + 1) / len(daftar_loker))

        browser.close()
        return hasil_akhir

if st.button("Mulai Scraping & Analisis", type="primary"):
    if not cv_input:
        st.error("CV tidak boleh kosong!")
    else:
        with st.spinner("Menjalankan Playwright di background... Perhatikan jendela browser yang terbuka."):
            hasil_data = jalankan_otomasi(cv_input, max_loker, login_wait)
            
            if hasil_data:
                st.subheader("📊 Hasil Filter Lowongan")
                df = pd.DataFrame(hasil_data)
                st.dataframe(df, use_container_width=True)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Data sebagai CSV",
                    data=csv,
                    file_name='hasil_filter_loker.csv',
                    mime='text/csv',
                )
