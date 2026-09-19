import unittest
from pathlib import Path

from config.settings import settings
from tools.maps import format_duration_minutes


class RouteDurationFormatV07102Tests(unittest.TestCase):
    def test_version(self):
        self.assertTrue(settings.APP_VERSION == "0.7.2")

    def test_minutes_remain_minutes_until_60(self):
        self.assertEqual(format_duration_minutes(47), "47 min")
        self.assertEqual(format_duration_minutes(60), "60 min")

    def test_over_60_uses_hours_and_minutes(self):
        self.assertEqual(format_duration_minutes(61), "1 h 01 min")
        self.assertEqual(format_duration_minutes(120), "2 h 00 min")
        self.assertEqual(format_duration_minutes(532), "8 h 52 min")

    def test_hud_uses_shared_duration_formatter(self):
        source = (Path(__file__).resolve().parents[1] / "ui" / "tool_hud_popups.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("format_duration_minutes("), 2)

    def test_maps_response_uses_same_formatter(self):
        source = (Path(__file__).resolve().parents[1] / "tools" / "maps.py").read_text(encoding="utf-8")
        self.assertIn("environ {format_duration_minutes(duration)}", source)


if __name__ == "__main__":
    unittest.main()
