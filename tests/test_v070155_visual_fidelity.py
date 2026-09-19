from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]
FOCUS_MODE = "UI_FOCUS_MODE = True" in (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")


class V070155VisualFidelityTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    def test_top_level_shell_is_opaque(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("Qt.WA_TranslucentBackground, False", source)
        self.assertIn("QMainWindow { background-color: #01060f; }", source)
        self.assertIn("QWidget#auraRoot { background-color: #01060f; }", source)

    def test_opengl_surface_outputs_opaque_alpha(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("gl_FragColor = vec4(finalCol, 1.0);", source)
        self.assertIn("glClearColor(0.0025, 0.0105, 0.0260, 1.0)", source)
        self.assertNotIn("glEnable(_GL_BLEND)", source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_shader_has_target_holographic_layers(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        for marker in (
            "float crownMid",
            "float coreDisc",
            "float rg1",
            "float rg9",
            "float wave1",
            "float beamWide",
            "float ellipse1",
            "float filament1",
        ):
            self.assertIn(marker, source)

    def test_result_panel_is_not_translucent(self):
        source = (ROOT / "ui" / "holographic_results_panel.py").read_text(encoding="utf-8")
        self.assertIn("background-color: #020916;", source)
        self.assertIn("background-color: #041022;", source)
        self.assertNotIn("background-color: rgba(2, 9, 22, 246);", source)

    def test_public_orb_host_is_opaque(self):
        source = (ROOT / "ui" / "orb_widget.py").read_text(encoding="utf-8")
        block = source[source.index("class OrbWidget"):]
        self.assertIn("Qt.WA_TranslucentBackground, False", block)
        self.assertIn('background-color:#010711', block)


if __name__ == "__main__":
    unittest.main()
