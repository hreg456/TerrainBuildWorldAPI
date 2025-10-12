# TerrainBuildWorldAPI

This is a simple Flask API for generating terrain tiles and fetching elevation data.

## Endpoints

### GET /
- Returns: {"status": "on"}

### GET /tile
- Query params: z, x, y (tile coordinates)
- Returns: PNG tile from OpenStreetMap

Example:
```
/tile?z=14&x=656&y=1584
```

### GET /elevation
- Query params: lat, lon (coordinates)
- Returns: JSON with elevation in meters

Example:
```
/elevation?lat=40.7&lon=-74.0
```

## Notes
- Tiles and elevation data are cached for 5 minutes to improve performance.
- Free APIs are used (OpenStreetMap & OpenTopoData)