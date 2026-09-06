import geopandas as gpd
import os

input_file = r"C:\xampp\htdocs\karhutla\data\gambut_hutan_kk_kalbar.shp"
output_file = r"C:\xampp\htdocs\karhutla\data\gambut_hutan_kk_kalbar.shp"

print("Sedang menyederhanakan geometri SHP...")
gdf = gpd.read_file(input_file)

# Sederhanakan batas poligon (presisi 0.0001 derajat ~10 meter di lapangan)
gdf['geometry'] = gdf.geometry.simplify(0.0001, preserve_topology=True)

# Simpan kembali
gdf.to_file(output_file)
print("Selesai! Ukuran file sekarang jauh lebih kecil.")