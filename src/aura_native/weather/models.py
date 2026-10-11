from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class WeatherLocation:
    name: str; country: str; latitude: float; longitude: float; timezone: str
    @property
    def label(self): return ", ".join(part for part in (self.name, self.country) if part)

@dataclass(frozen=True)
class WeatherCurrent:
    temperature_c: float; apparent_temperature_c: float | None; condition: str; weather_code: int
    wind_speed_kmh: float | None; humidity_percent: int | None; observed_at: str | None

@dataclass(frozen=True)
class WeatherDaily:
    date: str; min_temperature_c: float | None; max_temperature_c: float | None; condition: str
    weather_code: int; precipitation_probability_percent: int | None; sunrise: str | None = None; sunset: str | None = None

@dataclass(frozen=True)
class WeatherReport:
    location: WeatherLocation; current: WeatherCurrent | None; daily: tuple[WeatherDaily, ...]; source: str = "open-meteo"
    def as_payload(self):
        return {"location": {"name": self.location.name, "country": self.location.country, "latitude": self.location.latitude, "longitude": self.location.longitude, "timezone": self.location.timezone, "label": self.location.label}, "current": None if self.current is None else self.current.__dict__.copy(), "daily": tuple(day.__dict__.copy() for day in self.daily), "source": self.source, "units": {"temperature": "celsius", "wind_speed": "kmh", "precipitation": "mm"}}
