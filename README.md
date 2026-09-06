# 🧯 EWS KARHUTLA - YAYASAN PLANET INDONESIA (YPI)
> **Early Warning System & Sistem Analisis Prioritas Operasional Penanganan Kebakaran Hutan dan Lahan di Desa Dampingan YPI Kalimantan Barat.**

[![Live WebGIS](https://img.shields.io/badge/WebGIS-Live%20Demo-004B5C?style=for-the-badge&logo=leaflet)](https://username-anda.github.io/karhutla/)
[![Auto Scraping](https://img.shields.io/badge/GitHub%20Actions-Every%203%20Hours-20B2AA?style=for-the-badge&logo=github-actions)](https://github.com/username-anda/karhutla/actions)

Sistem Informasi Geospasial Analitik ini dirancang untuk mendukung **Tim Satgas Desa Dampingan Yayasan Planet Indonesia (YPI)** dalam mengambil keputusan penanganan Karhutla secara cepat, tepat sasaran, dan efisien di tengah keterbatasan tenaga serta peralatan pemadaman di lapangan.

---

## 📋 Daftar Isi
1. [Tentang Sistem](#-tentang-sistem)
2. [Fitur Utama](#-fitur-utama)
3. [Alur Analisis & Matriks Prioritas](#-alur-analisis--matriks-prioritas)
4. [Sumber Data Terintegrasi](#-sumber-data-terintegrasi)
5. [Arsitektur & Otomasi Sistem](#-arsitektur--otomasi-sistem)
6. [Panduan Penggunaan WebGIS](#-panduan-penggunaan-webgis)
7. [Struktur Repositori](#-struktur-repositori)
8. [Kontak & Pengembang](#-kontak--pengembang)

---

## 🎯 Tentang Sistem

Sistem EWS Karhutla secara otomatis menarik data pantauan satelit **SiPongi (Kementerian LHK)** setiap 3 jam sekali, lalu menganalisis posisi titik panas (*hotspot*) secara spasial terhadap batas administrasi desa dampingan, area penyangga (*ring buffer* 1.000m), dan kawasan ekosistem kritis (gambut, hutan, dan konservasi).

> ⚠️ **Catatan Penting:**  
> **Hotspot (Titik Panas) TIDAK SAMA dengan Titik Api.** Hotspot adalah indikasi anomali suhu permukaan bumi yang terekam satelit. Oleh karena itu, data dilengkapi dengan *Confidence Level* (Tingkat Kepercayaan) untuk menyaring potensi *false alarm*.

---

## ✨ Fitur Utama

- 🔄 **Live Monitoring Otomatis:** Data diperbarui setiap 3 jam sekali secara otomatis via GitHub Actions tanpa perlu server berbayar.
- 🎯 **Matriks Prioritas Operasional:** Otomatisasi pengelompokan hotspot dari Prioritas 1 (Tinggi) hingga Prioritas 4 (Waspada).
- 🖨️ **Modul Cetak Peta A4:** Fitur cetak layout peta standar kartografi otomatis lengkap dengan judul, skala, legenda, dan koordinat.
- 📏 **Alat Ukur Spasial (Measure Tool):** Mengukur jarak dari pemukiman ke titik api dan mengestimasi luas area terbakar secara presisi.
- 📍 **GPS Tracking (Deteksi Lokasi):** Membantu tim Satgas mengetahui posisi koordinat mereka di lapangan secara langsung dari HP.
- 📊 **Download Data Tabular (.CSV):** Rekapitulasi data hotspot historis dan harian yang siap diunduh untuk analisis lanjutan.

---

## 📐 Alur Analisis & Matriks Prioritas

Analisis tumpang susun (*spatial overlay*) dijalankan menggunakan algoritma Python (`GeoPandas`) dengan matriks keputusan sebagai berikut:

| Tingkat Prioritas | Confidence | Lokasi Hotspot | Ekosistem / Tutupan Lahan | Rekomendasi Tindakan Satgas |
| :--- | :---: | :--- | :--- | :--- |
| **Prioritas 1 (Tinggi)** | High / Medium | **Di Dalam** Desa | Gambut / Hutan / Konservasi | **Segera Padamkan.** Risiko pemadaman sulit & penyebaran masif. |
| **Prioritas 2 (Sedang)** | High / Medium | **Di Dalam** Desa | Area Penggunaan Lain (APL) / Mineral | **Tangani Segera.** Mencegah api meluas ke ekosistem kritis/pemukiman. |
| **Prioritas 3 (Rendah)** | High / Medium | **Di Luar** Desa (*Buffer* <1000m) | Semua Jenis Kawasan | **Siagakan Tim & Alat.** Api berada tepat di batas luar desa. |
| **Prioritas 4 (Waspada)** | Low (Rendah) | Dalam Desa / *Buffer* <1000m | Semua Jenis Kawasan | **Pantau via Satelit/Radio.** Indikasi *false alarm* atau api sangat kecil. |
| **Luar Pantauan** | Semua Level | **> 1.000 meter** dari Desa | Semua Jenis Kawasan | Diabaikan dalam target operasi utama Satgas Desa YPI. |

---

## 📚 Sumber Data Terintegrasi

| Jenis Data | Sumber Data | Keterangan / Lisensi |
| :--- | :--- | :--- |
| **Hotspot Satelit** | SiPongi KLHK (NASA-MODIS, SNPP, NOAA20) | Di-scrape realtime via API |
| **Batas Administrasi Desa** | BATAS WILAYAH (TASWIL) 2023 - BIG | Batas Desa Dampingan YPI |
| **Peta Gambut & Tutupan Lahan** | KLHK (2024) & ESA WorldCover (2021) | Peta Ekosistem Gambut & Lahan |
| **Kawasan Hutan & Konservasi** | SK.733/Menhut-II/2014 | Kawasan Hutan Kalimantan Barat |

---

## ⚙️ Arsitektur & Otomasi Sistem

Sistem ini berjalan 100% secara **serverless** dan gratis memanfaatkan alur kerja **GitHub Actions** dan **GitHub Pages**:

```mermaid
graph LR
    A[Satelit SiPongi KLHK] -->|1. Scrape API Setiap 3 Jam| B[GitHub Actions / main.py]
    C[Shapefile Desa & Kawasan] -->|2. Spatial Join & Buffer| B
    B -->|3. Generate Output| D[peta.html]
    B -->|3. Generate Output| E[stats.json]
    B -->|3. Generate Output| F[CSV Data /data/]
    D -->|4. Display| G[WebGIS GitHub Pages]
    E -->|4. Update UI Dashboard| G



⏰ Jadwal Eksekusi Otomatis (WIB):
Otomasi berjalan rutin pada jam: 01:00, 04:00, 07:00, 10:00, 13:00, 16:00, 19:00, dan 22:00 WIB.

🚀 Panduan Penggunaan WebGIS
1. Akses Dashboard: Buka link WebGIS publik pada browser HP atau laptop.
2. Pahami Informasi Awal: Tinjau Pop-up petunjuk operasional, centang persetujuan, lalu klik "Oke, Saya Paham".
3. Pantau Statistik Sidebar: Lihat rekapitulasi jumlah titik api per tingkat prioritas dan stempel waktu Update Terakhir.
4. Interaksi Peta:
Klik Titik Hotspot: Untuk menampilkan popup detail koordinat (X,Y), desa, sumber satelit, serta status kawasan.
Gunakan Tool Ukur (Kanan Atas): Untuk menghitung jarak tim ke lokasi atau menghitung luas area terbakar.
Tombol Cetak PDF A4: Pilih fokus desa pada dropdown di kiri atas, lalu klik Cetak PDF (A4) untuk mencetak peta lapangan.


📁 Struktur Repositori
karhutla/
├── .github/
│   └── workflows/
│       └── run_scraper.yml    # Script Otomasi GitHub Actions (3 Jam Sekali)
├── assets/
│   └── main.py                # Pipeline Utama (Scraping, Spatial Analysis, HTML Generator)
├── data/
│   ├── desa_intervensi.shp    # Boundary SHP Desa Dampingan YPI
│   ├── gambut_hutan_kk_kalbar.shp # Spatial Layer Kawasan Ekosistem
│   ├── data_hotspot_terbaru.csv # Dataset Hotspot Terbaru
│   └── YYYYMMDD_HHMM_analisis_prioritas_hotspot.csv # Arsip Historis Hotspot
├── index.html                 # Dashboard Utama WebGIS (UI & Sidebar)
├── peta.html                  # Peta Interaktif Folium (Embedded via Iframe)
├── stats.json                 # Metadata Ringkasan Statistik Realtime
└── README.md                  # Dokumentasi Sistem




Kontak & Pengembang
Pengembang: MEL Yayasan Planet Indonesia (arif@planetindonesia.org)
Web Portal: https://www.planetindonesia.org
Lokasi Fokus: Seluruh Desa Dampingan YPI, Provinsi Kalimantan Barat, Indonesia.
