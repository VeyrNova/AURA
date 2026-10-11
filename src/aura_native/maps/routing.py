"""Native, injectable road-routing boundary. No network activity at import."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import threading
import time
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class RoutingError(Exception):
    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


@dataclass(frozen=True)
class RoutePlace:
    label: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class RouteResult:
    origin: RoutePlace
    destination: RoutePlace
    distance_m: float
    duration_s: float
    geometry: tuple[tuple[float, float], ...]  # longitude, latitude
    instructions: tuple[str, ...]


class RoutingBackend(Protocol):
    def route(self, origin: RoutePlace, destination: RoutePlace) -> dict: ...


class OSRMRoutingBackend:
    """The legacy FOSSGIS OSRM car endpoint, without legacy process/AppData."""
    URL = 'https://routing.openstreetmap.de/routed-car'
    USER_AGENT = 'AURA-Native/1.0 (personal desktop routing)'
    _lock = threading.Lock()
    _last_request = 0.0

    def route(self, origin: RoutePlace, destination: RoutePlace) -> dict:
        points = f'{origin.longitude:.6f},{origin.latitude:.6f};{destination.longitude:.6f},{destination.latitude:.6f}'
        query = urlencode({'overview': 'full', 'geometries': 'geojson', 'steps': 'true', 'alternatives': 'false'})
        request = Request(f'{self.URL}/route/v1/driving/{points}?{query}', headers={
            'User-Agent': self.USER_AGENT, 'Accept': 'application/json', 'Accept-Language': 'fr,en;q=0.8'})
        # The public service asks for no more than one request per second.
        with self._lock:
            wait = 1.05 - (time.monotonic() - self._last_request)
            if wait > 0: time.sleep(wait)
            type(self)._last_request = time.monotonic()
        try:
            with urlopen(request, timeout=15) as response:
                if getattr(response, 'status', 200) != 200: raise RoutingError('provider_unavailable')
                raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024: raise RoutingError('invalid_result')
            payload = json.loads(raw)
        except HTTPError as exc:
            if exc.code == 429: raise RoutingError('rate_limited') from exc
            raise RoutingError('provider_unavailable') from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise RoutingError('network_error') from exc
        except (ValueError, UnicodeError) as exc:
            raise RoutingError('invalid_result') from exc
        if not isinstance(payload, dict): raise RoutingError('invalid_result')
        if payload.get('code') == 'NoRoute': raise RoutingError('no_route')
        if payload.get('code') != 'Ok': raise RoutingError('provider_unavailable')
        routes = payload.get('routes') or []
        if not isinstance(routes, list): raise RoutingError('invalid_result')
        if not routes: raise RoutingError('no_route')
        if not isinstance(routes[0], dict): raise RoutingError('invalid_result')
        return routes[0]


class FakeRoutingBackend:
    """Explicitly offline test backend; distances and durations are fixtures."""
    def __init__(self, route, error=None):
        self.response = route
        self.error = error
        self.calls = []

    def route(self, origin, destination):
        self.calls.append((origin, destination))
        if self.error: raise RoutingError(self.error)
        return self.response


class RoutingService:
    def __init__(self, backend: RoutingBackend): self.backend = backend

    @staticmethod
    def _valid(place, missing):
        if place is None: raise RoutingError(missing)
        try: lat, lon = float(place.latitude), float(place.longitude)
        except (TypeError, ValueError, AttributeError) as exc: raise RoutingError('invalid_location') from exc
        if not (math.isfinite(lat) and math.isfinite(lon) and -84 <= lat <= 84 and -180 <= lon <= 180):
            raise RoutingError('invalid_location')

    def calculate(self, origin: RoutePlace | None, destination: RoutePlace | None) -> RouteResult:
        self._valid(origin, 'origin_missing')
        self._valid(destination, 'destination_missing')
        if abs(origin.latitude-destination.latitude) < 1e-6 and abs(origin.longitude-destination.longitude) < 1e-6:
            raise RoutingError('same_origin_destination')
        raw = self.backend.route(origin, destination)
        try:
            distance, duration = float(raw['distance']), float(raw['duration'])
            geometry = raw['geometry']
            points = geometry['coordinates'] if isinstance(geometry, dict) and geometry.get('type') == 'LineString' else geometry
            coordinates = tuple((float(point[0]), float(point[1])) for point in points)
            if len(coordinates) < 2 or not all(math.isfinite(x) and math.isfinite(y) and -180 <= x <= 180 and -90 <= y <= 90 for x, y in coordinates):
                raise ValueError('coordinates')
            if not (math.isfinite(distance) and distance > 0 and math.isfinite(duration) and duration > 0):
                raise ValueError('metrics')
            instructions = tuple(self._instruction(step) for leg in raw.get('legs', ()) for step in leg.get('steps', ()) if step)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise RoutingError('invalid_result') from exc
        return RouteResult(origin, destination, distance, duration, coordinates, tuple(x for x in instructions if x))

    @staticmethod
    def _instruction(step):
        maneuver = step.get('maneuver') or {}
        kind = str(maneuver.get('type') or '').lower()
        side = str(maneuver.get('modifier') or '').lower()
        road = str(step.get('name') or '').strip()
        verb = {'depart': 'Départ', 'arrive': 'Arrivée', 'turn': 'Tourner',
                'continue': 'Continuer', 'merge': 'Rejoindre', 'fork': 'Prendre la bifurcation'}.get(kind, 'Continuer')
        direction = {'left': ' à gauche', 'right': ' à droite', 'slight left': ' légèrement à gauche',
                     'slight right': ' légèrement à droite', 'straight': ' tout droit'}.get(side, '')
        return verb + direction + (f' · {road}' if road else '')
