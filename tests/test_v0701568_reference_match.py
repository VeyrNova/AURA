from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]
FOCUS_MODE = "UI_FOCUS_MODE = True" in (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")


class V0701568ReferenceMatchTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")

    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_reference_scale_is_substantially_larger_than_v7(self):
        self.assertIn("p *= 0.70;", self.source)
        self.assertIn("about 35% more present than V7", self.source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_ten_thin_plasma_filaments_replace_thick_cables(self):
        for i in range(1, 11):
            self.assertIn(f"float filament{i}", self.source)
        self.assertIn("Ten thin multi-depth filaments", self.source)
        self.assertNotIn("float ribbon1", self.source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_hud_reaches_nine_large_telemetry_layers(self):
        for i in range(1, 10):
            self.assertIn(f"float rg{i}", self.source)
        self.assertIn("1.180", self.source)
        self.assertIn("brighter and wider telemetry rings", self.source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_wave_is_volumetric_five_layer_field(self):
        for i in range(1, 6):
            self.assertIn(f"float wave{i}", self.source)
            self.assertIn(f"float waveCore{i}", self.source)
        self.assertIn("float waveField", self.source)
        self.assertIn("float waveDust", self.source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_projector_has_five_depth_ellipses_and_particle_column(self):
        for i in range(1, 6):
            self.assertIn(f"float ellipse{i}", self.source)
        self.assertIn("float particleRain", self.source)
        self.assertIn("float beamCore", self.source)
        self.assertIn("float emitter", self.source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_ambient_stage_glow_exists_without_transparency(self):
        self.assertIn("float ambientHalo", self.source)
        self.assertIn("float chamber", self.source)
        self.assertIn("gl_FragColor = vec4(finalCol, 1.0);", self.source)


if __name__ == "__main__":
    unittest.main()
