from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]


class FinalShellStartupV07010Tests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.10")

    def test_launcher_has_no_splash_swap(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("splash.close()", source)
        self.assertNotIn("StartupWindow()", source)
        self.assertTrue("window.show()" in source or "window.showMaximized()" in source)
        self.assertIn("window.begin_startup()", source)

    def test_boot_progress_lives_inside_final_hero(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('self.boot_banner.setObjectName("bootBanner")', source)
        self.assertIn('self.boot_progress.setObjectName("bootProgress")', source)
        self.assertIn("self.startup_progress.connect(self._on_startup_progress)", source)
        self.assertIn('self.status_label.setText("BOOTING")', source)

    def test_controls_unlock_only_after_warmup_cleanup(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        cleanup = source[source.index("def _cleanup_warmup_thread"):source.index("def _start_voice_brain_prewarm")]
        self.assertIn("self._startup_complete = True", cleanup)
        self.assertIn("self._set_startup_locked(False)", cleanup)
        self.assertIn("self.startup_ready.emit()", cleanup)
        self.assertLess(cleanup.index("self._set_startup_locked(False)"), cleanup.index("self.startup_ready.emit()"))

    def test_chat_history_remains_visual_during_gate(self):
        source = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn("def set_interaction_enabled", source)
        self.assertIn("for control in self._interactive_controls", source)
        self.assertNotIn("self.history.setEnabled(enabled)", source)


if __name__ == "__main__":
    unittest.main()
