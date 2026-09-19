import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ORB = (ROOT / "ui" / "orb_widget.py").read_text(encoding="utf-8")
MAIN = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
SETTINGS = (ROOT / "config" / "settings.py").read_text(encoding="utf-8")


class OrbWrapperPreloadForwardingTests(unittest.TestCase):
    def test_public_wrapper_forwards_preload_visual_safety(self):
        self.assertIn("def set_preload_visual_safety(self, active: bool)", ORB)
        self.assertIn("self._gl_surface.set_preload_visual_safety(bool(active))", ORB)

    def test_public_wrapper_forwards_post_preload_restore(self):
        self.assertIn("def restore_post_preload_cinematic(self)", ORB)
        self.assertIn("self._gl_surface.restore_post_preload_cinematic()", ORB)

    def test_main_window_uses_public_wrapper_hooks(self):
        self.assertIn('hasattr(self.orb, "set_preload_visual_safety")', MAIN)
        self.assertIn('hasattr(self.orb, "restore_post_preload_cinematic")', MAIN)

    def test_version(self):
        self.assertIn('APP_VERSION: str = "0.7.2"', SETTINGS)


if __name__ == "__main__":
    unittest.main()
