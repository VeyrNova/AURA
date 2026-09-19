import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORB = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
MAIN = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
SETTINGS = (ROOT / "config" / "settings.py").read_text(encoding="utf-8")


class OrbPostPreloadRestoreTests(unittest.TestCase):
    def test_successful_preload_forces_cinematic_high(self):
        self.assertIn('def restore_post_preload_cinematic', ORB)
        self.assertIn('_set_adaptive_visual_quality("cinematic-high", reason="xtts-post-preload-restore")', ORB)

    def test_restore_runs_only_after_loaded_result(self):
        self.assertIn('if result == "loaded" and hasattr(self.orb, "restore_post_preload_cinematic")', MAIN)
        self.assertIn('self.orb.restore_post_preload_cinematic()', MAIN)

    def test_diagnostic_log_exposes_effective_cadence(self):
        self.assertIn('OpenGL Orb post-preload restore quality=%s target_fps=%.2f interval=%dms', ORB)
        self.assertIn('baseline=cinematic-opengl-v1', ORB)

    def test_version(self):
        self.assertIn('APP_VERSION: str = "0.7.2"', SETTINGS)


if __name__ == "__main__":
    unittest.main()
