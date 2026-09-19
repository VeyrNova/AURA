import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ORB=(ROOT/"ui"/"opengl_orb_surface.py").read_text(encoding="utf-8")
MAIN=(ROOT/"ui"/"main_window.py").read_text(encoding="utf-8")

class TestSafePreloadVisualLock(unittest.TestCase):
    def test_preload_suspends_framebuffer_selftest(self):
        self.assertIn("if self._preload_visual_safety", ORB)
        self.assertIn("framebuffer_selftest=suspended", ORB)
    def test_gate_controls_visual_safety(self):
        self.assertIn("set_preload_visual_safety(True)", MAIN)
        self.assertIn("set_preload_visual_safety(False)", MAIN)
    def test_same_cinematic_baseline_is_kept(self):
        self.assertIn("baseline=cinematic-opengl-v1", ORB)
        self.assertNotIn("animated QPainter fallback requested", ORB)

if __name__ == "__main__": unittest.main()
