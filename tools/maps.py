from __future__ import annotations

import re
import urllib.parse
from datetime import datetime

from tools.models import ToolResult, ToolSource
from tools.safe_http import SafeHTTPClient, SafeHTTPError


def format_duration_minutes(value) -> str:
    """Format a route duration for human display.

    Durations up to and including 60 minutes stay in minutes. Once the
    duration exceeds 60 minutes, AURA switches to hours + zero-padded minutes
    (for example 532 -> ``8 h 52 min`` and 61 -> ``1 h 01 min``).
    """
    try:
        total = max(0, int(round(float(value))))
    except (TypeError, ValueError):
        return "—"
    if total <= 60:
        return f"{total} min"
    hours, minutes = divmod(total, 60)
    return f"{hours} h {minutes:02d} min"


class MapsTool:
    """Controlled geocoding + lightweight routing helper.

    Place resolution uses Open-Meteo geocoding. When both endpoints are known
    and the requested mode is driving, AURA also requests a display geometry
    from the public OSRM-compatible route endpoint. Google Maps remains the
    final navigation handoff and therefore still works if integrated routing is
    temporarily unavailable.
    """

    GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
    ROUTE = "https://router.project-osrm.org/route/v1/driving"

    def __init__(self, client: SafeHTTPClient, *, default_origin: str = ""):
        self.client = client
        self.default_origin = str(default_origin or "").strip()

    @staticmethod
    def _checked_at() -> str:
        return datetime.now().astimezone().isoformat(timespec="minutes")

    def _geocode(self, query: str) -> tuple[dict, ToolSource]:
        params = urllib.parse.urlencode({"name": query, "count": 1, "language": "fr", "format": "json"})
        payload, response = self.client.get_json(f"{self.GEOCODE}?{params}")
        rows = payload.get("results") or []
        if not rows or not isinstance(rows[0], dict):
            raise SafeHTTPError(f"Je n'ai pas trouvé « {query} ».")
        row = rows[0]
        source = ToolSource(
            "Open-Meteo Geocoding",
            urllib.parse.urlsplit(response.url).hostname or "geocoding-api.open-meteo.com",
            self._checked_at(),
            response.url,
        )
        return row, source

    @staticmethod
    def _label(row: dict, fallback: str) -> str:
        parts = [
            str(row.get("name") or fallback).strip(),
            str(row.get("admin1") or "").strip(),
            str(row.get("country") or "").strip(),
        ]
        return ", ".join(p for p in parts if p)

    @staticmethod
    def _coordinates(row: dict) -> tuple[float, float]:
        return float(row["latitude"]), float(row["longitude"])

    @staticmethod
    def _decimate(points: list[list[float]], maximum: int = 700) -> list[list[float]]:
        if len(points) <= maximum:
            return points
        step = max(1, len(points) // maximum)
        reduced = points[::step]
        if reduced[-1] != points[-1]:
            reduced.append(points[-1])
        return reduced

    def _route_driving(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
    ) -> tuple[dict, ToolSource]:
        coords = f"{origin_lon:.6f},{origin_lat:.6f};{destination_lon:.6f},{destination_lat:.6f}"
        query = urllib.parse.urlencode({"overview": "simplified", "geometries": "geojson", "steps": "false"})
        payload, response = self.client.get_json(f"{self.ROUTE}/{coords}?{query}")
        routes = payload.get("routes") or []
        if str(payload.get("code") or "").casefold() != "ok" or not routes or not isinstance(routes[0], dict):
            raise SafeHTTPError("Le moteur d'itinéraire n'a pas renvoyé de trajet exploitable.")
        route = routes[0]
        geometry = ((route.get("geometry") or {}).get("coordinates") or [])
        points: list[list[float]] = []
        for pair in geometry:
            try:
                lon, lat = float(pair[0]), float(pair[1])
                points.append([lat, lon])
            except Exception:
                continue
        if len(points) < 2:
            raise SafeHTTPError("Le tracé de l'itinéraire est vide.")
        source = ToolSource(
            "OSRM Routing",
            urllib.parse.urlsplit(response.url).hostname or "router.project-osrm.org",
            self._checked_at(),
            response.url,
        )
        return {
            "route_points": self._decimate(points),
            "distance_km": round(float(route.get("distance") or 0.0) / 1000.0, 1),
            "duration_min": max(1, int(round(float(route.get("duration") or 0.0) / 60.0))),
        }, source

    @staticmethod
    def search_url(query: str) -> str:
        return "https://www.google.com/maps/search/?" + urllib.parse.urlencode({"api": "1", "query": query})

    @staticmethod
    def directions_url(destination: str, *, origin: str = "", travelmode: str = "driving") -> str:
        params = {"api": "1", "destination": destination, "travelmode": travelmode}
        if origin:
            params["origin"] = origin
        return "https://www.google.com/maps/dir/?" + urllib.parse.urlencode(params)

    def locate(self, query: str) -> ToolResult:
        query = str(query or "").strip(" ,.?!")
        if not query:
            return ToolResult(False, "Indique-moi le lieu que tu veux localiser.", "maps", "missing_location")
        try:
            row, source = self._geocode(query)
            label = self._label(row, query)
            lat, lon = self._coordinates(row)
            url = self.search_url(label)
            response = f"J'ai localisé {label}. Coordonnées : {lat:.5f}, {lon:.5f}."
            return ToolResult(True, response, "maps", "google-maps-url", (source,), "", data={
                "mode": "location",
                "query": query,
                "label": label,
                "latitude": lat,
                "longitude": lon,
                "destination_coordinates": [lat, lon],
                "google_maps_url": url,
                "map_provider": "openstreetmap",
            })
        except (SafeHTTPError, KeyError, TypeError, ValueError) as exc:
            return ToolResult(False, f"Je n'ai pas pu localiser ce lieu : {exc}", "maps", "maps_error")

    def directions(self, destination: str, *, origin: str = "", travelmode: str = "driving") -> ToolResult:
        destination = str(destination or "").strip(" ,.?!")
        origin = str(origin or self.default_origin or "").strip(" ,.?!")
        travelmode = str(travelmode or "driving").strip().casefold()
        if not destination:
            return ToolResult(False, "Indique-moi la destination de l'itinéraire.", "maps", "missing_destination")

        url = self.directions_url(destination, origin=origin, travelmode=travelmode)
        sources: list[ToolSource] = []
        try:
            destination_row, destination_source = self._geocode(destination)
            sources.append(destination_source)
            destination_label = self._label(destination_row, destination)
            destination_lat, destination_lon = self._coordinates(destination_row)
            url = self.directions_url(destination_label, origin=origin, travelmode=travelmode)

            data = {
                "mode": "directions",
                "origin": origin,
                "origin_label": origin or "position actuelle de l'appareil",
                "destination": destination,
                "label": destination_label,
                "latitude": destination_lat,
                "longitude": destination_lon,
                "destination_coordinates": [destination_lat, destination_lon],
                "travelmode": travelmode,
                "google_maps_url": url,
                "map_provider": "openstreetmap",
            }

            # A real in-app route needs both endpoints. AURA deliberately does
            # not infer the user's device position without LOCATION_ACCESS.
            if origin:
                try:
                    origin_row, origin_source = self._geocode(origin)
                    sources.append(origin_source)
                    origin_label = self._label(origin_row, origin)
                    origin_lat, origin_lon = self._coordinates(origin_row)
                    data["origin_label"] = origin_label
                    data["origin_coordinates"] = [origin_lat, origin_lon]
                    data["google_maps_url"] = self.directions_url(destination_label, origin=origin_label, travelmode=travelmode)

                    if travelmode == "driving":
                        try:
                            route_data, route_source = self._route_driving(
                                origin_lat, origin_lon, destination_lat, destination_lon,
                            )
                            data.update(route_data)
                            data["route_provider"] = "osrm"
                            sources.append(route_source)
                        except SafeHTTPError as route_exc:
                            data["route_warning"] = str(route_exc)
                    else:
                        data["route_warning"] = "Le tracé intégré est actuellement réservé au mode voiture ; Google Maps gère le mode demandé."
                except (SafeHTTPError, KeyError, TypeError, ValueError) as origin_exc:
                    data["route_warning"] = f"Origine non résolue dans l'aperçu AURA : {origin_exc}"
            else:
                data["route_warning"] = "Origine non fournie : Google Maps pourra utiliser la position de l'appareil si elle est autorisée."

            distance = data.get("distance_km")
            duration = data.get("duration_min")
            if distance and duration:
                response = f"Itinéraire prêt vers {destination_label}, depuis {data['origin_label']} : {distance:.1f} km, environ {format_duration_minutes(duration)}."
            else:
                response = f"Itinéraire prêt vers {destination_label}, depuis {data['origin_label']}."
            return ToolResult(True, response, "maps", "google-maps-url", tuple(sources), "", data=data)

        except (SafeHTTPError, KeyError, TypeError, ValueError) as exc:
            # The universal Google Maps URL still accepts free-form locations.
            origin_label = origin or "position actuelle de l'appareil"
            return ToolResult(True, f"Itinéraire Google Maps prêt vers {destination}.", "maps", "google-maps-url", tuple(sources), "", data={
                "mode": "directions",
                "origin": origin,
                "origin_label": origin_label,
                "destination": destination,
                "label": destination,
                "travelmode": travelmode,
                "google_maps_url": url,
                "preview_warning": str(exc),
                "map_provider": "openstreetmap",
            })


def extract_maps_request(text: str) -> dict | None:
    raw = str(text or "").strip()
    norm = raw.casefold().replace("’", "'")
    mode = "driving"
    if any(k in norm for k in ("à pied", "a pied", "walking", "marche")):
        mode = "walking"
    elif any(k in norm for k in ("vélo", "velo", "bicycl", "bike")):
        mode = "bicycling"
    elif any(k in norm for k in ("transport", "transit", "bus", "train")):
        mode = "transit"

    # Directions with explicit origin and destination.
    m = re.search(r"(?:itin[ée]raire|trajet|route)\s+(?:de|depuis)\s+(.+?)\s+(?:à|a|vers|jusqu['’]à|jusqu'a)\s+(.+?)[?.!]*$", raw, re.I)
    if m:
        return {"action": "directions", "origin": m.group(1).strip(), "destination": m.group(2).strip(), "travelmode": mode}

    # Directions to a destination; Google Maps may use device position as origin.
    m = re.search(r"(?:itin[ée]raire|trajet|route|emm[eè]ne[- ]moi|guide[- ]moi)\s+(?:pour|vers|jusqu['’]à|jusqu'a|à|a)\s+(.+?)[?.!]*$", raw, re.I)
    if m:
        return {"action": "directions", "origin": "", "destination": m.group(1).strip(), "travelmode": mode}

    # Locate/show place on map.
    m = re.search(r"(?:localise|localiser|situe|situer|montre(?:-moi)?|affiche(?:-moi)?)\s+(.+?)\s+(?:sur\s+(?:la\s+)?carte|sur\s+google\s+maps)[?.!]*$", raw, re.I)
    if m:
        return {"action": "locate", "query": m.group(1).strip()}
    m = re.search(r"(?:o[uù]\s+se\s+trouve|o[uù]\s+est)\s+(.+?)[?.!]*$", raw, re.I)
    if m and not any(k in norm for k in ("météo", "meteo", "weather")):
        return {"action": "locate", "query": m.group(1).strip()}
    return None
