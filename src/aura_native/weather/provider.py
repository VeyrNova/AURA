"""Open-Meteo boundary using only the standard library."""
from __future__ import annotations
import json
from urllib import error, parse, request

class WeatherProviderError(Exception):
    def __init__(self, code: str, message: str): self.code, self.message = code, message; super().__init__(message)

class OpenMeteoProvider:
    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
    forecast_url = "https://api.open-meteo.com/v1/forecast"
    def __init__(self, *, opener=request.urlopen, timeout_seconds: float = 8.0): self._open, self.timeout_seconds = opener, float(timeout_seconds)
    def _json(self, base, params):
        url = base + "?" + parse.urlencode(params)
        try:
            with self._open(request.Request(url, headers={"Accept":"application/json", "User-Agent":"AURA-Native/6A"}), timeout=self.timeout_seconds) as response: raw = response.read()
        except TimeoutError as exc: raise WeatherProviderError("weather_timeout", "Weather provider timed out") from exc
        except error.HTTPError as exc: raise WeatherProviderError("weather_provider_unavailable", "Weather provider is unavailable") from exc
        except error.URLError as exc: raise WeatherProviderError("weather_network_error", "Weather provider connection failed") from exc
        try: return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc: raise WeatherProviderError("weather_invalid_response", "Weather provider returned invalid data") from exc
    def geocode(self, location): return self._json(self.geocoding_url, {"name": location, "count": 1, "language": "fr", "format": "json"})
    def forecast(self, latitude, longitude, days):
        return self._json(self.forecast_url, {"latitude": latitude, "longitude": longitude, "timezone": "auto", "forecast_days": max(1, min(int(days), 7)), "temperature_unit": "celsius", "wind_speed_unit": "kmh", "precipitation_unit": "mm", "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m", "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset"})

class FakeWeatherProvider:
    """Deterministic offline weather source for native tests."""
    def __init__(self, *, geocode_payload=None, forecast_payload=None, failure=None):
        self.geocode_payload = {"results":[{"name":"Nice", "country":"France", "latitude":43.7, "longitude":7.25, "timezone":"Europe/Paris"}]} if geocode_payload is None else geocode_payload
        self.forecast_payload = {"current":{"temperature_2m":20.0,"apparent_temperature":19.0,"relative_humidity_2m":65,"weather_code":2,"wind_speed_10m":11.0,"time":"2026-09-28T10:00"},"daily":{"time":["2026-09-28","2026-09-29"],"weather_code":[2,61],"temperature_2m_max":[23.0,24.0],"temperature_2m_min":[16.0,17.0],"precipitation_probability_max":[10,70],"sunrise":["2026-09-28T07:20","2026-09-29T07:21"],"sunset":["2026-09-28T19:20","2026-09-29T19:18"]}} if forecast_payload is None else forecast_payload
        self.failure = failure; self.calls=[]
    def geocode(self, location): self.calls.append(("geocode", location)); self._raise(); return self.geocode_payload
    def forecast(self, latitude, longitude, days): self.calls.append(("forecast", latitude, longitude, days)); self._raise(); return self.forecast_payload
    def _raise(self):
        if self.failure: raise self.failure
