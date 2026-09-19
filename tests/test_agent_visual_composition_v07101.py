import unittest
from pathlib import Path

from config.settings import settings
from tools.models import ToolResult
from ui.agent_visual_composer import compose_agent_visual


class AgentVisualCompositionV07101Tests(unittest.TestCase):
    def _result(self, map_mode="location"):
        maps = {
            "mode": map_mode,
            "label": "Toulon, Région PACA, France",
            "latitude": 43.12442,
            "longitude": 5.92836,
            "google_maps_url": "https://www.google.com/maps/search/?api=1&query=Toulon",
        }
        if map_mode == "directions":
            maps.update({
                "origin_label": "Vidauban, Région PACA, France",
                "origin_coordinates": [43.427, 6.431],
                "destination_coordinates": [43.12442, 5.92836],
                "route_points": [[43.427, 6.431], [43.30, 6.20], [43.12442, 5.92836]],
                "distance_km": 62.5,
                "duration_min": 47,
                "travelmode": "driving",
            })
        weather = {
            "place_label": "Toulon, Région PACA, France",
            "temperature": 33.6,
            "apparent": 34.0,
            "condition": "ciel dégagé",
            "humidity": 36,
            "wind_speed": 11,
        }
        return ToolResult(
            True, "agent", "agent", "agent-kernel", item_count=2, expected_items=2,
            data={"observations": [
                {"ok": True, "category": "maps", "data": maps},
                {"ok": True, "category": "weather", "data": weather},
            ]},
        )

    def test_version_and_flag(self):
        self.assertTrue(settings.APP_VERSION == "0.7.2")
        self.assertTrue(settings.AGENT_COMPOSITE_HUD_ENABLED)

    def test_maps_weather_selects_composite(self):
        composition = compose_agent_visual(self._result("location"))
        self.assertIsNotNone(composition)
        self.assertEqual(composition.kind, "maps_weather")
        self.assertEqual(composition.maps_data["label"], "Toulon, Région PACA, France")
        self.assertEqual(composition.weather_data["temperature"], 33.6)

    def test_route_weather_preserves_real_route_payload(self):
        composition = compose_agent_visual(self._result("directions"))
        self.assertIsNotNone(composition)
        self.assertEqual(composition.kind, "route_weather")
        self.assertEqual(composition.maps_data["distance_km"], 62.5)
        self.assertEqual(composition.maps_data["duration_min"], 47)
        self.assertGreaterEqual(len(composition.maps_data["route_points"]), 2)

    def test_unknown_agent_combo_falls_back(self):
        result = ToolResult(True, "x", "agent", "agent-kernel", data={"observations": [
            {"ok": True, "category": "web_search", "data": {"items": [1]}},
            {"ok": True, "category": "weather", "data": {"temperature": 20}},
        ]})
        self.assertIsNone(compose_agent_visual(result))

    def test_failed_agent_result_never_requests_special_surface(self):
        result = self._result("location")
        failed = ToolResult(False, result.response, result.category, result.source, data=result.data)
        self.assertIsNone(compose_agent_visual(failed))

    def test_popup_reuses_native_map_widget_and_main_window_has_fallback(self):
        root = Path(__file__).resolve().parents[1]
        popup_source = (root / "ui" / "tool_hud_popups.py").read_text(encoding="utf-8")
        main_source = (root / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("class AgentMapsWeatherHudPopup", popup_source)
        self.assertIn("self.map_widget = AuraMapWidget(self.maps_data, self)", popup_source)
        self.assertIn("CADRER LE TRAJET", popup_source)
        self.assertIn("compose_agent_visual(result)", main_source)
        self.assertIn('title="PLAN AURA"', main_source)
        self.assertIn("if not dedicated_shown", main_source)


if __name__ == "__main__":
    unittest.main()
