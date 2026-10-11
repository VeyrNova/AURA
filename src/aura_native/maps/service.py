from dataclasses import dataclass
from pathlib import Path
import json

@dataclass(frozen=True)
class MapPlace:
    name: str; latitude: float; longitude: float; country: str = ""

class MapsService:
    def __init__(self, geocoder=None, geometry_root=None, routing_service=None):
        self.geocoder = geocoder
        self.routing_service = routing_service
        self.geometry_root = Path(geometry_root) if geometry_root is not None else None
        self._geometry_cache = {}
    def search(self, query):
        if not self.geocoder or not str(query).strip(): return ()
        return tuple(MapPlace(x.name, x.latitude, x.longitude, x.country) for x in self.geocoder.search_locations(str(query).strip()))

    def calculate_route(self, origin, destination):
        from .routing import RoutingError
        if self.routing_service is None: raise RoutingError('provider_unavailable')
        return self.routing_service.calculate(origin, destination)

    def local_geometry(self, resolution='regional'):
        """Read explicitly bundled GeoJSON only; never download or discover AppData."""
        if resolution in self._geometry_cache: return self._geometry_cache[resolution]
        result = {'land_polygons': [], 'coastlines': [], 'boundaries': []}
        if self.geometry_root is None: return result
        prefix = 'world_50m' if resolution == 'world' else 'europe_10m'
        bundle = self.geometry_root / 'natural_earth'
        names = ((bundle / f'{prefix}_land.geojson', 'land_polygons'),
                 (bundle / f'{prefix}_coastline.geojson', 'coastlines'))
        if not all(path.is_file() for path, _ in names):
            names = ((self.geometry_root / 'land.geojson', 'land_polygons'),
                     (self.geometry_root / 'coastline.geojson', 'coastlines'),
                     (self.geometry_root / 'boundaries.geojson', 'boundaries'))
        try:
            for path, key in names:
                if not path.is_file(): continue
                document = json.loads(path.read_text(encoding='utf-8'))
                if document.get('type') != 'FeatureCollection': raise ValueError('invalid GeoJSON collection')
                for feature in document.get('features', ()):
                    geometry = feature.get('geometry') or {}
                    kind, coords = geometry.get('type'), geometry.get('coordinates') or []
                    if kind == 'LineString': result[key].append(coords)
                    elif kind == 'MultiLineString': result[key].extend(coords)
                    elif kind == 'Polygon': result[key].extend(coords[:1])
                    elif kind == 'MultiPolygon': result[key].extend(poly[0] for poly in coords if poly)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            result = {'land_polygons': [], 'coastlines': [], 'boundaries': []}
        if not result['land_polygons'] or not result['coastlines']:
            result = {'land_polygons': [], 'coastlines': [], 'boundaries': []}
        self._geometry_cache[resolution] = result
        return result
