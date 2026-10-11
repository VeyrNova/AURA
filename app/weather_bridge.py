from __future__ import annotations

import json
import math
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QImage


class WeatherBridge(QObject):
    """Native AURA weather bridge backed by Open-Meteo."""

    weatherChanged = Signal()
    _resultReady = Signal(dict)

    WMO = {
        0: ("Ciel dégagé", "☀"),
        1: ("Plutôt dégagé", "☀"),
        2: ("Partiellement nuageux", "◒"),
        3: ("Couvert", "☁"),
        45: ("Brouillard", "≋"),
        48: ("Brouillard givrant", "≋"),
        51: ("Bruine légère", "☂"),
        53: ("Bruine", "☂"),
        55: ("Bruine forte", "☂"),
        56: ("Bruine verglaçante", "☂"),
        57: ("Bruine verglaçante forte", "☂"),
        61: ("Pluie légère", "☂"),
        63: ("Pluie", "☂"),
        65: ("Pluie forte", "☂"),
        66: ("Pluie verglaçante", "☂"),
        67: ("Pluie verglaçante forte", "☂"),
        71: ("Neige légère", "❄"),
        73: ("Neige", "❄"),
        75: ("Neige forte", "❄"),
        77: ("Grains de neige", "❄"),
        80: ("Averses légères", "☂"),
        81: ("Averses", "☂"),
        82: ("Fortes averses", "☂"),
        85: ("Averses de neige", "❄"),
        86: ("Fortes averses de neige", "❄"),
        95: ("Orage", "⚡"),
        96: ("Orage avec grêle", "⚡"),
        99: ("Orage fort avec grêle", "⚡"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self._error = ""
        self._location = ""
        self._location_detail = ""
        self._latitude = 0.0
        self._longitude = 0.0
        self._temperature = 0.0
        self._feels_like = 0.0
        self._humidity = 0
        self._wind_speed = 0.0
        self._wind_direction = ""
        self._wind_degrees = 0.0
        self._precipitation = 0.0
        self._weather_label = "—"
        self._weather_icon = "☁"
        self._updated_at = ""
        self._forecast_json = "[]"
        self._terrain_json = "{}"
        self._terrain_cache = {}
        self._wind_field_json = "{}"
        self._request_serial = 0
        self._settings_path = (
            Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
            / "AURA" / "data" / "weather_settings.json"
        )
        self._cache_dir = self._settings_path.parent / "weather_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_query = self._load_query()
        self._resultReady.connect(self._apply_result)

    def _load_query(self):
        try:
            if self._settings_path.is_file():
                data = json.loads(self._settings_path.read_text(encoding="utf-8"))
                value = str(data.get("query") or "").strip()
                if len(value) >= 2:
                    return value
        except Exception:
            pass
        return "Paris"

    def _save_query(self, query):
        try:
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._settings_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"query": query}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(tmp, self._settings_path)
        except Exception:
            pass

    def _cache_path(self, prefix, key):
        safe = "".join(ch if ch.isalnum() else "_" for ch in str(key))[:120]
        return self._cache_dir / f"{prefix}_{safe}.json"

    def _read_cache(self, prefix, key, max_age=None):
        path = self._cache_path(prefix, key)
        try:
            if not path.is_file():
                return None
            if max_age is not None and (time.time() - path.stat().st_mtime) > float(max_age):
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_cache(self, prefix, key, payload):
        path = self._cache_path(prefix, key)
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, path)
        except Exception:
            pass

    @staticmethod
    def _get_json(url, timeout=10.0, retries=1):
        last_exc = None
        for attempt in range(max(0, int(retries)) + 1):
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "AURA-Native/1.0", "Accept": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last_exc = exc
                if exc.code not in (429, 502, 503, 504) or attempt >= int(retries):
                    raise
                try:
                    retry_after = float(exc.headers.get("Retry-After") or 0)
                except Exception:
                    retry_after = 0
                time.sleep(min(6.0, max(1.5, retry_after or (1.8 * (attempt + 1)))))
            except Exception as exc:
                last_exc = exc
                if attempt >= int(retries):
                    raise
                time.sleep(1.2 * (attempt + 1))
        if last_exc:
            raise last_exc
        raise RuntimeError("weather_request_failed")

    @classmethod
    def _condition(cls, code):
        try:
            return cls.WMO.get(int(code), ("Conditions variables", "◌"))
        except Exception:
            return ("Conditions variables", "◌")

    @staticmethod
    def _wind_cardinal(degrees):
        try:
            deg = float(degrees) % 360.0
        except Exception:
            return "—"
        labels = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
        return labels[int((deg + 22.5) // 45) % 8]

    @staticmethod
    def _fr_day(iso_date):
        try:
            dt = datetime.fromisoformat(str(iso_date))
            labels = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"]
            return labels[dt.weekday()], dt.strftime("%d/%m")
        except Exception:
            return "JOUR", str(iso_date or "")

    @Property(bool, notify=weatherChanged)
    def loading(self): return self._loading

    @Property(str, notify=weatherChanged)
    def error(self): return self._error

    @Property(str, notify=weatherChanged)
    def locationName(self): return self._location

    @Property(str, notify=weatherChanged)
    def locationDetail(self): return self._location_detail

    @Property(str, notify=weatherChanged)
    def lastQuery(self): return self._last_query

    @Property(float, notify=weatherChanged)
    def latitude(self): return self._latitude

    @Property(float, notify=weatherChanged)
    def longitude(self): return self._longitude

    @Property(float, notify=weatherChanged)
    def temperature(self): return self._temperature

    @Property(float, notify=weatherChanged)
    def feelsLike(self): return self._feels_like

    @Property(int, notify=weatherChanged)
    def humidity(self): return self._humidity

    @Property(float, notify=weatherChanged)
    def windSpeed(self): return self._wind_speed

    @Property(str, notify=weatherChanged)
    def windDirection(self): return self._wind_direction

    @Property(float, notify=weatherChanged)
    def windDegrees(self): return self._wind_degrees

    @Property(float, notify=weatherChanged)
    def precipitation(self): return self._precipitation

    @Property(str, notify=weatherChanged)
    def weatherLabel(self): return self._weather_label

    @Property(str, notify=weatherChanged)
    def weatherIcon(self): return self._weather_icon

    @Property(str, notify=weatherChanged)
    def updatedAt(self): return self._updated_at

    @Property(str, notify=weatherChanged)
    def forecastJson(self): return self._forecast_json

    @Property(str, notify=weatherChanged)
    def terrainJson(self): return self._terrain_json

    @Property(str, notify=weatherChanged)
    def windFieldJson(self): return self._wind_field_json

    @staticmethod
    def _clip_polygon_ring(ring, xmin, ymin, xmax, ymax):
        pts = []
        for p in ring or []:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                try:
                    pts.append((float(p[0]), float(p[1])))
                except Exception:
                    pass
        if len(pts) < 3:
            return []

        def clip(points, inside, intersect):
            if not points:
                return []
            out = []
            prev = points[-1]
            prev_in = inside(prev)
            for cur in points:
                cur_in = inside(cur)
                if cur_in:
                    if not prev_in:
                        out.append(intersect(prev, cur))
                    out.append(cur)
                elif prev_in:
                    out.append(intersect(prev, cur))
                prev = cur
                prev_in = cur_in
            return out

        def ivert(xedge):
            def f(a, b):
                dx = b[0] - a[0]
                if abs(dx) < 1e-12:
                    return (xedge, a[1])
                t = (xedge - a[0]) / dx
                return (xedge, a[1] + t * (b[1] - a[1]))
            return f

        def ihoriz(yedge):
            def f(a, b):
                dy = b[1] - a[1]
                if abs(dy) < 1e-12:
                    return (a[0], yedge)
                t = (yedge - a[1]) / dy
                return (a[0] + t * (b[0] - a[0]), yedge)
            return f

        pts = clip(pts, lambda p: p[0] >= xmin, ivert(xmin))
        pts = clip(pts, lambda p: p[0] <= xmax, ivert(xmax))
        pts = clip(pts, lambda p: p[1] >= ymin, ihoriz(ymin))
        pts = clip(pts, lambda p: p[1] <= ymax, ihoriz(ymax))

        if len(pts) < 3:
            return []
        return [[round(p[0], 6), round(p[1], 6)] for p in pts]

    def _load_natural_earth_land(self):
        cached = getattr(self, "_natural_earth_land_cache", None)
        if cached is not None:
            return cached

        data_dir = self._settings_path.parent / "maps"
        data_dir.mkdir(parents=True, exist_ok=True)
        target = data_dir / "ne_10m_land.geojson"

        if not target.is_file() or target.stat().st_size < 100000:
            url = (
                "https://raw.githubusercontent.com/nvkelso/"
                "natural-earth-vector/master/geojson/ne_10m_land.geojson"
            )
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "AURA-Native/1.0",
                    "Accept": "application/geo+json,application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=25.0) as response:
                raw = response.read()
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(raw)
            os.replace(tmp, target)

        data = json.loads(target.read_text(encoding="utf-8"))
        self._natural_earth_land_cache = data
        return data

    def _fetch_land_polygons(self, lat_min, lat_max, lon_min, lon_max):
        """Clip Natural Earth land polygons to a viewport, including dateline wrap."""
        data = self._load_natural_earth_land()
        out = []

        def lon_windows(a, b):
            width = float(b) - float(a)
            if width >= 360.0:
                return [(-180.0, 180.0)]
            if a < -180.0:
                return [(a + 360.0, 180.0), (-180.0, b)]
            if b > 180.0:
                return [(a, 180.0), (-180.0, b - 360.0)]
            return [(a, b)]

        def ring_bbox(ring):
            xs = [p[0] for p in ring if isinstance(p, (list, tuple)) and len(p) >= 2]
            ys = [p[1] for p in ring if isinstance(p, (list, tuple)) and len(p) >= 2]
            if not xs or not ys:
                return None
            return min(xs), min(ys), max(xs), max(ys)

        def overlaps(box, x0, x1):
            if not box:
                return False
            return not (
                box[2] < x0 or box[0] > x1
                or box[3] < lat_min or box[1] > lat_max
            )

        for feature in data.get("features") or []:
            geom = feature.get("geometry") or {}
            gtype = geom.get("type")
            coords = geom.get("coordinates") or []

            rings = []
            if gtype == "Polygon":
                if coords:
                    rings.append(coords[0])
            elif gtype == "MultiPolygon":
                for poly in coords:
                    if poly:
                        rings.append(poly[0])

            for ring in rings:
                box = ring_bbox(ring)
                for x0, x1 in lon_windows(lon_min, lon_max):
                    if not overlaps(box, x0, x1):
                        continue
                    clipped = self._clip_polygon_ring(
                        ring, x0, lat_min, x1, lat_max
                    )
                    if len(clipped) >= 3:
                        out.append(clipped)

        return out

    @staticmethod
    def _clip_line_segment(a, b, xmin, ymin, xmax, ymax):
        """Liang-Barsky clip of one lon/lat segment to a rectangle."""
        x0, y0 = float(a[0]), float(a[1])
        x1, y1 = float(b[0]), float(b[1])
        dx = x1 - x0
        dy = y1 - y0
        p = (-dx, dx, -dy, dy)
        q = (x0 - xmin, xmax - x0, y0 - ymin, ymax - y0)
        u1, u2 = 0.0, 1.0

        for pi, qi in zip(p, q):
            if abs(pi) < 1e-12:
                if qi < 0:
                    return None
                continue
            t = qi / pi
            if pi < 0:
                if t > u2:
                    return None
                if t > u1:
                    u1 = t
            else:
                if t < u1:
                    return None
                if t < u2:
                    u2 = t

        return (
            [x0 + u1 * dx, y0 + u1 * dy],
            [x0 + u2 * dx, y0 + u2 * dy],
        )

    @staticmethod
    def _lon_windows(lon_min, lon_max):
        width = float(lon_max) - float(lon_min)
        if width >= 360.0:
            return [(-180.0, 180.0)]
        if lon_min < -180.0:
            return [(lon_min + 360.0, 180.0), (-180.0, lon_max)]
        if lon_max > 180.0:
            return [(lon_min, 180.0), (-180.0, lon_max - 360.0)]
        return [(lon_min, lon_max)]

    def _load_natural_earth_coastline(self):
        cached = getattr(self, "_natural_earth_coastline_cache", None)
        if cached is not None:
            return cached

        data_dir = self._settings_path.parent / "maps"
        data_dir.mkdir(parents=True, exist_ok=True)
        target = data_dir / "ne_10m_coastline.geojson"

        if not target.is_file() or target.stat().st_size < 100000:
            url = (
                "https://raw.githubusercontent.com/nvkelso/"
                "natural-earth-vector/master/geojson/ne_10m_coastline.geojson"
            )
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "AURA-Native/1.0",
                    "Accept": "application/geo+json,application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=25.0) as response:
                raw = response.read()
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(raw)
            os.replace(tmp, target)

        data = json.loads(target.read_text(encoding="utf-8"))
        self._natural_earth_coastline_cache = data
        return data

    def _load_natural_earth_places(self):
        cached = getattr(self, "_natural_earth_places_cache", None)
        if cached is not None:
            return cached

        data_dir = self._settings_path.parent / "maps"
        data_dir.mkdir(parents=True, exist_ok=True)
        target = data_dir / "ne_10m_populated_places_simple.geojson"

        if not target.is_file() or target.stat().st_size < 100000:
            url = (
                "https://raw.githubusercontent.com/nvkelso/"
                "natural-earth-vector/master/geojson/"
                "ne_10m_populated_places_simple.geojson"
            )
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "AURA-Native/1.0",
                    "Accept": "application/geo+json,application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=25.0) as response:
                raw = response.read()
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(raw)
            os.replace(tmp, target)

        data = json.loads(target.read_text(encoding="utf-8"))
        self._natural_earth_places_cache = data
        return data

    def _fetch_coastline_lines(self, lat_min, lat_max, lon_min, lon_max):
        """Return clipped Natural Earth coastline polylines for the active viewport."""
        data = self._load_natural_earth_coastline()
        out = []

        def consume_line(line, x0, x1):
            current = []
            for i in range(1, len(line or [])):
                a = line[i - 1]
                b = line[i]
                if not (
                    isinstance(a, (list, tuple)) and len(a) >= 2
                    and isinstance(b, (list, tuple)) and len(b) >= 2
                ):
                    continue
                clipped = self._clip_line_segment(
                    a, b, x0, lat_min, x1, lat_max
                )
                if clipped is None:
                    if len(current) >= 2:
                        out.append(current)
                    current = []
                    continue

                p0, p1 = clipped
                if not current:
                    current = [p0, p1]
                else:
                    last = current[-1]
                    if abs(last[0] - p0[0]) < 1e-6 and abs(last[1] - p0[1]) < 1e-6:
                        current.append(p1)
                    else:
                        if len(current) >= 2:
                            out.append(current)
                        current = [p0, p1]

            if len(current) >= 2:
                out.append(current)

        windows = self._lon_windows(lon_min, lon_max)

        for feature in data.get("features") or []:
            geom = feature.get("geometry") or {}
            gtype = geom.get("type")
            coords = geom.get("coordinates") or []
            lines = []
            if gtype == "LineString":
                lines = [coords]
            elif gtype == "MultiLineString":
                lines = coords

            for line in lines:
                for x0, x1 in windows:
                    consume_line(line, x0, x1)

        return out

    def _fetch_visible_places(self, lat_min, lat_max, lon_min, lon_max, limit=28):
        """Return globally valid nearby city labels from Natural Earth."""
        data = self._load_natural_earth_places()
        windows = self._lon_windows(lon_min, lon_max)
        places = []

        def in_lon_windows(lon):
            for x0, x1 in windows:
                if x0 <= lon <= x1:
                    return True
            return False

        for feature in data.get("features") or []:
            geom = feature.get("geometry") or {}
            if geom.get("type") != "Point":
                continue

            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue

            try:
                lon = float(coords[0])
                lat = float(coords[1])
            except Exception:
                continue

            if lat < lat_min or lat > lat_max or not in_lon_windows(lon):
                continue

            props = feature.get("properties") or {}
            name = (
                props.get("name")
                or props.get("nameascii")
                or props.get("NAME")
                or ""
            )
            if not name:
                continue

            try:
                pop = float(props.get("pop_max") or props.get("POP_MAX") or 0.0)
            except Exception:
                pop = 0.0
            try:
                rank = float(props.get("scalerank") or props.get("SCALERANK") or 99.0)
            except Exception:
                rank = 99.0

            places.append({
                "name": str(name),
                "lat": lat,
                "lon": lon,
                "population": pop,
                "rank": rank,
                "country": str(props.get("adm0name") or props.get("ADM0NAME") or ""),
                "region": str(props.get("adm1name") or props.get("ADM1NAME") or ""),
            })

        places.sort(key=lambda p: (p["rank"], -p["population"], p["name"]))
        return places[:max(1, int(limit))]

    @staticmethod
    def _wrap_longitude(lon):
        value = float(lon)
        return ((value + 180.0) % 360.0) - 180.0

    def _dynamic_map_bounds(self, lat, lon, span_km=300.0, aspect=2.0, pad=1.10):
        """Ground-distance viewport valid for arbitrary cities worldwide."""
        lat = max(-84.0, min(84.0, float(lat)))
        lon = float(lon)
        width_km = float(span_km) * float(pad)
        height_km = width_km / max(1.15, float(aspect))
        half_lat = (height_km * 0.5) / 111.32
        cos_lat = max(0.10, abs(math.cos(math.radians(lat))))
        half_lon = (width_km * 0.5) / (111.32 * cos_lat)
        return (
            max(-85.0, lat - half_lat),
            min(85.0, lat + half_lat),
            lon - half_lon,
            lon + half_lon,
        )

    def _load_natural_earth_admin1_lines(self):
        cached = getattr(self, "_natural_earth_admin1_cache", None)
        if cached is not None:
            return cached

        data_dir = self._settings_path.parent / "maps"
        data_dir.mkdir(parents=True, exist_ok=True)
        target = data_dir / "ne_10m_admin_1_states_provinces_lines.geojson"

        if not target.is_file() or target.stat().st_size < 100000:
            url = (
                "https://raw.githubusercontent.com/nvkelso/"
                "natural-earth-vector/master/geojson/"
                "ne_10m_admin_1_states_provinces_lines.geojson"
            )
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "AURA-Native/1.0",
                    "Accept": "application/geo+json,application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=35.0) as response:
                raw = response.read()
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(raw)
            os.replace(tmp, target)

        data = json.loads(target.read_text(encoding="utf-8"))
        self._natural_earth_admin1_cache = data
        return data

    def _load_natural_earth_rivers(self):
        cached = getattr(self, "_natural_earth_rivers_cache", None)
        if cached is not None:
            return cached

        data_dir = self._settings_path.parent / "maps"
        data_dir.mkdir(parents=True, exist_ok=True)
        target = data_dir / "ne_10m_rivers_lake_centerlines_scale_rank.geojson"

        if not target.is_file() or target.stat().st_size < 100000:
            url = (
                "https://raw.githubusercontent.com/nvkelso/"
                "natural-earth-vector/master/geojson/"
                "ne_10m_rivers_lake_centerlines_scale_rank.geojson"
            )
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "AURA-Native/1.0",
                    "Accept": "application/geo+json,application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=35.0) as response:
                raw = response.read()
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(raw)
            os.replace(tmp, target)

        data = json.loads(target.read_text(encoding="utf-8"))
        self._natural_earth_rivers_cache = data
        return data

    def _fetch_ranked_context_lines(
        self,
        data,
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        rank_limit=6,
        max_lines=240,
    ):
        """Clip real Natural Earth line features to the active viewport."""
        out = []
        windows = self._lon_windows(lon_min, lon_max)

        def feature_rank(props):
            for key in ("scalerank", "scale_rank", "SCALERANK", "ScaleRank"):
                if key in props:
                    try:
                        return float(props.get(key))
                    except Exception:
                        pass
            return 5.0

        def append_line(line, rank, name, x0, x1):
            current = []
            for i in range(1, len(line or [])):
                a = line[i - 1]
                b = line[i]
                if not (
                    isinstance(a, (list, tuple)) and len(a) >= 2
                    and isinstance(b, (list, tuple)) and len(b) >= 2
                ):
                    continue

                clipped = self._clip_line_segment(
                    a, b, x0, lat_min, x1, lat_max
                )
                if clipped is None:
                    if len(current) >= 2:
                        out.append({
                            "points": current,
                            "rank": rank,
                            "name": name,
                        })
                    current = []
                    if len(out) >= max_lines:
                        return
                    continue

                p0, p1 = clipped
                if not current:
                    current = [p0, p1]
                else:
                    last = current[-1]
                    if (
                        abs(last[0] - p0[0]) < 1e-6
                        and abs(last[1] - p0[1]) < 1e-6
                    ):
                        current.append(p1)
                    else:
                        if len(current) >= 2:
                            out.append({
                                "points": current,
                                "rank": rank,
                                "name": name,
                            })
                        current = [p0, p1]

                if len(out) >= max_lines:
                    return

            if len(current) >= 2 and len(out) < max_lines:
                out.append({
                    "points": current,
                    "rank": rank,
                    "name": name,
                })

        for feature in data.get("features") or []:
            if len(out) >= max_lines:
                break

            props = feature.get("properties") or {}
            rank = feature_rank(props)
            if rank > float(rank_limit):
                continue

            name = str(
                props.get("name")
                or props.get("name_en")
                or props.get("NAME")
                or ""
            )

            geom = feature.get("geometry") or {}
            gtype = geom.get("type")
            coords = geom.get("coordinates") or []
            if gtype == "LineString":
                lines = [coords]
            elif gtype == "MultiLineString":
                lines = coords
            else:
                continue

            for line in lines:
                if len(out) >= max_lines:
                    break
                for x0, x1 in windows:
                    append_line(line, rank, name, x0, x1)
                    if len(out) >= max_lines:
                        break

        out.sort(key=lambda item: (item.get("rank", 99), item.get("name", "")))
        return out[:max_lines]

    def _fetch_admin1_lines(self, lat_min, lat_max, lon_min, lon_max):
        data = self._load_natural_earth_admin1_lines()
        return self._fetch_ranked_context_lines(
            data,
            lat_min,
            lat_max,
            lon_min,
            lon_max,
            rank_limit=6,
            max_lines=180,
        )

    def _fetch_river_lines(self, lat_min, lat_max, lon_min, lon_max):
        data = self._load_natural_earth_rivers()
        return self._fetch_ranked_context_lines(
            data,
            lat_min,
            lat_max,
            lon_min,
            lon_max,
            rank_limit=6,
            max_lines=220,
        )

    @staticmethod
    def _slippy_tile_fraction(lat, lon, zoom):
        """Return fractional Web-Mercator tile coordinates."""
        lat = max(-85.05112878, min(85.05112878, float(lat)))
        lon = ((float(lon) + 180.0) % 360.0) - 180.0
        n = float(1 << int(zoom))
        x = (lon + 180.0) / 360.0 * n
        lat_rad = math.radians(lat)
        y = (
            1.0
            - math.asinh(math.tan(lat_rad)) / math.pi
        ) * 0.5 * n
        return x, y

    def _terrarium_tile_path(self, zoom, x, y):
        base = self._settings_path.parent / "maps" / "terrarium"
        return base / str(int(zoom)) / str(int(x)) / f"{int(y)}.png"

    def _load_terrarium_tile(self, zoom, x, y):
        """Load one public AWS Terrain Tiles Terrarium PNG with local caching."""
        zoom = int(zoom)
        n = 1 << zoom
        x = int(x) % n
        y = max(0, min(n - 1, int(y)))

        path = self._terrarium_tile_path(zoom, x, y)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.is_file() or path.stat().st_size < 1000:
            url = (
                "https://s3.amazonaws.com/elevation-tiles-prod/"
                f"terrarium/{zoom}/{x}/{y}.png"
            )
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "AURA-Native/1.0",
                    "Accept": "image/png",
                },
            )
            with urllib.request.urlopen(req, timeout=20.0) as response:
                raw = response.read()
            if len(raw) < 1000:
                raise RuntimeError("terrarium_tile_too_small")
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(raw)
            os.replace(tmp, path)

        image = QImage(str(path))
        if image.isNull() or image.width() < 2 or image.height() < 2:
            raise RuntimeError("terrarium_tile_decode_failed")
        return image

    @staticmethod
    def _terrarium_elevation(color):
        """Mapzen Terrarium RGB -> elevation in metres."""
        value = (
            float(color.red()) * 256.0
            + float(color.green())
            + float(color.blue()) / 256.0
            - 32768.0
        )
        if value < -12000.0 or value > 10000.0:
            return 0.0
        return value

    def _fetch_terrarium_elevation_grid(
        self,
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        rows=40,
        cols=64,
        zoom=8,
    ):
        """Sample a high-resolution DEM from public AWS Terrain Tiles."""
        rows = max(8, int(rows))
        cols = max(12, int(cols))
        zoom = max(1, min(12, int(zoom)))

        tiles = {}
        elevations = []

        for r in range(rows):
            rr = r / float(rows - 1)
            plat = float(lat_max) - rr * (float(lat_max) - float(lat_min))

            for c in range(cols):
                cc = c / float(cols - 1)
                raw_lon = float(lon_min) + cc * (float(lon_max) - float(lon_min))
                plon = self._wrap_longitude(raw_lon)

                txf, tyf = self._slippy_tile_fraction(plat, plon, zoom)
                tx = int(math.floor(txf))
                ty = int(math.floor(tyf))
                key = (zoom, tx, ty)

                image = tiles.get(key)
                if image is None:
                    image = self._load_terrarium_tile(zoom, tx, ty)
                    tiles[key] = image

                fx = txf - math.floor(txf)
                fy = tyf - math.floor(tyf)
                px = max(0, min(image.width() - 1, int(fx * image.width())))
                py = max(0, min(image.height() - 1, int(fy * image.height())))

                elev = self._terrarium_elevation(image.pixelColor(px, py))
                elevations.append(round(float(elev), 1))

        if len(elevations) != rows * cols:
            raise RuntimeError("terrarium_grid_count_mismatch")

        return rows, cols, elevations

    def _fetch_open_meteo_elevation_grid(
        self,
        lat_min,
        lat_max,
        lon_min,
        lon_max,
        rows=12,
        cols=18,
    ):
        """Safe fallback if public terrain tiles are unavailable."""
        coords = []
        for r in range(rows):
            rr = r / float(rows - 1)
            plat = lat_max - rr * (lat_max - lat_min)
            for c in range(cols):
                cc = c / float(cols - 1)
                raw_lon = lon_min + cc * (lon_max - lon_min)
                coords.append((plat, self._wrap_longitude(raw_lon)))

        elevations = []
        batch_size = 100
        for start in range(0, len(coords), batch_size):
            batch = coords[start:start + batch_size]
            latitudes = ",".join(f"{p[0]:.5f}" for p in batch)
            longitudes = ",".join(f"{p[1]:.5f}" for p in batch)
            url = (
                "https://api.open-meteo.com/v1/elevation?"
                + urllib.parse.urlencode({
                    "latitude": latitudes,
                    "longitude": longitudes,
                })
            )
            data = self._get_json(url, timeout=12.0, retries=0)
            vals = list(data.get("elevation") or [])
            if len(vals) != len(batch):
                raise RuntimeError("terrain_elevation_count_mismatch")
            elevations.extend(float(v or 0.0) for v in vals)

        return int(rows), int(cols), elevations

    def _fetch_terrain_grid(self, lat, lon):
        """Fetch high-resolution global relief + geography around the selected city."""
        lat = float(lat)
        lon = float(lon)
        span_km = 300.0
        aspect = 2.0

        # Versioned cache so R22 never reuses the old coarse 12x18 DEM.
        key = f"{round(lat,2)}_{round(lon,2)}_{int(span_km)}_terrain_hr1"
        cached = self._read_cache("terrain", key, max_age=30 * 24 * 3600)
        if (
            isinstance(cached, dict)
            and int(cached.get("rows", 0) or 0) >= 32
            and int(cached.get("cols", 0) or 0) >= 48
            and cached.get("dem_source") == "aws-terrarium-v1"
        ):
            return cached

        lat_min, lat_max, lon_min, lon_max = self._dynamic_map_bounds(
            lat, lon, span_km=span_km, aspect=aspect, pad=1.12
        )

        dem_source = "aws-terrarium-v1"
        try:
            rows, cols, elevations = self._fetch_terrarium_elevation_grid(
                lat_min,
                lat_max,
                lon_min,
                lon_max,
                rows=40,
                cols=64,
                zoom=8,
            )
        except Exception:
            # Keep AURA functional if the public terrain tile service is unreachable.
            dem_source = "open-meteo-elevation-fallback"
            rows, cols, elevations = self._fetch_open_meteo_elevation_grid(
                lat_min,
                lat_max,
                lon_min,
                lon_max,
                rows=12,
                cols=18,
            )

        try:
            land_polygons = self._fetch_land_polygons(
                lat_min, lat_max, lon_min, lon_max
            )
        except Exception:
            land_polygons = []

        try:
            coastlines = self._fetch_coastline_lines(
                lat_min, lat_max, lon_min, lon_max
            )
        except Exception:
            coastlines = []

        try:
            places = self._fetch_visible_places(
                lat_min, lat_max, lon_min, lon_max, limit=28
            )
        except Exception:
            places = []

        try:
            admin_lines = self._fetch_admin1_lines(
                lat_min, lat_max, lon_min, lon_max
            )
        except Exception:
            admin_lines = []

        try:
            rivers = self._fetch_river_lines(
                lat_min, lat_max, lon_min, lon_max
            )
        except Exception:
            rivers = []

        terrain = {
            "rows": rows,
            "cols": cols,
            "center_lat": lat,
            "center_lon": lon,
            "span_km": span_km,
            "aspect": aspect,
            "lat_min": lat_min,
            "lat_max": lat_max,
            "lon_min": lon_min,
            "lon_max": lon_max,
            "elevation": elevations,
            "land_polygons": land_polygons,
            "coastlines": coastlines,
            "places": places,
            "admin_lines": admin_lines,
            "rivers": rivers,
            "dem_source": dem_source,
            "source": (
                "Natural Earth 1:10m + AWS Terrain Tiles (Terrarium)"
                if dem_source == "aws-terrarium-v1"
                else "Natural Earth 1:10m + Open-Meteo elevation fallback"
            ),
        }
        self._write_cache("terrain", key, terrain)
        return terrain

    @Slot()
    def ensureLoaded(self):
        if not self._location and not self._loading:
            self.searchCity(self._last_query)

    @Slot()
    def refresh(self):
        if not self._loading:
            self.searchCity(self._last_query)

    @Slot(str)
    def searchCity(self, query):
        query = str(query or "").strip()
        if len(query) < 2:
            self._error = "Saisissez au moins 2 caractères."
            self.weatherChanged.emit()
            return

        self._request_serial += 1
        serial = self._request_serial
        self._loading = True
        self._error = ""
        self.weatherChanged.emit()

        def worker():
            try:
                place_key = query.casefold().strip()
                place = self._read_cache("geocode", place_key, max_age=30 * 24 * 3600)
                if not isinstance(place, dict) or "latitude" not in place or "longitude" not in place:
                    geocode_url = (
                        "https://geocoding-api.open-meteo.com/v1/search?"
                        + urllib.parse.urlencode(
                            {"name": query, "count": 1, "language": "fr", "format": "json"}
                        )
                    )
                    geo = self._get_json(geocode_url, retries=1)
                    results = list(geo.get("results") or [])
                    if not results:
                        raise RuntimeError("Ville introuvable")
                    place = dict(results[0])
                    self._write_cache("geocode", place_key, place)
                else:
                    place = dict(place)
                lat = float(place["latitude"])
                lon = float(place["longitude"])

                # Essential current/forecast data is always fetched BEFORE optional map layers.
                terrain_grid = {}

                current_vars = ",".join([
                    "temperature_2m", "apparent_temperature", "relative_humidity_2m",
                    "precipitation", "weather_code", "wind_speed_10m", "wind_direction_10m"
                ])
                daily_vars = ",".join([
                    "weather_code", "temperature_2m_max", "temperature_2m_min",
                    "precipitation_probability_max", "sunrise", "sunset"
                ])
                forecast_url = (
                    "https://api.open-meteo.com/v1/forecast?"
                    + urllib.parse.urlencode({
                        "latitude": lat,
                        "longitude": lon,
                        "current": current_vars,
                        "daily": daily_vars,
                        "timezone": "auto",
                        "forecast_days": 7,
                        "temperature_unit": "celsius",
                        "wind_speed_unit": "kmh",
                        "precipitation_unit": "mm",
                    })
                )
                forecast = self._get_json(forecast_url, timeout=10.0, retries=2)
                current = dict(forecast.get("current") or {})
                daily = dict(forecast.get("daily") or {})

                # Optional geography/relief comes second so it can never block core weather.
                try:
                    terrain_grid = self._fetch_terrain_grid(lat, lon)
                except Exception:
                    terrain_grid = self._read_cache(
                        "terrain", f"{lat:.3f}_{lon:.3f}", max_age=90 * 24 * 3600
                    ) or {}

                # Spatial weather grid used by the native Windy-like renderer.
                # Open-Meteo supports multiple comma-separated coordinates in one request.
                field_key = f"{lat:.3f}_{lon:.3f}"
                field = self._read_cache("windfield", field_key, max_age=20 * 60) or {}
                try:
                    grid_rows = 3
                    grid_cols = 5
                    field_lat_min, field_lat_max, field_lon_min, field_lon_max = (
                        self._dynamic_map_bounds(
                            lat, lon, span_km=300.0, aspect=2.0, pad=1.12
                        )
                    )
                    grid_lats = []
                    grid_lons = []
                    for row in range(grid_rows):
                        fy = row / float(grid_rows - 1)
                        sample_lat = field_lat_max - fy * (
                            field_lat_max - field_lat_min
                        )
                        for col in range(grid_cols):
                            fx = col / float(grid_cols - 1)
                            raw_lon = field_lon_min + fx * (
                                field_lon_max - field_lon_min
                            )
                            grid_lats.append(f"{sample_lat:.5f}")
                            grid_lons.append(
                                f"{self._wrap_longitude(raw_lon):.5f}"
                            )

                    grid_vars = ",".join([
                        "wind_speed_10m",
                        "wind_direction_10m",
                        "temperature_2m",
                        "precipitation",
                        "cloud_cover",
                        "pressure_msl",
                    ])
                    grid_url = (
                        "https://api.open-meteo.com/v1/forecast?"
                        + urllib.parse.urlencode({
                            "latitude": ",".join(grid_lats),
                            "longitude": ",".join(grid_lons),
                            "current": grid_vars,
                            "forecast_days": 1,
                            "temperature_unit": "celsius",
                            "wind_speed_unit": "kmh",
                            "precipitation_unit": "mm",
                        })
                    )
                    grid_payload = self._get_json(grid_url, timeout=8.0, retries=0)
                    grid_items = grid_payload if isinstance(grid_payload, list) else [grid_payload]
                    points = []
                    for item in grid_items:
                        gcur = dict((item or {}).get("current") or {})
                        gspeed = float(gcur.get("wind_speed_10m") or 0.0)
                        gfrom = float(gcur.get("wind_direction_10m") or 0.0)
                        grad = gfrom * 3.141592653589793 / 180.0
                        # Meteorological bearing is the direction the wind comes FROM.
                        # Convert to screen velocity pointing TO the destination.
                        gu = -gspeed * __import__("math").sin(grad)
                        gv =  gspeed * __import__("math").cos(grad)
                        points.append({
                            "u": round(gu, 5),
                            "v": round(gv, 5),
                            "speed": round(gspeed, 3),
                            "direction": round(gfrom, 2),
                            "temperature": round(float(gcur.get("temperature_2m") or 0.0), 2),
                            "precipitation": round(float(gcur.get("precipitation") or 0.0), 3),
                            "clouds": round(float(gcur.get("cloud_cover") or 0.0), 2),
                            "pressure": round(float(gcur.get("pressure_msl") or 1013.0), 2),
                        })
                    if len(points) == grid_rows * grid_cols:
                        field = {
                            "rows": grid_rows,
                            "cols": grid_cols,
                            "center_lat": lat,
                            "center_lon": lon,
                            "span_km": 300.0,
                            "aspect": 2.0,
                            "lat_min": field_lat_min,
                            "lat_max": field_lat_max,
                            "lon_min": field_lon_min,
                            "lon_max": field_lon_max,
                            "points": points,
                        }
                        self._write_cache("windfield", field_key, field)
                except Exception:
                    field = field or self._read_cache(
                        "windfield", field_key, max_age=6 * 3600
                    ) or {}

                dates = list(daily.get("time") or [])
                codes = list(daily.get("weather_code") or [])
                tmax = list(daily.get("temperature_2m_max") or [])
                tmin = list(daily.get("temperature_2m_min") or [])
                rainp = list(daily.get("precipitation_probability_max") or [])
                sunrise = list(daily.get("sunrise") or [])
                sunset = list(daily.get("sunset") or [])

                days = []
                for i, date_value in enumerate(dates[:7]):
                    code = codes[i] if i < len(codes) else -1
                    label, icon = self._condition(code)
                    day_label, date_label = self._fr_day(date_value)
                    days.append({
                        "day": day_label,
                        "date": date_label,
                        "label": label,
                        "icon": icon,
                        "max": round(float(tmax[i]), 1) if i < len(tmax) else 0.0,
                        "min": round(float(tmin[i]), 1) if i < len(tmin) else 0.0,
                        "rain": int(round(float(rainp[i]))) if i < len(rainp) and rainp[i] is not None else 0,
                        "sunrise": str(sunrise[i])[-5:] if i < len(sunrise) else "",
                        "sunset": str(sunset[i])[-5:] if i < len(sunset) else "",
                    })

                # Do not let an occasional partial daily response collapse the 7-day ribbon.
                # Reuse only a previously complete snapshot; never invent weather values.
                if len(days) < 5:
                    previous_snapshot = self._read_cache(
                        "snapshot", query.casefold().strip(), max_age=48 * 3600
                    )
                    previous_days = (
                        previous_snapshot.get("forecast")
                        if isinstance(previous_snapshot, dict)
                        else None
                    )
                    if isinstance(previous_days, list) and len(previous_days) >= 5:
                        days = previous_days[:7]

                code = int(current.get("weather_code", -1))
                condition, icon = self._condition(code)
                name = str(place.get("name") or query)
                admin = str(place.get("admin1") or "").strip()
                country = str(place.get("country") or "").strip()
                detail = " · ".join([x for x in (admin, country) if x])

                self._resultReady.emit({
                    "serial": serial,
                    "ok": True,
                    "query": query,
                    "location": name,
                    "detail": detail,
                    "latitude": lat,
                    "longitude": lon,
                    "temperature": float(current.get("temperature_2m") or 0.0),
                    "feels_like": float(current.get("apparent_temperature") or 0.0),
                    "humidity": int(round(float(current.get("relative_humidity_2m") or 0))),
                    "wind_speed": float(current.get("wind_speed_10m") or 0.0),
                    "wind_direction": self._wind_cardinal(current.get("wind_direction_10m")),
                    "wind_degrees": float(current.get("wind_direction_10m") or 0.0),
                    "precipitation": float(current.get("precipitation") or 0.0),
                    "weather_label": condition,
                    "weather_icon": icon,
                    "updated_at": str(current.get("time") or "").replace("T", " "),
                    "terrain": terrain_grid,
                    "forecast": days,
                    "wind_field": field,
                })
            except Exception as exc:
                cached = self._read_cache(
                    "snapshot", query.casefold().strip(), max_age=6 * 3600
                )
                if isinstance(cached, dict) and cached.get("ok"):
                    cached = dict(cached)
                    cached["serial"] = serial
                    cached["cached"] = True
                    self._resultReady.emit(cached)
                else:
                    message = str(exc) or type(exc).__name__
                    if "429" in message or "Too Many Requests" in message:
                        message = "Limite Open-Meteo temporaire · réessayez dans 60 s"
                    self._resultReady.emit({
                        "serial": serial,
                        "ok": False,
                        "error": message,
                    })

        threading.Thread(target=worker, daemon=True, name="AuraNativeWeather").start()

    @Slot(dict)
    def _apply_result(self, payload):
        if int(payload.get("serial") or 0) != self._request_serial:
            return
        self._loading = False
        if not bool(payload.get("ok")):
            self._error = "Météo indisponible · " + str(payload.get("error") or "erreur réseau")
            self.weatherChanged.emit()
            return

        self._error = ""
        self._last_query = str(payload.get("query") or self._last_query)
        self._location = str(payload.get("location") or "")
        self._location_detail = str(payload.get("detail") or "")
        self._latitude = float(payload.get("latitude") or 0.0)
        self._longitude = float(payload.get("longitude") or 0.0)
        self._temperature = float(payload.get("temperature") or 0.0)
        self._feels_like = float(payload.get("feels_like") or 0.0)
        self._humidity = int(payload.get("humidity") or 0)
        self._wind_speed = float(payload.get("wind_speed") or 0.0)
        self._wind_direction = str(payload.get("wind_direction") or "—")
        self._wind_degrees = float(payload.get("wind_degrees") or 0.0)
        self._precipitation = float(payload.get("precipitation") or 0.0)
        self._weather_label = str(payload.get("weather_label") or "—")
        self._weather_icon = str(payload.get("weather_icon") or "☁")
        self._updated_at = str(payload.get("updated_at") or "")
        self._forecast_json = json.dumps(payload.get("forecast") or [], ensure_ascii=False)
        self._terrain_json = json.dumps(payload.get("terrain") or {}, ensure_ascii=False)
        self._wind_field_json = json.dumps(payload.get("wind_field") or {}, ensure_ascii=False)
        self._save_query(self._last_query)
        try:
            cache_payload = dict(payload)
            cache_payload["serial"] = 0
            cached_forecast = cache_payload.get("forecast")
            # Never overwrite a good snapshot with an incomplete daily payload.
            if isinstance(cached_forecast, list) and len(cached_forecast) >= 5:
                self._write_cache(
                    "snapshot",
                    self._last_query.casefold().strip(),
                    cache_payload,
                )
        except Exception:
            pass
        self.weatherChanged.emit()
