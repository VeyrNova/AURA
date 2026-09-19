import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
GUARD = (ROOT / "runtime" / "resource_guardian.py").read_text(encoding="utf-8")
ORB = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
SETTINGS = (ROOT / "config" / "settings.py").read_text(encoding="utf-8")

class JarvisPreloadHudTests(unittest.TestCase):
    def test_version(self):
        self.assertIn('APP_VERSION: str = "0.7.2"', SETTINGS)

    def test_worker_emits_real_progress(self):
        self.assertIn('progress = Signal(int, str)', MAIN)
        self.assertIn('progress_callback=lambda percent, phase:', MAIN)
        self.assertIn('_progress(56, "Chargement du modèle neural XTTS")', GUARD)
        self.assertIn('_progress(88, "Préchauffage neural silencieux")', GUARD)
        self.assertIn('_progress(98, "Validation finale RAM / VRAM")', GUARD)

    def test_hud_uses_progress_tray(self):
        self.assertIn('def _update_xtts_preload_progress', MAIN)
        self.assertIn('self.boot_progress.setValue(percent)', MAIN)
        self.assertIn('RTX 4050', MAIN)
        self.assertIn('VOICE CORE BOOT', MAIN)

    def test_preload_orb_state(self):
        self.assertIn('"PRELOAD":', ORB)
        self.assertIn('"PRELOAD": 8', ORB)
        self.assertIn('self.orb.set_state("PRELOAD")', MAIN)

    def test_gate_still_blocks_inputs(self):
        self.assertIn('self.chat_panel.set_input_enabled(False', MAIN)
        self.assertIn('self.chat_panel.set_microphone_available(False)', MAIN)
        self.assertIn('XTTS preload UI gate released result=', MAIN)

if __name__ == "__main__":
    unittest.main()
