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
def scrape_sipongi(provinsi_kode="11", late_hours=12):
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
        <div style="font-family: Arial, sans-serif; width: 300px;">
            <h4 style="margin:0; padding:5px; background-color:{warna}; color:{'black' if warna in ['yellow', 'white'] else 'white'}; text-align:center; border-radius:3px;">
                {prioritas}
            </h4>
            <table style="width:100%; margin-top:10px; font-size:12px; border-collapse: collapse;">
                <tr><td style="width:130px;"><b>Desa</b></td><td style="width:10px;">:</td><td>{row['Desa']}</td></tr>
                <tr><td><b>Tanggal</b></td><td>:</td><td>{tanggal}</td></tr>
                <tr><td><b>Jam</b></td><td>:</td><td>{jam}</td></tr>
                <tr><td><b>Sumber</b></td><td>:</td><td>SiPongi ({row['Satelit']})</td></tr>
                <tr><td><b>Confidence</b></td><td>:</td><td>{row['Confidence']}</td></tr>
                <tr><td><b>Hutan</b></td><td>:</td><td>{hutan_stat}</td></tr>
                <tr><td><b>Gambut</b></td><td>:</td><td>{gambut_stat}</td></tr>
                <tr><td><b>Konservasi/Lindung</b></td><td>:</td><td>{kk_stat}</td></tr>
                <tr><td><b>Latitude (Y)</b></td><td>:</td><td>{row['Latitude']:.5f}</td></tr>
                <tr><td><b>Longitude (X)</b></td><td>:</td><td>{row['Longitude']:.5f}</td></tr>
            </table>
        </div>
        """

        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=radius,
            color='black',
            weight=1,
            fill=True,
            fill_color=warna,
            fill_opacity=0.9 if prioritas.startswith("Prioritas") else 0.4,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=prioritas
        ).add_to(hotspot_group)

    hotspot_group.add_to(peta)

    legend_html = '''
    <style>
        .map-legend-box {
            position: fixed; bottom: 30px; left: 30px; z-index: 9999; 
            background-color: rgba(255, 255, 255, 0.95); border: 2px solid #333; 
            border-radius: 6px; padding: 10px; font-family: Arial, sans-serif; font-size: 11px;
            box-shadow: 0 0 10px rgba(0,0,0,0.3); width: 220px;
        }
        @media (max-width: 768px) {
            .map-legend-box {
                bottom: 20px; left: 15px; width: 165px; padding: 8px; font-size: 9px;
                background-color: rgba(255, 255, 255, 0.8);
                backdrop-filter: blur(4px);
            }
            .map-legend-box b { font-size: 10px !important; }
            .map-legend-box i { width: 8px !important; height: 8px !important; margin-right: 4px !important; }
        }
    </style>
    <div class="map-legend-box">
        <b style="color: #000;">LEGENDA PRIORITAS</b><br>
        <hr style="margin: 4px 0 6px 0; border: 0; border-top: 1px solid #666;">
        <i style="background: red; width: 10px; height: 10px; float: left; margin-right: 6px; border-radius: 50%; border: 1px solid #000;"></i> Prioritas 1 (Tinggi)<br>
        <i style="background: orange; width: 10px; height: 10px; float: left; margin-right: 6px; border-radius: 50%; border: 1px solid #000; margin-top: 3px;"></i> Prioritas 2 (Sedang)<br>
        <i style="background: yellow; width: 10px; height: 10px; float: left; margin-right: 6px; border-radius: 50%; border: 1px solid #000; margin-top: 3px;"></i> Prioritas 3 (Rendah)<br>
        <i style="background: blue; width: 10px; height: 10px; float: left; margin-right: 8px; border-radius: 50%; border: 1px solid #000; margin-top: 3px;"></i> Prioritas 4 (Waspada)<br>
        <i style="background: gray; width: 10px; height: 10px; float: left; margin-right: 6px; border-radius: 50%; border: 1px solid #000; margin-top: 3px;"></i> Luar Pantauan (>1000m)<br>
    </div>
    '''
    peta.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(position='topright', collapsed=False).add_to(peta)

    MeasureControl(
        position='topright', 
        primary_length_unit='meters', 
        secondary_length_unit='kilometers', 
        primary_area_unit='sqmeters', 
        secondary_area_unit='hectares'
    ).add_to(peta)
    
    LocateControl(
        position='topright', 
        strings={'title': 'Deteksi Lokasi Saya', 'popup': 'Lokasi Anda saat ini'}
    ).add_to(peta)
    
    zoom_js = """
    <script>
        document.addEventListener("DOMContentLoaded", function() {
            for (var key in window) {
                if (key.startsWith("map_") && window[key] instanceof L.Map) {
                    L.control.zoom({position: 'topright'}).addTo(window[key]);
                }
            }
        });
    </script>
    """
    peta.get_root().html.add_child(folium.Element(zoom_js))

    village_bounds = {}
    if not gdf_desa.empty:
        for idx, row in gdf_desa.iterrows():
            bounds = row.geometry.bounds
            v_name = str(row[desa_col])
            village_bounds[v_name] = [[bounds[1], bounds[0]], [bounds[3], bounds[2]]]

    waktu_cetak = datetime.now().strftime("%d %B %Y %H:%M WIB")

    print_module_html = f"""
    <style>
        * {{
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}

        @media screen {{
            .print-layout {{ display: none !important; }}
            
            /* Kontainer Menu Cetak Interaktif */
            #print-control-container {{
                position: absolute;
                top: 15px; 
                left: 55px; 
                z-index: 9999;
                background: white;
                border: 2px solid rgba(0,0,0,0.2);
                border-radius: 4px;
                box-shadow: 0 1px 5px rgba(0,0,0,0.4);
                font-family: Arial, sans-serif;
                overflow: hidden;
            }}
            
            /* Tombol Ikon (Selalu Tampil) */
            #print-icon {{
                display: flex;
                align-items: center;
                justify-content: center;
                width: 34px;
                height: 34px;
                cursor: pointer;
                background-color: #fff;
                font-size: 16px;
                transition: background 0.2s;
            }}
            #print-icon:hover {{ background-color: #f4f4f4; }}
            
            /* Isi Menu (Tersembunyi secara default) */
            #print-menu-content {{
                display: none;
                flex-direction: column;
                gap: 8px;
                padding: 10px;
                border-top: 1px solid #ddd;
                min-width: 220px;
                font-size: 12px;
            }}
            
            /* Class active untuk menampilkan menu */
            #print-control-container.active #print-menu-content {{
                display: flex;
            }}

            #print-menu-content select {{
                padding: 5px; font-size: 12px; border-radius: 3px; border: 1px solid #ccc; width: 100%;
            }}
            #print-menu-content button {{
                padding: 6px 10px; font-size: 12px; cursor: pointer; font-weight: bold;
                background-color: #28a745; color: white; border: none; border-radius: 3px; width: 100%;
            }}
            #print-menu-content button:hover {{ background-color: #218838; }}

            /* --- TAMPILAN MOBILE --- */
            @media (max-width: 768px) {{
                #print-control-container {{
                    top: 65px; /* Geser ke bawah tombol sidebar */
                    left: 15px; 
                }}
                #print-icon {{
                    width: 40px;
                    height: 40px;
                    border-radius: 6px;
                }}
                #print-menu-content {{
                    background: rgba(255, 255, 255, 0.95);
                    backdrop-filter: blur(4px);
                }}
            }}
        }}

        @media print {{
            @page {{ size: A4 landscape; margin: 1cm; }}
            body, html, .folium-map {{ width: 100% !important; height: 100% !important; margin: 0; padding: 0; }}
            #print-control-container, .leaflet-control-container, .map-legend-box {{ display: none !important; }}
            
            .print-layout {{ 
                display: block !important; position: fixed; z-index: 9999; 
                background: rgba(255, 255, 255, 0.95); padding: 10px 14px; 
                border: 1.5px solid #000; font-family: Arial, sans-serif; box-shadow: none; border-radius: 4px;
            }}
            .print-header {{ top: 0.5cm; right: 0.5cm; text-align: left; min-width: 280px; }}
            .print-header h2 {{ margin: 0 0 6px 0; font-size: 14px; font-weight: bold; color: #b30000; text-transform: uppercase; border-bottom: 1.5px solid #000; padding-bottom: 4px; text-align: center; }}
            .print-header table {{ width: 100%; font-size: 10px; border-collapse: collapse; color: #000; }}
            .print-header td {{ padding: 2px 0; vertical-align: top; }}
            
            .print-legend {{ bottom: 0.5cm; left: 0.5cm; min-width: 190px; }}
            .print-legend h4 {{ margin: 0 0 6px 0; font-size: 11px; font-weight: bold; text-align: center; border-bottom: 1.5px solid #000; padding-bottom: 4px; text-transform: uppercase; }}
            .print-legend ul {{ list-style: none; padding: 0; margin: 0; font-size: 10px; }}
            .print-legend li {{ margin-bottom: 5px; display: flex; align-items: center; font-weight: 500; }}
            .print-legend .dot {{ width: 12px; height: 12px; margin-right: 8px; border: 1px solid #000; display: inline-block; border-radius: 50%; flex-shrink: 0; }}
        }}
    </style>

    <div id="print-control-container" class="leaflet-control">
        <div id="print-icon" onclick="togglePrintMenu()" title="Buka Menu Cetak">🖨️</div>
        
        <div id="print-menu-content">
            <b>Fokus Cetak:</b> 
            <select id="desa-selector" onchange="zoomToSelectedDesa()">
                <option value="current">-- Cakupan Layar Saat Ini --</option>
                {''.join([f'<option value="{desa}">{desa}</option>' for desa in sorted(village_bounds.keys())])}
            </select>
            <button onclick="window.print()">Cetak PDF (A4)</button>
        </div>
    </div>

    <div class="print-layout print-header">
        <h2>Peta Prioritas Operasi Karhutla</h2>
        <table>
            <tr><td style="width: 85px;"><b>Waktu Cetak</b></td><td style="width: 10px;">:</td><td>{waktu_cetak}</td></tr>
            <tr><td><b>Sumber Data</b></td><td>:</td><td>Satgas / SiPongi Modis</td></tr>
            <tr><td><b>Sistem Proyeksi</b></td><td>:</td><td>WGS 84 (EPSG:4326)</td></tr>
        </table>
    </div>
    <div class="print-layout print-legend">
        <h4>Legenda Prioritas</h4>
        <ul>
            <li><span class="dot" style="background-color: #ff0000 !important;"></span> Prioritas 1 (Tinggi)</li>
            <li><span class="dot" style="background-color: #ffa500 !important;"></span> Prioritas 2 (Sedang)</li>
            <li><span class="dot" style="background-color: #ffff00 !important;"></span> Prioritas 3 (Rendah)</li>
            <li><span class="dot" style="background-color: #0000ff !important;"></span> Prioritas 4 (Waspada)</li>
            <li><span class="dot" style="background-color: #808080 !important;"></span> Luar Pantauan (&gt;1000m)</li>
        </ul>
    </div>

    <script>
        var villageBounds = {json.dumps(village_bounds)};
        
        function togglePrintMenu() {{
            var container = document.getElementById('print-control-container');
            container.classList.toggle('active');
        }}

        function zoomToSelectedDesa() {{
            var selectedDesa = document.getElementById('desa-selector').value;
            for (var key in window) {{
                if (key.startsWith("map_") && window[key] instanceof L.Map) {{
                    var mapInstance = window[key];
                    if (selectedDesa !== "current" && villageBounds[selectedDesa]) {{
                        mapInstance.fitBounds(villageBounds[selectedDesa]);
                    }}
                    break;
                }}
            }}
        }}
    </script>
    """
    
    peta.get_root().html.add_child(folium.Element(print_module_html))

    file_peta = os.path.join(OUTPUT_DIR, 'peta.html')
    peta.save(file_peta)
    print(f"\n✅ Peta interaktif + Modul Cetak A4 berhasil dibuat: {file_peta}")

# ==============================================================================
# EKSEKUSI PIPELINE UTAMA
# ==============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("MEMULAI SISTEM ANALISIS HOTSPOT".center(60))
    print("=" * 60)
    
    df_raw_hotspot, waktu_scraping_str = scrape_sipongi(provinsi_kode="11", late_hours=12)
    hasil = analisis_prioritas(df_raw_hotspot, waktu_scraping_str)
    
    if hasil is not None:
        gdf_hs_analyzed, gdf_desa_shp, gdf_buffer_shp = hasil
        
        print("\n📊 RINGKASAN REKOMENDASI OPERASIONAL SATGAS:")
        ringkasan = gdf_hs_analyzed['Prioritas_Satgas'].value_counts().reset_index()
        ringkasan.columns = ['Prioritas', 'Jumlah Titik']
        print(ringkasan.to_string(index=False))
        
        visualisasi_peta(gdf_hs_analyzed, gdf_desa_shp, gdf_buffer_shp)
