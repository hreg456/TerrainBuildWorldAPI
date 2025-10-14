from flask import Flask, request, jsonify
import requests
from io import BytesIO
from PIL import Image

app = Flask(__name__)

GPXZ_TOKEN = "ak_Ge4wEM8B_GepEI242D3wy9Mxd"
GPXZ_TILE_URL = "https://api.gpxz.io/tiles/{z}/{x}/{y}.png?access_token={token}"

@app.route("/")
def home():
    return jsonify({"status": "on"})

@app.route("/tile")
def get_tile():
    z = request.args.get("z")
    x = request.args.get("x")
    y = request.args.get("y")

    if not all([z, x, y]):
        return jsonify({"error": "Missing parameters"}), 400

    try:
        z = int(z)
        x = int(x)
        y = int(y)
    except ValueError:
        return jsonify({"error": "Invalid parameters"}), 400

    tile_url = GPXZ_TILE_URL.format(z=z, x=x, y=y, token=GPXZ_TOKEN)

    try:
        res = requests.get(tile_url, timeout=10)
        res.raise_for_status()

        # Open the PNG image
        img = Image.open(BytesIO(res.content))
        img = img.convert("RGB")  # Ensure RGB

        width, height = img.size
        tile_data = []

        for y_pix in range(height):
            row = []
            for x_pix in range(width):
                r, g, b = img.getpixel((x_pix, y_pix))
                row.append({"r": r, "g": g, "b": b})
            tile_data.append(row)

        return jsonify(tile_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
