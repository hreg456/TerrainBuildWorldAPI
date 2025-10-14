from flask import Flask, request, jsonify, send_file
import requests
from io import BytesIO
from cachetools import TTLCache
import math
from PIL import Image
import numpy as np

app = Flask(__name__)

# Cache for tiles
tile_cache = TTLCache(maxsize=100, ttl=300)  # 5 min

@app.route('/')
def home():
    return jsonify({"status": "online"})

# -----------------------------
# OLD IMAGE TILE (PNG) ENDPOINT
# -----------------------------
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
        n = 2.0 ** z

        lon_min = x / n * 360.0 - 180.0
        lon_max = (x + 1) / n * 360.0 - 180.0
        lat_min_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
        lat_max_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_min = math.degrees(lat_min_rad)
        lat_max = math.degrees(lat_max_rad)

        bbox = f"{lat_min},{lon_min},{lat_max},{lon_max}"

        # Use NASA Blue Marble (satellite)
        wms_url = (
            "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?"
            f"SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
            f"&LAYERS=BlueMarble_ShadedRelief_Bathymetry"
            f"&CRS=EPSG:4326"
            f"&BBOX={bbox}"
            f"&WIDTH=256&HEIGHT=256&FORMAT=image/png"
        )

        if wms_url in tile_cache:
            tile_bytes = tile_cache[wms_url]
            return send_file(BytesIO(tile_bytes), mimetype="image/png")

        res = requests.get(wms_url, timeout=10)
        if res.status_code == 200:
            tile_cache[wms_url] = res.content
            return send_file(BytesIO(res.content), mimetype="image/png")
        else:
            return jsonify({"error": f"WMS failed: {res.status_code}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------
# NEW JSON TILE ENDPOINT FOR ROBLOX
# -----------------------------
@app.route('/tilejson')
def get_tile_json():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    zoom = request.args.get("zoom", default=14, type=int)

    if lat is None or lon is None:
        return jsonify({"error": "Missing lat/lon"}), 400

    try:
        # Convert lat/lon to tile x/y (Google-style)
        n = 2 ** zoom
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n)

        # Build bbox for WMS query
        lon_min = x / n * 360.0 - 180.0
        lon_max = (x + 1) / n * 360.0 - 180.0
        lat_min_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
        lat_max_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_min = math.degrees(lat_min_rad)
        lat_max = math.degrees(lat_max_rad)

        bbox = f"{lat_min},{lon_min},{lat_max},{lon_max}"

        # Satellite source (Blue Marble)
        wms_url = (
            "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?"
            f"SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
            f"&LAYERS=BlueMarble_ShadedRelief_Bathymetry"
            f"&CRS=EPSG:4326"
            f"&BBOX={bbox}"
            f"&WIDTH=64&HEIGHT=64&FORMAT=image/png"
        )

        if wms_url in tile_cache:
            img_data = tile_cache[wms_url]
        else:
            res = requests.get(wms_url, timeout=10)
            if res.status_code != 200:
                return jsonify({"error": f"Tile fetch failed: {res.status_code}"}), 500
            img_data = res.content
            tile_cache[wms_url] = img_data

        # Convert image to RGB array
        img = Image.open(BytesIO(img_data)).convert("RGB")
        arr = np.array(img)
        # Convert NumPy array -> nested Python lists (64x64x3)
        rgb_list = arr.tolist()

        return jsonify({
            "heightmap": rgb_list,
            "source": "NASA Blue Marble",
            "resolution": [len(arr), len(arr[0])]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
