from __future__ import annotations

# AURA P0.5.2.3.2 WEATHER ERROR DIAGNOSTICS
import logging
_aura_weather_log = logging.getLogger(__name__)

# AURA P0.5.2.1 WEATHER GEOSPATIAL PAYLOAD

import math
import time
import urllib.parse
from datetime import datetime

from config.settings import settings
from tools.models import ToolResult, ToolSource
from tools.safe_http import SafeHTTPClient, SafeHTTPError
from tools.geo_resolver import resolve_geo_entity


_WEATHER_LABELS = {
    0: "ciel dégagé", 1: "principalement dégagé", 2: "partiellement nuageux", 3: "couvert",
    45: "brouillard", 48: "brouillard givrant", 51: "bruine légère", 53: "bruine modérée",
    55: "bruine forte", 61: "pluie légère", 63: "pluie modérée", 65: "forte pluie",
    71: "neige légère", 73: "neige modérée", 75: "fortes chutes de neige", 80: "averses légères",
    81: "averses modérées", 82: "fortes averses", 95: "orage", 96: "orage avec grêle légère",
    99: "orage avec forte grêle",
}


class WeatherTool:
    GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST = "https://api.open-meteo.com/v1/forecast"
    AIR_QUALITY = "https://air-quality-api.open-meteo.com/v1/air-quality"

    def __init__(self, client: SafeHTTPClient):
        self.client = client
        # Weather-map fields are an optional visual enhancement. Cache them
        # briefly so reopening the same city or scrubbing the timeline never
        # causes a burst of identical network calls.
        self._map_field_cache: dict[tuple, tuple[float, dict]] = {}

    @staticmethod
    def _checked_at() -> str:
        return datetime.now().astimezone().isoformat(timespec="minutes")

    def _geocode(self, location: str) -> dict:
        query = urllib.parse.urlencode({"name": location, "count": 1, "language": "fr", "format": "json"})
        payload, _ = self.client.get_json(f"{self.GEOCODE}?{query}")
        results = payload.get("results") or []
        if not results or not isinstance(results[0], dict):
            raise SafeHTTPError(f"Je n'ai pas trouvé de lieu correspondant à « {location} ».")
        return results[0]

    def fetch_map_field(
        self, center_lat: float, center_lon: float, *, rows: int = 5, cols: int = 5,
        lat_span: float = 5.0, forecast_hours: int = 25, cache_ttl: float = 600.0,
    ) -> dict:
        """Fetch one bounded, multi-coordinate Open-Meteo field for the map.

        This is a sampled forecast field, not radar imagery.  A 5x5 grid is
        intentionally small enough for the Weather Workspace while still
        providing genuine spatial variation for temperature/rain/cloud/wind.
        Open-Meteo accepts comma-separated coordinate lists, so all samples are
        retrieved in one request.
        """
        center_lat = max(-85.0, min(85.0, float(center_lat)))
        center_lon = max(-180.0, min(180.0, float(center_lon)))
        rows = max(3, min(7, int(rows)))
        cols = max(3, min(7, int(cols)))
        forecast_hours = max(1, min(48, int(forecast_hours)))
        lat_span = max(1.0, min(10.0, float(lat_span)))
        # Keep the physical width roughly comparable to the north/south span.
        cos_lat = max(0.40, abs(math.cos(math.radians(center_lat))))
        lon_span = min(12.0, lat_span * 1.35 / cos_lat)
        cache_key = (round(center_lat, 2), round(center_lon, 2), rows, cols, round(lat_span, 1), forecast_hours)
        cached = self._map_field_cache.get(cache_key)
        if cached and (time.monotonic() - cached[0]) <= float(cache_ttl):
            return dict(cached[1])

        samples: list[tuple[float, float]] = []
        for r in range(rows):
            fy = (r / (rows - 1)) - 0.5
            lat = max(-85.0, min(85.0, center_lat - fy * lat_span))
            for c in range(cols):
                fx = (c / (cols - 1)) - 0.5
                lon = center_lon + fx * lon_span
                if lon > 180.0:
                    lon -= 360.0
                elif lon < -180.0:
                    lon += 360.0
                samples.append((lat, lon))

        params = {
            "latitude": ",".join(f"{lat:.4f}" for lat, _ in samples),
            "longitude": ",".join(f"{lon:.4f}" for _, lon in samples),
            "timezone": "auto",
            "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,pressure_msl",
            "forecast_hours": str(forecast_hours),
        }
        request_url = f"{self.FORECAST}?{urllib.parse.urlencode(params)}"
        try:
            payload, _response = self.client.get_json(request_url, allow_list=True)
        except TypeError:
            payload, _response = self.client.get_json(request_url)
        payloads = payload if isinstance(payload, list) else [payload]
        if len(payloads) != len(samples):
            raise SafeHTTPError("Le champ météo régional reçu est incomplet.")

        points: list[dict] = []
        shared_times: list[str] = []
        for index, ((lat, lon), item) in enumerate(zip(samples, payloads)):
            hourly = (item or {}).get("hourly") or {}
            times = list(hourly.get("time") or [])[:forecast_hours]
            if index == 0:
                shared_times = [str(v) for v in times]
            temperatures = hourly.get("temperature_2m") or []
            rain = hourly.get("precipitation_probability") or []
            wind_speed = hourly.get("wind_speed_10m") or []
            wind_direction = hourly.get("wind_direction_10m") or []
            wind_gusts = hourly.get("wind_gusts_10m") or []
            cloud = hourly.get("cloud_cover") or []
            pressure = hourly.get("pressure_msl") or []
            hours: list[dict] = []
            for h, stamp in enumerate(times):
                hours.append({
                    "time": stamp,
                    "temperature": temperatures[h] if h < len(temperatures) else None,
                    "rain_probability": rain[h] if h < len(rain) else None,
                    "wind_speed": wind_speed[h] if h < len(wind_speed) else None,
                    "wind_direction": wind_direction[h] if h < len(wind_direction) else None,
                    "wind_gusts": wind_gusts[h] if h < len(wind_gusts) else None,
                    "cloud_cover": cloud[h] if h < len(cloud) else None,
                    "pressure": pressure[h] if h < len(pressure) else None,
                })
            points.append({"latitude": lat, "longitude": lon, "hours": hours})

        field = {
            "source": "open-meteo",
            "kind": "sampled-forecast-field",
            "rows": rows, "cols": cols,
            "center_latitude": center_lat, "center_longitude": center_lon,
            "lat_span": lat_span, "lon_span": lon_span,
            "times": shared_times, "points": points,
            "forecast_hours": forecast_hours,
        }
        self._map_field_cache[cache_key] = (time.monotonic(), field)
        return dict(field)

    def _air_quality(self, lat: float, lon: float) -> tuple[dict, ToolSource | None]:
        try:
            params = {
                "latitude": f"{lat:.5f}", "longitude": f"{lon:.5f}", "timezone": "auto",
                "current": "european_aqi,pm2_5,pm10",
            }
            payload, response = self.client.get_json(f"{self.AIR_QUALITY}?{urllib.parse.urlencode(params)}")
            current = payload.get("current") or {}
            data = {
                "european_aqi": current.get("european_aqi"),
                "pm2_5": current.get("pm2_5"),
                "pm10": current.get("pm10"),
            }
            source = ToolSource(
                "Open-Meteo Air Quality",
                urllib.parse.urlsplit(response.url).hostname or "air-quality-api.open-meteo.com",
                self._checked_at(), response.url,
            )
            return data, source
        except Exception:
            # AQI is an enhancement only. Weather must still render if this
            # secondary endpoint is unavailable or not covered at a location.
            return {}, None

    def execute(self, location: str, *, tomorrow: bool = False) -> ToolResult:
        location = (location or "").strip(" ,.?\t\r\n")
        geo = resolve_geo_entity(location)
        location = geo.canonical or location
        if len(location) < 2:
            return ToolResult(False, "Indique-moi une ville ou un lieu pour que je puisse vérifier la météo.", "weather", "missing_location")
        try:
            place = self._geocode(location)
            return self._execute_resolved(place, location=location, geo=geo, tomorrow=tomorrow)
        except (SafeHTTPError, KeyError, TypeError, ValueError) as exc:
            message = str(exc) if isinstance(exc, SafeHTTPError) else "Les données météo reçues sont incomplètes."
            return ToolResult(False, f"Je n'ai pas pu vérifier la météo : {message}", "weather", "weather_error")

    def execute_coordinates(self, latitude: float, longitude: float, *, label: str = "Position actuelle", tomorrow: bool = False) -> ToolResult:
        """Use fresh device coordinates without inferring a fixed city."""
        try:
            lat, lon = float(latitude), float(longitude)
        except (TypeError, ValueError):
            return ToolResult(False, "La position actuelle reçue est invalide.", "weather", "invalid_coordinates")
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return ToolResult(False, "La position actuelle reçue est hors limites.", "weather", "invalid_coordinates")
        place = {"name": "Position actuelle", "admin1": "", "country": "", "latitude": lat, "longitude": lon}
        geo = resolve_geo_entity("Position actuelle", fuzzy=False)
        try:
            result = self._execute_resolved(place, location="Position actuelle", geo=geo, tomorrow=tomorrow)
            if isinstance(getattr(result, "data", None), dict):
                result.data["location_source"] = "device_geolocation"
                result.data["current_position"] = True
            return result
        except (SafeHTTPError, KeyError, TypeError, ValueError) as exc:
            message = str(exc) if isinstance(exc, SafeHTTPError) else "Les données météo reçues sont incomplètes."
            return ToolResult(False, f"Je n'ai pas pu vérifier la météo : {message}", "weather", "weather_error")

    def _execute_resolved(self, place: dict, *, location: str, geo, tomorrow: bool = False) -> ToolResult:
        lat, lon = float(place["latitude"]), float(place["longitude"])
        params = {"latitude": f"{lat:.5f}", "longitude": f"{lon:.5f}", "timezone": "auto"}
        if tomorrow:
            params.update({
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "forecast_days": "2",
            })
        else:
            params.update({
                "current": (
                    "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,"
                    "wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,pressure_msl,surface_pressure,visibility,dew_point_2m"
                ),
                "hourly": "precipitation_probability",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
                "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,pressure_msl",
                "forecast_days": "8",
            })
        url = f"{self.FORECAST}?{urllib.parse.urlencode(params)}"
        payload, response = self.client.get_json(url)
        name = str(place.get("name") or location)
        admin = str(place.get("admin1") or "").strip()
        country = str(place.get("country") or "").strip()
        place_label = ", ".join(part for part in (name, admin, country) if part)
        checked = self._checked_at()
        data: dict = {
            "location": name, "place_label": place_label, "latitude": lat, "longitude": lon,
            "geo_input": geo.raw, "geo_canonical": geo.canonical, "geo_kind": geo.kind, "geo_confidence": geo.confidence,
            "tomorrow": bool(tomorrow), "checked_at": checked,
        }
        sources = [ToolSource("Open-Meteo", urllib.parse.urlsplit(response.url).hostname or "open-meteo.com", checked, response.url)]

        if tomorrow:
            daily = payload.get("daily") or {}
            dates = daily.get("time") or []
            idx = 1 if len(dates) > 1 else 0
            code = int((daily.get("weather_code") or [3])[idx])
            tmax = float((daily.get("temperature_2m_max") or [0])[idx])
            tmin = float((daily.get("temperature_2m_min") or [0])[idx])
            probs = daily.get("precipitation_probability_max") or []
            prob = int(probs[idx]) if len(probs) > idx and probs[idx] is not None else None
            weather = _WEATHER_LABELS.get(code, "conditions variables")
            data.update({"weather_code": code, "condition": weather, "temp_max": tmax, "temp_min": tmin, "precip_probability": prob})
            rain_sentence = f" Le risque maximal de précipitations est de {prob}%." if prob is not None else ""
            answer = (
                f"Demain à {place_label}, Open-Meteo prévoit {weather}. "
                f"Les températures seront comprises entre {tmin:.0f} et {tmax:.0f} °C.{rain_sentence} "
                f"Prévision vérifiée à {datetime.now().astimezone().strftime('%H:%M')}."
            )
            if settings.WEATHER_VOICE_CONCISE:
                spoken_parts = [f"Demain à {name}, {weather}", f"{tmin:.0f} à {tmax:.0f} degrés"]
                if prob is not None and prob >= settings.WEATHER_VOICE_RAIN_PROB_THRESHOLD:
                    spoken_parts.append(f"Risque de pluie : {prob}%")
                spoken = ". ".join(spoken_parts) + "."
            else:
                speech_rain = f" Risque de pluie : {prob}%." if prob is not None else ""
                # Sources remain attached to ToolResult/HUD; they are never
                # recited in spoken weather output.
                spoken = f"Demain à {name}, {weather}. Températures entre {tmin:.0f} et {tmax:.0f} degrés Celsius.{speech_rain}"
        else:
            current = payload.get("current") or {}
            daily = payload.get("daily") or {}
            temp = float(current.get("temperature_2m"))
            apparent = float(current.get("apparent_temperature"))
            humidity = int(current.get("relative_humidity_2m"))
            wind = float(current.get("wind_speed_10m"))
            wind_direction_now = float(current.get("wind_direction_10m")) if current.get("wind_direction_10m") is not None else None
            wind_gusts_now = float(current.get("wind_gusts_10m")) if current.get("wind_gusts_10m") is not None else None
            cloud_cover_now = float(current.get("cloud_cover")) if current.get("cloud_cover") is not None else None
            pressure_msl_now = float(current.get("pressure_msl")) if current.get("pressure_msl") is not None else None
            precip = float(current.get("precipitation"))
            pressure = float(current.get("surface_pressure")) if current.get("surface_pressure") is not None else None
            visibility_m = float(current.get("visibility")) if current.get("visibility") is not None else None
            dew_point = float(current.get("dew_point_2m")) if current.get("dew_point_2m") is not None else None
            code = int(current.get("weather_code", 3))
            weather = _WEATHER_LABELS.get(code, "conditions variables")
            highs = daily.get("temperature_2m_max") or []
            lows = daily.get("temperature_2m_min") or []
            probs = daily.get("precipitation_probability_max") or []
            hourly = payload.get("hourly") or {}
            hourly_times = hourly.get("time") or []
            hourly_probs = hourly.get("precipitation_probability") or []
            rain_prob_now = None
            current_time = str(current.get("time") or "")
            if current_time and hourly_times and hourly_probs:
                # Open-Meteo current timestamps are aligned to a local hour.
                # Match the exact hour when possible; otherwise use the nearest
                # preceding hourly slot. This is distinct from the daily maximum.
                current_hour = current_time[:13]
                matches = [i for i, stamp in enumerate(hourly_times) if str(stamp)[:13] == current_hour]
                if matches:
                    idx_now = matches[0]
                    if idx_now < len(hourly_probs) and hourly_probs[idx_now] is not None:
                        rain_prob_now = int(hourly_probs[idx_now])
            rain_prob_day_max = int(probs[0]) if probs and probs[0] is not None else None
            aqi, aqi_source = self._air_quality(lat, lon)
            if aqi_source is not None:
                sources.append(aqi_source)
            # Rich workspace payload: keep the compact legacy keys while
            # exposing a bounded 8-day / 48-hour visual dataset for the
            # standalone Weather application. This remains deterministic
            # Open-Meteo data; no LLM is used to build the forecast cards.
            daily_rows = []
            daily_times = daily.get("time") or []
            daily_codes = daily.get("weather_code") or []
            daily_max = daily.get("temperature_2m_max") or []
            daily_min = daily.get("temperature_2m_min") or []
            daily_rain = daily.get("precipitation_probability_max") or []
            daily_sunrise = daily.get("sunrise") or []
            daily_sunset = daily.get("sunset") or []
            for i, day in enumerate(daily_times[:8]):
                daily_rows.append({
                    "date": day,
                    "weather_code": daily_codes[i] if i < len(daily_codes) else None,
                    "temp_max": daily_max[i] if i < len(daily_max) else None,
                    "temp_min": daily_min[i] if i < len(daily_min) else None,
                    "rain_probability": daily_rain[i] if i < len(daily_rain) else None,
                    "sunrise": daily_sunrise[i] if i < len(daily_sunrise) else None,
                    "sunset": daily_sunset[i] if i < len(daily_sunset) else None,
                })
            hourly_rows = []
            hourly_temp = hourly.get("temperature_2m") or []
            hourly_rain = hourly.get("precipitation_probability") or []
            hourly_wind = hourly.get("wind_speed_10m") or []
            hourly_wind_direction = hourly.get("wind_direction_10m") or []
            hourly_wind_gusts = hourly.get("wind_gusts_10m") or []
            hourly_cloud = hourly.get("cloud_cover") or []
            hourly_pressure = hourly.get("pressure_msl") or []
            for i, stamp in enumerate((hourly.get("time") or [])[:48]):
                hourly_rows.append({
                    "time": stamp,
                    "temperature": hourly_temp[i] if i < len(hourly_temp) else None,
                    "rain_probability": hourly_rain[i] if i < len(hourly_rain) else None,
                    "wind_speed": hourly_wind[i] if i < len(hourly_wind) else None,
                    "wind_direction": hourly_wind_direction[i] if i < len(hourly_wind_direction) else None,
                    "wind_gusts": hourly_wind_gusts[i] if i < len(hourly_wind_gusts) else None,
                    "cloud_cover": hourly_cloud[i] if i < len(hourly_cloud) else None,
                    "pressure": hourly_pressure[i] if i < len(hourly_pressure) else None,
                })

            data.update({
                "weather_code": code, "condition": weather, "temperature": temp, "apparent": apparent,
                "humidity": humidity, "wind_speed": wind, "wind_direction": wind_direction_now,
                "wind_gusts": wind_gusts_now, "cloud_cover": cloud_cover_now, "pressure_msl": pressure_msl_now,
                "precipitation": precip,
                "pressure": pressure, "visibility_km": (visibility_m / 1000.0 if visibility_m is not None else None),
                "dew_point": dew_point,
                "temp_max": float(highs[0]) if highs else None, "temp_min": float(lows[0]) if lows else None,
                # Keep the legacy key for visual/backward compatibility, but
                # make the semantics explicit for all new UI/voice code.
                "precip_probability": rain_prob_day_max,
                "rain_probability_now": rain_prob_now,
                "rain_probability_today_max": rain_prob_day_max,
                "daily_forecast": daily_rows,
                "hourly_forecast": hourly_rows,
                "sunrise": daily_sunrise[0] if daily_sunrise else None,
                "sunset": daily_sunset[0] if daily_sunset else None,
                **aqi,
            })
            answer = (
                f"À {place_label}, il fait actuellement {temp:.1f} °C. Conditions actuelles : {weather}. "
                f"Le ressenti est de {apparent:.1f} °C. L'humidité est de {humidity}%, et le vent souffle à {wind:.0f} km/h. "
                f"Les précipitations actuelles sont de {precip:.1f} mm. Source : Open-Meteo, vérifiée à {datetime.now().astimezone().strftime('%H:%M')}."
            )
            if settings.WEATHER_VOICE_CONCISE:
                spoken_parts = [f"À {name}, {temp:.0f} degrés, {weather}"]
                if abs(apparent - temp) >= settings.WEATHER_VOICE_FEELS_LIKE_DELTA_C:
                    spoken_parts.append(f"ressenti {apparent:.0f}")
                if precip > 0.05:
                    spoken_parts.append("Pluie en cours")
                else:
                    # Never present the daily maximum as if it were the
                    # immediate rain probability. Humidity is unrelated and
                    # remains a separate HUD metric.
                    if rain_prob_now is not None and rain_prob_now >= settings.WEATHER_VOICE_RAIN_PROB_THRESHOLD:
                        spoken_parts.append(f"Risque de pluie maintenant : {rain_prob_now}%")
                    else:
                        spoken_parts.append("Pas de pluie actuellement")
                        if rain_prob_day_max is not None and rain_prob_day_max >= settings.WEATHER_VOICE_RAIN_PROB_THRESHOLD:
                            spoken_parts.append("Averses possibles plus tard aujourd'hui")
                if wind >= settings.WEATHER_VOICE_WIND_THRESHOLD_KMH:
                    spoken_parts.append(f"vent {wind:.0f} kilomètres heure")
                spoken = ". ".join(spoken_parts) + "."
            else:
                rain_spoken = "Pas de pluie actuellement." if precip <= 0.05 else f"Précipitations : {precip:.1f} millimètres."
                spoken = f"À {name}, {temp:.1f} degrés, {weather}. Vent {wind:.0f} kilomètres par heure. {rain_spoken}"
        if not data.get("weather_field"):
            try:
                data["weather_field"] = self.fetch_map_field(lat, lon, rows=5, cols=5, lat_span=5.0, forecast_hours=25)
            except Exception:
                data["weather_field"] = {}
        return ToolResult(True, answer, "weather", "open-meteo", tuple(sources), spoken, data=data)
