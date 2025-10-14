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
GPXZ_KEY = "ak_Ge4wEM8B_GepEI242D3wy9Mxd"

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def latlon_to_tile_xy(lat, lon, zoom):
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n)
    return x, y

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

def fetch_elevation_tile(lat, lon, zoom):
    url = f"https://api.gpxz.io/v1/elevation?lat={lat}&lon={lon}&zoom={zoom}&apikey={GPXZ_KEY}"
    if url in tile_cache:
        data = tile_cache[url]
    else:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return None
        data = res.json()
        tile_cache[url] = data
    return data.get("elevation", [])

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

    if lat is None or lon is None:
        return jsonify({"error": "Missing lat/lon"}), 400

    x, y = latlon_to_tile_xy(lat, lon, zoom)
    rgb_tile = fetch_rgb_tile(x, y, zoom)
    if not rgb_tile:
        return jsonify({"error": "Failed to fetch RGB tile"}), 500

    elev_tile = fetch_elevation_tile(lat, lon, zoom)
    if not elev_tile:
        elev_tile = []  # fallback if GPXZ fails

    return jsonify({
        "heightmap": rgb_tile,
        "elevation": elev_tile,
        "source": "MapTiler / GPXZ",
        "resolution": [len(rgb_tile), len(rgb_tile[0])]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
