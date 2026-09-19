from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]
FOCUS_MODE = "UI_FOCUS_MODE = True" in (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")


class V0701562VisibleMotionTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_shader_has_explicit_startup_state_and_visible_rotating_features(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn('"STARTUP": ((0.00, 0.82, 1.00)', source)
        self.assertIn("uniform float u_state;", source)
        self.assertIn("vec2 rp = mat2(cs, -sn, sn, cs) * p;", source)
        self.assertIn("float filament1  =", source)
        self.assertIn("float knot1 =", source)
        self.assertIn("float orbitBeacon =", source)
        self.assertIn("float startupScan =", source)

    def test_startup_gate_uses_startup_visual_state(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('self.orb.set_state("STARTUP")', source)

    def test_probe_measures_pixel_motion_not_only_frame_count(self):
        probe = (ROOT / "scripts" / "opengl_orb_probe.py").read_text(encoding="utf-8")
        self.assertIn("sampled_pixels", probe)
        self.assertIn("motion_score", probe)
        self.assertIn("motion_score >= 0.75", probe)
        self.assertIn("QTimer.singleShot(900, capture_baseline)", probe)

    def test_state_uniform_is_resolved_and_uploaded(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn('"u_secondary", "u_state"', source)
        self.assertIn('funcs.glUniform1f(uniforms["u_state"], float(self._state_code))', source)


if __name__ == "__main__":
    unittest.main()
