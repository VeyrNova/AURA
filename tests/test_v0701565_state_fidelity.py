from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]
FOCUS_MODE = "UI_FOCUS_MODE = True" in (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")


class V0701565StateFidelityTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    def test_llm_finish_is_fail_safe_and_reconciles_state(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("LLM presentation finalization failed; continuing with chat-only result", source)
        self.assertIn("def _reconcile_interaction_state", source)
        self.assertIn("State Lifecycle watchdog recovered stale THINKING", source)
        self.assertIn("llm-finished-guard", source)

    def test_visual_panel_show_first_animation_second(self):
        source = (ROOT / "ui" / "holographic_results_panel.py").read_text(encoding="utf-8")
        show = source[source.index("def show_animated"):source.index("def hide_animated")]
        self.assertLess(show.index("self.show()"), show.index("anim = QPropertyAnimation"))
        self.assertIn("return True", show)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_shader_reference_fidelity_remains_large_and_flowing(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("Material & Typography Match", source)
        self.assertIn("float crownOuter = 0.600;", source)
        self.assertIn("float crownMid = 0.402", source)
        self.assertIn("vec2 tangentDir", source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_reference_rings_extend_farther_out(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        for radius in ("0.640", "0.700", "0.760", "0.825", "0.895", "0.970", "1.045", "1.115", "1.180"):
            self.assertIn(radius, source)


if __name__ == "__main__":
    unittest.main()
