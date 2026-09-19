from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]
FOCUS_MODE = "UI_FOCUS_MODE = True" in (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")


class V0701566VisualFidelityTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    def test_qrect_is_imported_for_adaptive_result_geometry(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("QPointF, QRect, QRectF", source)
        self.assertIn("return QRect(x, y, width, height)", source)

    def test_visual_speech_handoff_is_committed_before_overlay(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        block = source[source.index("def _on_llm_finished"):source.index("def _on_llm_failed")]
        self.assertLess(block.index("self._pending_voice_override = presentation.speech"), block.index("self._show_visual_result("))
        self.assertIn("concise handoff", block)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_shader_v8_is_open_reactor_not_closed_sphere(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("Visual Core V11 Material & Typography Match", source)
        self.assertIn("float coreR = 0.135;", source)
        self.assertIn("float crownMid = 0.402", source)
        self.assertIn("float angleDistance", source)
        self.assertIn("float plasmaRibbon", source)
        self.assertIn("Ten thin multi-depth filaments", source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_reference_hud_has_seven_thin_outer_rings(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        for token in ("float rg1", "float rg2", "float rg3", "float rg4", "float rg5", "float rg6", "float rg7", "float rg8", "float rg9"):
            self.assertIn(token, source)
        self.assertIn("p *= 0.70;", source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_wave_and_pedestal_are_reference_weighted(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("float waveField", source)
        self.assertIn("float waveCore1", source)
        self.assertIn("float ellipse5", source)
        self.assertIn("float beamCore", source)


if __name__ == "__main__":
    unittest.main()
