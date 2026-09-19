import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class CinematicOrbLockTests(unittest.TestCase):
    def test_low_motion_never_requests_qpainter_fallback(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        block = source[source.index("def _validate_dynamic_output"):source.index("def _set_adaptive_visual_quality")]
        self.assertNotIn("initialization_failed.emit", block)
        self.assertNotIn("self._failed = True", block)
        self.assertIn("OpenGL cinematic lock retained", block)

    def test_adaptive_tiers_keep_cinematic_baseline(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("cinematic-high", source)
        self.assertIn("cinematic-balanced", source)
        self.assertIn("cinematic-eco", source)
        self.assertIn("cinematic-opengl-v1", source)

    def test_qpainter_remains_available_for_hard_opengl_failure(self):
        source = (ROOT / "ui" / "orb_widget.py").read_text(encoding="utf-8")
        self.assertIn("def _fallback_to_painter", source)
        self.assertIn("backend=qpainter-fallback", source)

if __name__ == "__main__":
    unittest.main()
