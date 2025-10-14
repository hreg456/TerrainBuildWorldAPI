from flask import Flask, request, jsonify
import requests
from cachetools import TTLCache

app = Flask(__name__)
tile_cache = TTLCache(maxsize=100, ttl=300)

GPXZ_TOKEN = "ak_Ge4wEM8B_GepEI242D3wy9Mxd"

@app.route("/tile")
def tile():
    z = request.args.get("z")
    x = request.args.get("x")
    y = request.args.get("y")
    if not all([z, x, y]):
        return jsonify({"error":"Missing parameters"}), 400

    url = f"https://api.gpxz.io/tiles/{z}/{x}/{y}.png"
    headers = {"Authorization": f"Bearer {GPXZ_TOKEN}"}

    if url in tile_cache:
        return tile_cache[url]

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()

        # Convert PNG to RGB array for Roblox
        from PIL import Image
        from io import BytesIO

        img = Image.open(BytesIO(r.content)).convert("RGB")
        data = [[{"r": p[0], "g": p[1], "b": p[2]} for p in list(img.getdata())[i*img.width:(i+1)*img.width]] for i in range(img.height)]

        tile_cache[url] = jsonify(data)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
