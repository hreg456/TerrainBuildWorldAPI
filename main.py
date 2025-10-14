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
CACHE_TTL = 300  # 5 min
tile_cache = TTLCache(maxsize=500, ttl=CACHE_TTL)

MAPTILER_KEY = "llBJwuCjthGvMocsOkwp"
GPXZ_KEY = "ak_Ge4wEM8B_GepEI242D3wy9Mxd"

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def latlon_to_tile_xy(lat, lon, zoom):
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y

def tile_xy_to_bbox(x, y, zoom):
    n = 2 ** zoom
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0
    lat_min_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
    lat_max_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_min = math.degrees(lat_min_rad)
    lat_max = math.degrees(lat_max_rad)
    return lat_min, lon_min, lat_max, lon_max

def fetch_rgb_tile(lat, lon, zoom):
    url = f"https://api.maptiler.com/tiles/terrain-rgb/14/{lat}/{lon}.png?key={MAPTILER_KEY}"
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

def fetch_elevation(lat, lon, zoom):
    url = f"https://api.gpxz.io/v1/elevation/point?lat={lat}&lon={lon}&zoom={zoom}&apikey={GPXZ_KEY}"
    if url in tile_cache:
        data = tile_cache[url]
    else:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return None
        data = res.json()
        tile_cache[url] = data
    return data.get("elevation", None)

# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    return jsonify({"status": "online"})

@app.route("/tilejson")
def tilejson():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    zoom = request.args.get("zoom", default=14, type=int)
    if None in [lat, lon]:
        return jsonify({"error": "Missing lat/lon"}), 400

    rgb_tile = fetch_rgb_tile(lat, lon, zoom)
    if rgb_tile is None:
        return jsonify({"error": "Failed to fetch RGB tile"}), 500

    return jsonify({
        "heightmap": rgb_tile,
        "source": "MapTiler Terrain-RGB",
        "resolution": [len(rgb_tile), len(rgb_tile[0])]
    })

@app.route("/elevationjson")
def elevationjson():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    zoom = request.args.get("zoom", default=14, type=int)
    if None in [lat, lon]:
        return jsonify({"error": "Missing lat/lon"}), 400

    elevation = fetch_elevation(lat, lon, zoom)
    if elevation is None:
        return jsonify({"error": "Failed to fetch elevation"}), 500

    return jsonify({
        "elevation": elevation,
        "source": "GPXZ API"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
