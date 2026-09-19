from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings


ROOT = Path(__file__).resolve().parents[1]


class StartupGateV0701Tests(unittest.TestCase):
    def test_version_is_supported(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.1")

    def test_production_launcher_uses_single_final_shell(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("from ui.startup_window import StartupWindow", source)
        self.assertIn("MainWindow(startup_gate=True)", source)
        self.assertTrue("window.show()" in source or "window.showMaximized()" in source)
        self.assertIn("window.startup_ready.connect(on_ready)", source)
        self.assertIn("Final Shell visible: Startup Gate verrouille", source)

    def test_main_window_gates_controls_without_hiding_final_shell(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("def _set_startup_locked", source)
        self.assertIn("self.chat_panel.set_interaction_enabled(not locked)", source)
        self.assertIn("self.boot_banner.setVisible(locked)", source)
        self.assertIn("self.startup_ready.emit()", source)
        self.assertNotIn("self.chat_panel.setEnabled(False)", source)

    def test_final_shell_contains_reference_layout_regions(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        for marker in (
            'setObjectName("topBar")',
            'setObjectName("navRail")',
            '"✦  CONVERSATION"',
            'setObjectName("heroPanel")',
            '"TABLEAU DE BORD"',
            '"ÉTAT ACTUEL"',
            'HudWaveformWidget',
            'QProgressBar',
        ):
            self.assertIn(marker, source)

    def test_repair_xtts_batch_is_cmd_safe(self):
        data = (ROOT / "REPAIR_XTTS_DEPS.bat").read_bytes()
        crlf = data.count(b"\r\n")
        lone_lf = data.count(b"\n") - crlf
        self.assertTrue(all(b < 128 for b in data))
        self.assertGreater(crlf, 0)
        self.assertEqual(lone_lf, 0)


if __name__ == "__main__":
    unittest.main()
