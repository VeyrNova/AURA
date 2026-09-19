from __future__ import annotations

import math

TILE_SIZE = 256
MIN_LAT = -85.05112878
MAX_LAT = 85.05112878


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def geo_to_world_xy(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    lat = clamp(lat, MIN_LAT, MAX_LAT)
    lon = ((float(lon) + 180.0) % 360.0) - 180.0
    scale = float(TILE_SIZE * (1 << int(zoom)))
    x = (lon + 180.0) / 360.0 * scale
    rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(rad)) / math.pi) * 0.5 * scale
    return x, y


def world_xy_to_geo(x: float, y: float, zoom: int) -> tuple[float, float]:
    scale = float(TILE_SIZE * (1 << int(zoom)))
    x = float(x) % scale
    y = clamp(y, 0.0, scale)
    lon = x / scale * 360.0 - 180.0
    n = math.pi * (1.0 - 2.0 * y / scale)
    lat = math.degrees(math.atan(math.sinh(n)))
    return lat, lon
