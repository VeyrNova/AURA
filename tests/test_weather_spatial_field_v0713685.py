import unittest
import urllib.parse
from pathlib import Path

from tools.weather import WeatherTool
from tools.safe_http import SafeHTTPClient, HTTPResponse

ROOT = Path(__file__).resolve().parents[1]


class _Response:
    url = "https://api.open-meteo.com/v1/forecast"


class _FieldClient:
    def __init__(self):
        self.urls = []

    def get_json(self, url):
        self.urls.append(url)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        lats = query["latitude"][0].split(",")
        lons = query["longitude"][0].split(",")
        hours = int(query["forecast_hours"][0])
        payload = []
        for index, (lat, lon) in enumerate(zip(lats, lons)):
            times = [f"2026-08-11T{(10+h)%24:02d}:00" for h in range(hours)]
            payload.append({
                "latitude": float(lat), "longitude": float(lon),
                "hourly": {
                    "time": times,
                    "temperature_2m": [18.0 + index * 0.1 + h * 0.05 for h in range(hours)],
                    "precipitation_probability": [(index * 3 + h) % 100 for h in range(hours)],
                    "wind_speed_10m": [12.0 + (index % 5) for _ in range(hours)],
                    "wind_direction_10m": [(index * 15 + h * 2) % 360 for h in range(hours)],
                    "cloud_cover": [(index * 4 + h) % 100 for h in range(hours)],
                },
            })
        return payload, _Response()


class WeatherSpatialFieldTests(unittest.TestCase):
    def test_one_multi_coordinate_request_builds_25_point_field(self):
        client = _FieldClient()
        field = WeatherTool(client).fetch_map_field(43.43, 6.43, rows=5, cols=5, forecast_hours=25)
        self.assertEqual(len(client.urls), 1)
        self.assertEqual(field["kind"], "sampled-forecast-field")
        self.assertEqual(field["rows"], 5)
        self.assertEqual(field["cols"], 5)
        self.assertEqual(len(field["points"]), 25)
        self.assertEqual(len(field["times"]), 25)
        self.assertEqual(len(field["points"][0]["hours"]), 25)

    def test_request_contains_wind_direction_and_forecast_hours(self):
        client = _FieldClient()
        WeatherTool(client).fetch_map_field(43.43, 6.43)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(client.urls[0]).query)
        self.assertEqual(query["forecast_hours"], ["25"])
        self.assertIn("wind_direction_10m", query["hourly"][0])
        self.assertEqual(len(query["latitude"][0].split(",")), 25)
        self.assertEqual(len(query["longitude"][0].split(",")), 25)

    def test_field_cache_avoids_duplicate_request(self):
        client = _FieldClient()
        tool = WeatherTool(client)
        first = tool.fetch_map_field(43.43, 6.43)
        second = tool.fetch_map_field(43.43, 6.43)
        self.assertEqual(len(client.urls), 1)
        self.assertEqual(len(first["points"]), len(second["points"]))

    def test_workspace_has_layer_and_timeline_controls(self):
        text = (ROOT / "ui" / "weather_workspace.py").read_text(encoding="utf-8")
        self.assertIn('((0,"Maintenant"),(3,"+3 h"),(6,"+6 h"),(12,"+12 h"),(24,"+24 h"))', text)
        self.assertIn("fetch_map_field", text)
        self.assertIn('"weather_field":field', text)
        self.assertIn('"preserve_map_zoom":True', text)

    def test_map_renders_sampled_field_and_real_wind_vectors(self):
        text = (ROOT / "ui" / "map_widget.py").read_text(encoding="utf-8")
        self.assertIn("def _draw_weather_field", text)
        self.assertIn("def _draw_wind_arrow", text)
        self.assertIn("wind_direction", text)
        self.assertIn("CARTE ANIMÉE · CHAMP 5×5", text)
        self.assertIn("set_weather_time_offset", text)
        self.assertIn("preserve_map_zoom", text)


    def test_safe_http_json_list_behavior(self):
        client = SafeHTTPClient()
        client.get = lambda *args, **kwargs: HTTPResponse(
            "https://api.open-meteo.com/v1/forecast", 200, "application/json", b"[{\"latitude\":43.4}]"
        )
        payload, _response = client.get_json("https://api.open-meteo.com/v1/forecast", allow_list=True)
        self.assertIsInstance(payload, list)
        with self.assertRaises(Exception):
            client.get_json("https://api.open-meteo.com/v1/forecast")

    def test_safe_http_can_accept_json_lists_for_weather_field(self):
        safe_http = (ROOT / "tools" / "safe_http.py").read_text(encoding="utf-8")
        self.assertIn("allow_list: bool = False", safe_http)
        self.assertIn("if allow_list and isinstance(payload, list)", safe_http)

    def test_weather_map_has_animation_core(self):
        text = (ROOT / "ui" / "map_widget.py").read_text(encoding="utf-8")
        self.assertIn("def _advance_animation", text)
        self.assertIn("self._anim_timer", text)
        self.assertIn("def _interpolate_scalar", text)
        self.assertIn("def _interpolate_wind", text)

    def test_visual_core_not_touched_by_weather_hotfix(self):
        # This regression test makes the scope explicit: weather evolution must
        # not alter the protected cinematic orb implementation.
        orb = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("cinematic-opengl-v1", orb)
        self.assertIn("OpenGL Orb post-preload restore", orb)

    def test_version(self):
        settings_text = (ROOT / "config" / "settings.py").read_text(encoding="utf-8")
        self.assertIn('APP_VERSION: str = "0.7.2"', settings_text)


if __name__ == "__main__":
    unittest.main()
