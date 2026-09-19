from __future__ import annotations

import unittest
from regression_compat import assert_version_at_least
from pathlib import Path

from config.settings import settings
from tools.weather import WeatherTool

ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    status_code = 200
    url = "https://api.open-meteo.com/v1/forecast"


class FakeHTTP:
    def __init__(self, payloads):
        self.payloads = list(payloads)

    def get_json(self, url):
        if "air-quality" in url:
            return ({"current": {}}, FakeResponse())
        return (self.payloads.pop(0), FakeResponse())


def weather_payload(*, now_prob=15, day_max=100, humidity=83, precip=0.0):
    return {
        "current": {
            "time": "2026-08-10T19:00",
            "temperature_2m": 28.2,
            "apparent_temperature": 29.0,
            "relative_humidity_2m": humidity,
            "precipitation": precip,
            "weather_code": 3,
            "wind_speed_10m": 11.0,
            "surface_pressure": 1011.0,
            "visibility": 12000.0,
            "dew_point_2m": 24.0,
        },
        "hourly": {
            "time": ["2026-08-10T18:00", "2026-08-10T19:00", "2026-08-10T20:00"],
            "precipitation_probability": [10, now_prob, 65],
        },
        "daily": {
            "temperature_2m_max": [31.0],
            "temperature_2m_min": [24.0],
            "precipitation_probability_max": [day_max],
        },
    }


class WeatherSemanticsHudMotionV07127Tests(unittest.TestCase):
    def make_tool(self, **kwargs):
        geocode = {"results": [{
            "name": "Tokyo", "admin1": "Préfecture de Tokyo", "country": "Japon",
            "latitude": 35.68, "longitude": 139.76,
        }]}
        return WeatherTool(FakeHTTP([geocode, weather_payload(**kwargs)]))

    def test_version_and_hud_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.2.7")
        self.assertTrue(settings.WEATHER_HUD_ANIMATIONS_ENABLED)
        self.assertGreaterEqual(settings.WEATHER_HUD_ANIMATION_FPS, 8)
        self.assertLessEqual(settings.WEATHER_HUD_ANIMATION_FPS, 30)

    def test_current_probability_is_not_daily_max(self):
        result = self.make_tool(now_prob=15, day_max=100, humidity=83).execute("Tokyo")
        self.assertTrue(result.ok)
        self.assertEqual(result.data["humidity"], 83)
        self.assertEqual(result.data["rain_probability_now"], 15)
        self.assertEqual(result.data["rain_probability_today_max"], 100)
        self.assertEqual(result.data["precip_probability"], 100)

    def test_voice_does_not_say_daily_max_is_current_risk(self):
        speech = self.make_tool(now_prob=15, day_max=100).execute("Tokyo").speech_response
        self.assertIn("Pas de pluie actuellement", speech)
        self.assertIn("Averses possibles plus tard aujourd'hui", speech)
        self.assertNotIn("Risque de pluie : 100%", speech)
        self.assertNotIn("Risque de pluie maintenant : 100%", speech)

    def test_voice_can_state_true_immediate_probability(self):
        speech = self.make_tool(now_prob=70, day_max=100).execute("Tokyo").speech_response
        self.assertIn("Risque de pluie maintenant : 70%", speech)
        self.assertNotIn("100%", speech)

    def test_rain_in_progress_takes_priority(self):
        speech = self.make_tool(now_prob=90, day_max=100, precip=1.2).execute("Tokyo").speech_response
        self.assertIn("Pluie en cours", speech)
        self.assertNotIn("Risque de pluie maintenant", speech)

    def test_hud_source_has_distinct_humidity_and_rain_metrics(self):
        source = (ROOT / "ui" / "tool_hud_popups.py").read_text(encoding="utf-8")
        self.assertIn('"HUMIDITÉ"', source)
        self.assertIn('"RISQUE PLUIE MAINT."', source)
        self.assertIn('"RISQUE PLUIE JOURNÉE"', source)

    def test_hud_motion_uses_one_bounded_timer_no_extra_opengl(self):
        source = (ROOT / "ui" / "tool_hud_popups.py").read_text(encoding="utf-8")
        weather_block = source[source.index("class WeatherHudPopup"):source.index("class MapsHudPopup")]
        self.assertEqual(weather_block.count("QTimer("), 1)
        self.assertIn("_HudMotionOverlay", weather_block)
        self.assertIn("setInterval(90)", weather_block)
        self.assertNotIn("QOpenGL", weather_block)
        self.assertNotIn("QPropertyAnimation", weather_block)


if __name__ == "__main__":
    unittest.main()
