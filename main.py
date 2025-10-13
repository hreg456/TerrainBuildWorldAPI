from flask import Flask, request, jsonify, send_file
import requests
from io import BytesIO
from cachetools import TTLCache
import math

app = Flask(__name__)

# Cache for tiles/elevation
tile_cache = TTLCache(maxsize=100, ttl=300)  # store up to 100 tiles for 5 min
elev_cache = TTLCache(maxsize=500, ttl=300)  # store elevations for 5 min

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
        # Convert tile x,y,z to lat/lon bounds for EPSG:4326
        z = int(z)
        x = int(x)
        y = int(y)
        n = 2.0 ** z

        lon_min = x / n * 360.0 - 180.0
        lon_max = (x + 1) / n * 360.0 - 180.0
        lat_min_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
        lat_max_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_min = math.degrees(lat_min_rad)
        lat_max = math.degrees(lat_max_rad)

        bbox = f"{lat_min},{lon_min},{lat_max},{lon_max}"

        # NASA SVS WMS URL
        wms_url = (
            "https://svs.gsfc.nasa.gov/cgi-bin/wms?"
            f"SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
            f"&LAYERS=SRTM30"  # <--- valid layer
            f"&CRS=EPSG:4326"
            f"&BBOX={bbox}"
            f"&WIDTH=256&HEIGHT=256&FORMAT=image/png"
        )

        # Check cache first
        if wms_url in tile_cache:
            tile_bytes = tile_cache[wms_url]
            return send_file(BytesIO(tile_bytes), mimetype="image/png")

        res = requests.get(wms_url, timeout=10)
        if res.status_code == 200:
            tile_cache[wms_url] = res.content
            return send_file(BytesIO(res.content), mimetype="image/png")
        else:
            return jsonify({"error": f"WMS request failed: {res.status_code}"}), 500

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)