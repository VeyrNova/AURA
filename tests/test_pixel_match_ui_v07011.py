from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]


class PixelMatchUiV07011Tests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.11")

    def test_window_is_frameless_and_opaque_for_opengl(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("Qt.FramelessWindowHint", source)
        self.assertIn("Qt.WA_TranslucentBackground, False", source)
        self.assertIn("QMainWindow { background-color: #01060f; }", source)
        self.assertIn('setObjectName("appSurface")', source)

    def test_custom_window_controls_exist(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        for marker in (
            "self.minimize_button = QToolButton()",
            "self.maximize_button = QToolButton()",
            "self.close_button = QToolButton()",
            "def _toggle_maximize",
            "startSystemMove",
        ):
            self.assertIn(marker, source)

    def test_production_launcher_uses_maximized_final_shell(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("MainWindow(startup_gate=True)", source)
        self.assertIn("window.showMaximized()", source)
        self.assertNotIn("StartupWindow()", source)

    def test_conversation_uses_real_bubbles_not_raw_qtextedit(self):
        source = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn("class _MessageBubble", source)
        self.assertIn("QScrollArea", source)
        self.assertIn('setObjectName("userBubbleCard")', source)
        self.assertIn('setObjectName("auraBubbleCard")', source)
        self.assertNotIn("QTextEdit", source)

    def test_dashboard_uses_structured_cards_and_rows(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("class DashboardCard", source)
        self.assertIn("def set_rows", source)
        self.assertIn('DashboardCard("▣  TÂCHES"', source)
        self.assertIn('DashboardCard("◉  MÉMOIRE & PRÉFÉRENCES"', source)

    def test_orb_has_target_holographic_layers(self):
        source = (ROOT / "ui" / "orb_widget.py").read_text(encoding="utf-8")
        for marker in (
            "_draw_back_halo",
            "_draw_energy_wave",
            "_draw_telemetry_rings",
            "_draw_sphere",
            "_draw_platform",
            "_draw_particles",
            "ÉCOUTE. COMPREND. AGIT.",
        ):
            self.assertIn(marker, source)

    def test_startup_diagnostics_do_not_spam_chat(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        block = source[source.index("def _announce_ready"):source.index("def begin_startup")]
        self.assertNotIn("Resource Guardian protège", block)
        self.assertNotIn("Mémoire adaptative prudente", block)
        self.assertIn("Final UI ready", block)


if __name__ == "__main__":
    unittest.main()
