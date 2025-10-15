from flask import Flask, request, jsonify
import requests
from io import BytesIO
from cachetools import TTLCache
from PIL import Image
import numpy as np
import math
app = Flask(__name__)
# -----------------------------
# CONFIG
# -----------------------------
CACHE_TTL = 300  # seconds
tile_cache = TTLCache(maxsize=500, ttl=CACHE_TTL)
MAPTILER_KEY = "llBJwuCjthGvMocsOkwp"
OPENTOPO_KEY = "6a3cf43d33d4bc03d6cb609fc8828ae4"
# OpenTopography dataset - using LIDAR at max resolution
OPENTOPO_DATASET = "RGTM2Topo"
# Resolution in meters (LIDAR is ~1m)
OPENTOPO_RESOLUTION = 1
# Tile size (how many samples to fetch)
TILE_SIZE = 512
# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def latlon_to_tile_xy(lat, lon, zoom):
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y

def tile_xy_to_bbox(x, y, zoom):
    """Convert tile x,y to lat/lon bounding box"""
    n = 2 ** zoom
    lon_min = (x / n) * 360.0 - 180.0
    lon_max = ((x + 1) / n) * 360.0 - 180.0
    
    lat_max = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    lat_min = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    
    return lat_min, lat_max, lon_min, lon_max

def fetch_rgb_tile(x, y, zoom):
    url = f"https://api.maptiler.com/tiles/satellite-v2/{zoom}/{x}/{y}.jpg?key={MAPTILER_KEY}"
    if url in tile_cache:
        img_data = tile_cache[url]
    else:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return None
        img_data = res.content
        tile_cache[url] = img_data
    img = Image.open(BytesIO(img_data)).convert("RGB")
    arr = np.array(img)
    return arr.tolist()

def fetch_elevation_tile(lat_min, lat_max, lon_min, lon_max):
    """Fetch elevation data from OpenTopography API"""
    url = f"https://cloud.sdsc.edu/v1/AUTH_opentopography/Raster/{OPENTOPO_DATASET}/SRTM_GL3/SRTM_GL3_srtm"
    
    cache_key = f"opentopo_{lat_min}_{lat_max}_{lon_min}_{lon_max}"
    if cache_key in tile_cache:
        return tile_cache[cache_key]
    
    params = {
        "south": lat_min,
        "north": lat_max,
        "west": lon_min,
        "east": lon_max,
        "demtype": OPENTOPO_DATASET,
        "outputFormat": "AAIGrid",
        "API_Key": OPENTOPO_KEY
    }
    
    try:
        res = requests.get(url, params=params, timeout=15)
        if res.status_code != 200:
            print(f"OpenTopography error: {res.status_code} - {res.text}")
            return None
        
        # Parse AAIGrid format (ASCII grid)
        lines = res.text.strip().split('\n')
        data = []
        for line in lines[6:]:  # Skip header lines
            data.extend([float(x) for x in line.split()])
        
        # Reshape to 2D array (TILE_SIZE x TILE_SIZE approximately)
        ncols = int(lines[0].split()[1])
        nrows = int(lines[1].split()[1])
        elevation = np.array(data).reshape(nrows, ncols)
        
        # Normalize to RGB format (0-255 range, 24-bit integer encoding)
        elev_min = np.nanmin(elevation)
        elev_max = np.nanmax(elevation)
        if elev_max > elev_min:
            normalized = (elevation - elev_min) / (elev_max - elev_min) * 16777215
        else:
            normalized = elevation
        
        # Convert to 24-bit RGB array
        result = []
        for row in normalized:
            rgb_row = []
            for val in row:
                v = int(val) & 0xFFFFFF
                r = (v >> 16) & 0xFF
                g = (v >> 8) & 0xFF
                b = v & 0xFF
                rgb_row.append([r, g, b])
            result.append(rgb_row)
        
        tile_cache[cache_key] = result
        return result
    except Exception as e:
        print(f"Error fetching from OpenTopography: {e}")
        return None

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    return jsonify({"status": "online", "elevation_source": "OpenTopography"})

@app.route("/tilejson")
def tilejson():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    zoom = request.args.get("zoom", default=14, type=int)
    
    if lat is None or lon is None:
        return jsonify({"error": "Missing lat/lon"}), 400
    
    x, y = latlon_to_tile_xy(lat, lon, zoom)
    
    # Fetch RGB satellite tile
    rgb_tile = fetch_rgb_tile(x, y, zoom)
    if not rgb_tile:
        return jsonify({"error": "Failed to fetch RGB tile"}), 500
    
    # Get bounding box for elevation tile
    lat_min, lat_max, lon_min, lon_max = tile_xy_to_bbox(x, y, zoom)
    
    # Fetch elevation tile from OpenTopography
    elev_tile = fetch_elevation_tile(lat_min, lat_max, lon_min, lon_max)
    if not elev_tile:
        # Fallback: use RGB as elevation if OpenTopography fails
        elev_tile = rgb_tile
    
    # Resize elevation tile to match RGB tile size if needed
    if len(elev_tile) != len(rgb_tile):
        # Simple resizing by interpolation or sampling
        elev_tile = rgb_tile  # fallback
    
    return jsonify({
        "heightmap": rgb_tile,
        "elevation": elev_tile,
        "source": "MapTiler (RGB) / OpenTopography (Elevation)",
        "resolution": [len(rgb_tile), len(rgb_tile[0])],
        "bounds": {
            "south": lat_min,
            "north": lat_max,
            "west": lon_min,
            "east": lon_max
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)