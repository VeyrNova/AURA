from __future__ import annotations
import time
from aura_native.weather.models import WeatherCurrent, WeatherDaily, WeatherLocation, WeatherReport
from aura_native.weather.provider import WeatherProviderError

_CODE = {0:"clear",1:"partly_cloudy",2:"partly_cloudy",3:"cloudy",45:"fog",48:"fog",51:"drizzle",53:"drizzle",55:"drizzle",56:"drizzle",57:"drizzle",61:"rain",63:"rain",65:"rain",66:"rain",67:"rain",71:"snow",73:"snow",75:"snow",77:"snow",80:"rain",81:"rain",82:"rain",85:"snow",86:"snow",95:"thunderstorm",96:"thunderstorm",99:"thunderstorm"}
def condition_for(code):
    try: return _CODE.get(int(code), "unknown")
    except (TypeError, ValueError): return "unknown"

class WeatherService:
    def __init__(self, provider, *, cache_seconds: float = 300.0, clock=time.monotonic): self.provider, self.cache_seconds, self.clock, self._cache = provider, float(cache_seconds), clock, {}
    def _location(self, query):
        value = str(query or "").strip()
        if len(value) < 2: raise WeatherProviderError("weather_location_not_found", "Weather location is required")
        data = self.provider.geocode(value); results = data.get("results") if isinstance(data, dict) else None
        if not results: raise WeatherProviderError("weather_location_not_found", "Weather location was not found")
        row = results[0]
        try: return WeatherLocation(str(row["name"]), str(row.get("country") or ""), float(row["latitude"]), float(row["longitude"]), str(row.get("timezone") or "UTC"))
        except (KeyError, TypeError, ValueError) as exc: raise WeatherProviderError("weather_invalid_response", "Weather location data is invalid") from exc
    def search_locations(self, query):
        value = str(query or "").strip()
        if len(value) < 2: return ()
        data = self.provider.geocode(value)
        results = data.get("results") if isinstance(data, dict) else None
        if not results: return ()
        out = []
        for row in results:
            try:
                out.append(WeatherLocation(str(row["name"]), str(row.get("country") or ""), float(row["latitude"]), float(row["longitude"]), str(row.get("timezone") or "UTC")))
            except (KeyError, TypeError, ValueError):
                continue
        return tuple(out)
    def get_forecast(self, location, days=2):
        place = location if isinstance(location, WeatherLocation) else self._location(location)
        key = (place.name.casefold().strip(), max(1, min(int(days), 7))); cached = self._cache.get(key)
        if cached and self.clock() - cached[0] < self.cache_seconds: return cached[1]
        data = self.provider.forecast(place.latitude, place.longitude, key[1])
        try:
            current_row = data.get("current") or {}; daily_row = data.get("daily") or {}
            current = WeatherCurrent(float(current_row["temperature_2m"]), float(current_row["apparent_temperature"]) if current_row.get("apparent_temperature") is not None else None, condition_for(current_row.get("weather_code")), int(current_row.get("weather_code", -1)), float(current_row["wind_speed_10m"]) if current_row.get("wind_speed_10m") is not None else None, int(current_row["relative_humidity_2m"]) if current_row.get("relative_humidity_2m") is not None else None, str(current_row.get("time") or "") or None)
            daily=[]
            for index, date in enumerate(daily_row.get("time") or []):
                code=(daily_row.get("weather_code") or [])[index] if index < len(daily_row.get("weather_code") or []) else -1
                value=lambda name: (daily_row.get(name) or [])[index] if index < len(daily_row.get(name) or []) else None
                daily.append(WeatherDaily(str(date), float(value("temperature_2m_min")) if value("temperature_2m_min") is not None else None, float(value("temperature_2m_max")) if value("temperature_2m_max") is not None else None, condition_for(code), int(code), int(value("precipitation_probability_max")) if value("precipitation_probability_max") is not None else None, str(value("sunrise") or "") or None, str(value("sunset") or "") or None))
        except (KeyError, TypeError, ValueError, IndexError) as exc: raise WeatherProviderError("weather_invalid_response", "Weather forecast data is invalid") from exc
        report=WeatherReport(place, current, tuple(daily)); self._cache[key]=(self.clock(), report); return report
    def get_current(self, location): return self.get_forecast(location, 1)
    def get_day(self, location, date):
        report=self.get_forecast(location, 7)
        for day in report.daily:
            if day.date == str(date): return report, day
        raise WeatherProviderError("weather_invalid_response", "Requested forecast day is unavailable")
