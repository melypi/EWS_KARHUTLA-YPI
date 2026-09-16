# ==============================================================================
# SISTEM DETEKSI DAN ANALISIS PRIORITAS KARHUTLA TERINTEGRASI (XAMPP VERSION)
# DENGAN FITUR MEASURE, CUSTOM KONTROL & DUKUNGAN CETAK PDF A4
# ==============================================================================
import os
import json
import random
import requests
import pandas as pd
import geopandas as gpd
import folium
from shapely.geometry import Point
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from folium.plugins import LocateControl, MeasureControl

# ==============================================================================
# 1. SETUP LINGKUNGAN DIREKTORI LOKAL (XAMPP)
# ==============================================================================
print("1️⃣ Menyiapkan Direktori Lokal...")

ASSETS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(ASSETS_DIR)

INPUT_DIR = os.path.join(BASE_DIR, 'data')
OUTPUT_DIR = BASE_DIR

# ==============================================================================
# 2. FUNGSI SCRAPING SIPONGI (Harvesting Data)
# ==============================================================================
def scrape_sipongi(provinsi_kode="11", late_hours=48):
    # Catat tanggal dan jam tepat saat scraping dilakukan
    waktu_scraping_dt = datetime.now()
    waktu_scraping_str = waktu_scraping_dt.strftime("%Y%m%d_%H%M")
    
    print(f"\n2️⃣ Mengambil Data Hotspot SiPongi ({late_hours} Jam Terakhir) pada [{waktu_scraping_str}]...")
    API_URL = "https://opsroom.sipongidata.my.id/api/opsroom/indoHotspot"
    
    params = {
        "wilayah": "IN", "filterperiode": "false", "late": late_hours,
        "satelit[]": ["NASA-MODIS", "NASA-SNPP", "NASA-NOAA20"],
        "confidence[]": ["low", "medium", "high"],
        "provinsi": provinsi_kode, "kabkota": ""
    }

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    ]
    
    headers = {
        "Accept": "application/json", 
        "Origin": "https://sipongi.gakkum.kehutanan.go.id",
        "Referer": "https://sipongi.gakkum.kehutanan.go.id/", 
        "User-Agent": random.choice(user_agents)
    }

    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))

    try:
        response = session.get(API_URL, params=params, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        features = data.get("features", [])
        if not features:
            print("   ⚠️ Tidak ada hotspot ditemukan pada periode ini.")
            return pd.DataFrame(), waktu_scraping_str

        rows = []
        for ft in features:
            props = ft.get("properties", {})
            geom = ft.get("geometry", {})
            coords = geom.get("coordinates", [None, None])
            
            lon, lat = coords[0], coords[1]
            if lon is None or lat is None:
                continue

            conf = props.get("confidence_level") or props.get("confidence") or ""
            
            rows.append({
                "Kecamatan": props.get("kecamatan", ""),
                "Desa": props.get("desa", ""),
                "Waktu": props.get("date_hotspot", ""),
                "Satelit": props.get("satelit") or props.get("sumber") or "",
                "Confidence": str(conf).capitalize(),
                "Longitude": float(lon),
                "Latitude": float(lat)
            })
            
        df = pd.DataFrame(rows)
        print(f"   ✅ Ditemukan {len(df)} titik hotspot.")
        return df, waktu_scraping_str
    
    except Exception as e:
        print(f"   ❌ Gagal mengambil data: {e}")
        return pd.DataFrame(), waktu_scraping_str

# ==============================================================================
# 3. FUNGSI PEMROSESAN SPASIAL (SHP & Matriks Prioritas)
# ==============================================================================
def analisis_prioritas(df_hotspot, waktu_scraping_str):
    print("\n3️⃣ Memulai Analisis Spasial & Klasifikasi Prioritas...")
    
    if df_hotspot.empty:
        print("   ⚠️ Data hotspot kosong, menghentikan analisis.")
        return None

    gdf_hotspot = gpd.GeoDataFrame(
        df_hotspot, 
        geometry=gpd.points_from_xy(df_hotspot.Longitude, df_hotspot.Latitude),
        crs="EPSG:4326"
    )

    file_desa = os.path.join(INPUT_DIR, 'desa_intervensi.shp')
    file_kawasan = os.path.join(INPUT_DIR, 'gambut_hutan_kk_kalbar.shp')
    
    try:
        gdf_desa = gpd.read_file(file_desa).to_crs("EPSG:4326")
        gdf_kawasan = gpd.read_file(file_kawasan).to_crs("EPSG:4326")
    except Exception as e:
        print(f"   ❌ Gagal membaca SHP. Pastikan file SHP Anda berada di: {INPUT_DIR}")
        print(f"   Error: {e}")
        return None

    gdf_desa['geometry'] = gdf_desa.geometry.buffer(0)
    gdf_kawasan['geometry'] = gdf_kawasan.geometry.buffer(0)

    print("   ✅ Data SHP berhasil dimuat.")

    try:
        utm_crs = gdf_desa.estimate_utm_crs() 
    except Exception:
        utm_crs = "EPSG:3857"

    gdf_desa_utm = gdf_desa.to_crs(utm_crs)
    gdf_hotspot_utm = gdf_hotspot.to_crs(utm_crs)
    gdf_kawasan_utm = gdf_kawasan.to_crs(utm_crs)

    print("   Membuat Ring Buffer 1000m di luar batas desa...")
    gdf_buffer_utm = gdf_desa_utm.copy()
    gdf_buffer_utm['geometry'] = gdf_desa_utm.geometry.buffer(1000).difference(gdf_desa_utm.geometry)

    print("   Melakukan tumpang susun (overlay) spasial...")
    hs_in_desa = gpd.sjoin(gdf_hotspot_utm, gdf_desa_utm, how='left', predicate='within')
    hs_in_buffer = gpd.sjoin(gdf_hotspot_utm, gdf_buffer_utm, how='left', predicate='within')
    hs_in_kawasan = gpd.sjoin(gdf_hotspot_utm, gdf_kawasan_utm, how='left', predicate='within')

    # ==============================================================================
    # TAMBAHAN FIX: Hapus duplikat indeks akibat overlap spasial pada polygon SHP
    # ==============================================================================
    hs_in_desa = hs_in_desa[~hs_in_desa.index.duplicated(keep='first')]
    hs_in_buffer = hs_in_buffer[~hs_in_buffer.index.duplicated(keep='first')]
    hs_in_kawasan = hs_in_kawasan[~hs_in_kawasan.index.duplicated(keep='first')]
    # ==============================================================================

    gdf_hotspot['in_desa'] = ~hs_in_desa['index_right'].isna()
    gdf_hotspot['in_buffer'] = ~hs_in_buffer['index_right'].isna()
    
    hutan_val = hs_in_kawasan['hutan'].astype(str).str.lower()
    gambut_val = hs_in_kawasan['gambut'].astype(str).str.lower()
    kons_val = hs_in_kawasan['konservasi'].astype(str).str.lower()

    gdf_hotspot['is_hutan'] = hs_in_kawasan['hutan'].notna() & (~hutan_val.isin(['bukan', 'nan', 'none']))
    gdf_hotspot['is_gambut'] = hs_in_kawasan['gambut'].notna() & (~gambut_val.isin(['bukan', 'nan', 'none']))
    gdf_hotspot['is_kk'] = hs_in_kawasan['konservasi'].notna() & (~kons_val.isin(['bukan', 'nan', 'none']))
    
    gdf_hotspot['in_kawasan'] = gdf_hotspot['is_hutan'] | gdf_hotspot['is_gambut'] | gdf_hotspot['is_kk']

    print("   Menghitung klasifikasi prioritas operasi Satgas...")
    def tentukan_prioritas(row):
        conf = str(row['Confidence']).lower()
        is_high_med = conf in ['high', 'medium']
        lokasi_tercover = row['in_desa'] or row['in_buffer']

        if not lokasi_tercover:
            return "Di Luar Area Pantauan (>1000m dari Desa)"
            
        if not is_high_med: 
            return "Prioritas 4 (Waspada)"
            
        if row['in_desa']:
            if row['in_kawasan']:
                return "Prioritas 1 (Tinggi)"
            else:
                return "Prioritas 2 (Sedang)"
        elif row['in_buffer']:
            return "Prioritas 3 (Rendah)"
            
        return "Unclassified"

    gdf_hotspot['Prioritas_Satgas'] = gdf_hotspot.apply(tentukan_prioritas, axis=1)
    
    # Simpan file CSV dengan prefix tanggal & jam scraping
    file_output = os.path.join(INPUT_DIR, f'{waktu_scraping_str}_analisis_prioritas_hotspot.csv')
    df_final = pd.DataFrame(gdf_hotspot.drop(columns='geometry'))
    df_final.to_csv(file_output, index=False)

    # Simpan salinan file CSV terbaru untuk tombol download langsung di index.html
    file_latest_csv = os.path.join(INPUT_DIR, 'data_hotspot_terbaru.csv')
    df_final.to_csv(file_latest_csv, index=False)

    # Format tampilan tanggal-jam untuk UI Sidebar index.html
    try:
        waktu_display = datetime.strptime(waktu_scraping_str, "%Y%m%d_%H%M").strftime("%d %b %Y %H:%M WIB")
    except Exception:
        waktu_display = waktu_scraping_str

    # Buat file statistik JSON untuk dibaca oleh index.html
    rekap = gdf_hotspot['Prioritas_Satgas'].value_counts()
    stats_data = {
        "p1": int(rekap.get("Prioritas 1 (Tinggi)", 0)),
        "p2": int(rekap.get("Prioritas 2 (Sedang)", 0)),
        "p3": int(rekap.get("Prioritas 3 (Rendah)", 0)),
        "p4": int(rekap.get("Prioritas 4 (Waspada)", 0)),
        "luar_pantauan": int(rekap.get("Di Luar Area Pantauan (>1000m dari Desa)", 0)),
        "total": len(gdf_hotspot),
        "last_update": waktu_display
    }

    file_stats_json = os.path.join(BASE_DIR, 'stats.json')
    with open(file_stats_json, 'w', encoding='utf-8') as f:
        json.dump(stats_data, f, indent=4)

    print(f"   ✅ Analisis selesai!")
    print(f"   📁 CSV Disimpan: {file_output}")
    print(f"   📁 JSON Statistik: {file_stats_json}")
    
    return gdf_hotspot, gdf_desa, gdf_buffer_utm.to_crs("EPSG:4326")

# ==============================================================================
# 4. FUNGSI VISUALISASI PETA INTERAKTIF & MODUL CETAK
# ==============================================================================
def visualisasi_peta(gdf_hotspot, gdf_desa, gdf_buffer):
    print("\n4️⃣ Membangun Visualisasi Peta Interaktif & Modul Cetak...")
    
    if gdf_hotspot is None or gdf_hotspot.empty:
        print("Tidak ada data untuk divisualisasikan.")
        return

    centroid = gdf_desa.geometry.unary_union.centroid
    pusat_peta = [centroid.y, centroid.x]
    
    peta = folium.Map(location=pusat_peta, zoom_start=9, tiles=None, zoom_control=False)

    folium.TileLayer(
        tiles='OpenStreetMap',
        name='Open Street Map',
        overlay=False,
        control=True,
        show=False
    ).add_to(peta)

    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Satellite Hybrid',
        overlay=False,
        control=True,
        show=True
    ).add_to(peta)
    
    hs_in_desa_map = gpd.sjoin(gdf_hotspot, gdf_desa, how='inner', predicate='within')
    for prioritas_level in ["Prioritas 1 (Tinggi)", "Prioritas 2 (Sedang)", "Prioritas 3 (Rendah)", "Prioritas 4 (Waspada)"]:
        col_name = prioritas_level.split(" (")[0] 
        counts = hs_in_desa_map[hs_in_desa_map['Prioritas_Satgas'] == prioritas_level].groupby('index_right').size()
        gdf_desa[col_name] = gdf_desa.index.map(counts).fillna(0).astype(int)

    desa_col = 'desa' if 'desa' in gdf_desa.columns else gdf_desa.columns[0]

    folium.GeoJson(
        gdf_desa,
        name="Batas Desa Intervensi",
        style_function=lambda x: {'fillColor': '#00ffff', 'color': '#00ffff', 'weight': 2, 'fillOpacity': 0.15},
        tooltip=folium.GeoJsonTooltip(fields=[desa_col], aliases=['Desa:']),
        popup=folium.GeoJsonPopup(
            fields=[desa_col, 'Prioritas 1', 'Prioritas 2', 'Prioritas 3', 'Prioritas 4'],
            aliases=['Desa:', 'Prioritas 1:', 'Prioritas 2:', 'Prioritas 3:', 'Prioritas 4:']
        )
    ).add_to(peta)

    folium.GeoJson(
        gdf_buffer,
        name="Buffer 1000m (Ring Luar)",
        style_function=lambda x: {'fillColor': 'white', 'color': 'white', 'weight': 1.5, 'dashArray': '5, 5', 'fillOpacity': 0.1}
    ).add_to(peta)

    warna_prioritas = {
        "Prioritas 1 (Tinggi)": "red",        
        "Prioritas 2 (Sedang)": "orange",      
        "Prioritas 3 (Rendah)": "yellow",      
        "Prioritas 4 (Waspada)": "blue",       
        "Di Luar Area Pantauan (>1000m dari Desa)": "gray"
    }

    hotspot_group = folium.FeatureGroup(name="Hotspot Karhutla")
    
    for idx, row in gdf_hotspot.iterrows():
        prioritas = row['Prioritas_Satgas']
        warna = warna_prioritas.get(prioritas, "gray")
        radius = 8 if prioritas.startswith("Prioritas") else 2
         
        waktu_str = str(row['Waktu'])
        if " " in waktu_str and waktu_str.count(":") >= 1:
            waktu_split = waktu_str.rsplit(' ', 1)
            tanggal = waktu_split[0]
            jam = waktu_split[1] + " WIB"
        else:
            tanggal = waktu_str
            jam = "-"

        hutan_stat = 'Ya' if row.get('is_hutan', False) else 'Bukan'
        gambut_stat = 'Ya' if row.get('is_gambut', False) else 'Bukan'
        kk_stat = 'Ya' if row.get('is_kk', False) else 'Bukan'

        popup_html = f"""
