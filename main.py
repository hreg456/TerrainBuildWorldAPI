from flask import Flask, request, jsonify, Response
import requests
from io import BytesIO
from cachetools import TTLCache
import math

app = Flask(__name__)

# === CACHE SETTINGS ===
tile_cache = TTLCache(maxsize=200, ttl=600)  # cache 200 tiles for 10 min
elev_cache = TTLCache(maxsize=500, ttl=300)  # cache elevation for 5 min

# === CONFIG ===
GPXZ_KEY = "ak_Ge4wEM8B_GepEI242D3wy9Mxd"  # replace with your GPXZ key

# === ROUTES ===
@app.route('/')
def home():
    return jsonify({"status": "on"})

@app.route('/tile')
def get_tile():
    z = request.args.get('z')
    x = request.args.get('x')
    y = request.args.get('y')

    if not all([z, x, y]):
        return jsonify({"error": "Missing parameters"}), 400

    try:
        z = int(z)
        x = int(x)
        y = int(y)

        # GPXZ tile URL
        tile_url = f"https://tiles.gpxz.io/satellite/{z}/{x}/{y}.png?key={GPXZ_KEY}"

        # Check cache first
        if tile_url in tile_cache:
            return Response(tile_cache[tile_url], content_type="image/png")

        # Fetch tile
        res = requests.get(tile_url, timeout=10)
        if res.status_code == 200:
            tile_cache[tile_url] = res.content
            return Response(res.content, content_type="image/png")
        else:
            return jsonify({"error": f"Tile fetch failed: {res.status_code}"}), res.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/elevation')
def get_elevation():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    if not all([lat, lon]):
        return jsonify({"error": "Missing lat or lon"}), 400

    key = f"{lat}_{lon}"
    if key in elev_cache:
        return jsonify({"lat": lat, "lon": lon, "elevation": elev_cache[key]})

    try:
        # Using free OpenTopoData API for elevation
        r = requests.get(f"https://api.opentopodata.org/v1/test-dataset?locations={lat},{lon}", timeout=5)
        data = r.json()
        if "results" in data and len(data["results"]) > 0:
            elevation = data["results"][0]["elevation"]
            elev_cache[key] = elevation
            return jsonify({"lat": lat, "lon": lon, "elevation": elevation})
        else:
            return jsonify({"error": "No elevation data"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === MAIN ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
