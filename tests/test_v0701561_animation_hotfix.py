from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]
FOCUS_MODE = "UI_FOCUS_MODE = True" in (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")


class V0701561AnimationHotfixTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    def test_shader_time_uses_monotonic_clock_without_catchup_jumps(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("QElapsedTimer", source)
        self.assertIn("self._clock.start()", source)
        self.assertIn("sim_dt = min(dt, 1.0 / 30.0)", source)
        self.assertIn("self._elapsed += sim_dt", source)
        self.assertNotIn("self._elapsed = now_ms / 1000.0", source)

    def test_animation_timer_is_precise_and_update_not_visibility_gated(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("Qt.TimerType.PreciseTimer", source)
        self.assertIn("self._timer.timeout.connect(self._tick)", source)
        self.assertIn("self.update()", source)
        self.assertNotIn("if self.isVisible():\n            self.update()", source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_idle_motion_is_visible_but_temporally_smooth(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn('"IDLE": ((0.00, 0.74, 1.00), (0.60, 0.25, 1.00), 0.42, 0.78)', source)
        self.assertIn("float rot = t *", source)
        self.assertIn("float orbitBeacon =", source)
        self.assertIn("t * 0.018 * motionScale", source)
        self.assertNotIn("t * 3.10", source)

    def test_animation_watchdog_and_probe_measure_real_frames(self):
        surface = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        probe = (ROOT / "scripts" / "opengl_orb_probe.py").read_text(encoding="utf-8")
        self.assertIn("OpenGL Orb animation state=", surface)
        self.assertIn("paint_frames", surface)
        self.assertIn("AURA_OPENGL_ORB_ANIMATION=", probe)
        self.assertIn('int(stats.get("paint_frames", 0)) >= 20', probe)

    def test_show_event_restarts_animation_timer(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("def showEvent(self, event)", source)
        self.assertIn("if not self._timer.isActive()", source)
        self.assertIn("self._timer.start(self._frame_interval_ms)", source)


if __name__ == "__main__":
    unittest.main()
