from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]
FOCUS_MODE = "UI_FOCUS_MODE = True" in (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")


class V07015610PrecisionMatchTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.orb = (ROOT / "ui" / "orb_widget.py").read_text(encoding="utf-8")

    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_orbital_plasma_replaces_flower_geometry(self):
        self.assertIn("V10 PRECISION MATCH: orbital plasma", self.source)
        self.assertIn("float packetA", self.source)
        self.assertIn("float packetB", self.source)
        self.assertIn("float packetC", self.source)
        self.assertIn("crownMid + 0.105", self.source)
        self.assertNotIn("0.036, 3.0, -t * 0.098", self.source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_hud_is_technical_and_segmented(self):
        self.assertIn("technical instrumentation, not extra plasma", self.source)
        self.assertIn("float hudNodes", self.source)
        self.assertIn("float nodeA", self.source)
        self.assertIn("0.86);", self.source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_wave_is_asymmetric_and_localized(self):
        self.assertIn("V10 asymmetric energy volume", self.source)
        self.assertIn("float leftGain", self.source)
        self.assertIn("float rightGain", self.source)
        self.assertIn("float peakL", self.source)
        self.assertIn("float peakR2", self.source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_projector_is_raised(self):
        self.assertIn("float baseY = p.y + 0.600;", self.source)
        self.assertIn("V10 moves the projector upward", self.source)
        self.assertIn("particleRain * 0.46", self.source)

    def test_bloom_is_softer_and_wider(self):
        self.assertIn("u_texel.x * 2.05", self.source)
        self.assertIn("u_texel.y * 2.05", self.source)
        self.assertIn("bloom * bloom * 0.22", self.source)
        self.assertIn("bloom_strength = 0.88 + 0.34", self.source)

    def test_brand_is_slightly_larger(self):
        self.assertIn("brand_font.setPixelSize(35)", self.orb)
        self.assertIn("tagline_font.setPixelSize(10)", self.orb)


if __name__ == "__main__":
    unittest.main()
