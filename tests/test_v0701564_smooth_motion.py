from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]
FOCUS_MODE = "UI_FOCUS_MODE = True" in (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")


class V0701564SmoothMotionTests(unittest.TestCase):
    def test_version_and_default_fps(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")
        self.assertEqual(settings.OPENGL_ORB_FPS, 60)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_shader_removes_discrete_time_reseed_and_slows_advection(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertNotIn("floor(t *", source)
        self.assertIn("float starSeed = hash21(cell);", source)
        self.assertIn("float rainPhase = fract", source)
        self.assertIn("t * 0.018 * motionScale", source)
        self.assertIn("for (int i = 0; i < 4; ++i)", source)

    def test_visual_time_is_clamped_not_wall_clock_catchup(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("sim_dt = min(dt, 1.0 / 30.0)", source)
        self.assertIn("self._elapsed += sim_dt", source)
        self.assertNotIn("self._elapsed = max(self._elapsed, self._clock.elapsed() / 1000.0)", source)

    def test_state_visual_parameters_are_interpolated(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("self._target_primary", source)
        self.assertIn("self._target_secondary", source)
        self.assertIn("self._target_state_code", source)
        self.assertIn("color_alpha = smooth_alpha", source)
        self.assertIn("state_alpha = smooth_alpha", source)

    def test_display_refresh_alignment_and_frame_gap_diagnostics(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("def _sync_fps_for_refresh", source)
        self.assertIn("screen.refreshRate()", source)
        self.assertIn("OpenGL Orb cadence display_refresh=", source)
        self.assertIn("frame_gap_p95=", source)
        self.assertIn("max_gap=", source)
        probe = (ROOT / "scripts" / "opengl_orb_probe.py").read_text(encoding="utf-8")
        self.assertIn("AURA_OPENGL_ORB_PACING=", probe)


if __name__ == "__main__":
    unittest.main()
