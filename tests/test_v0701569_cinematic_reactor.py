from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]
FOCUS_MODE = "UI_FOCUS_MODE = True" in (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")


class V0701569CinematicReactorTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")

    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    def test_native_qt_framebuffer_pipeline_exists(self):
        self.assertIn("QOpenGLFramebufferObject", self.source)
        self.assertIn("_scene_fbo", self.source)
        self.assertIn("_bloom_a_fbo", self.source)
        self.assertIn("_bloom_b_fbo", self.source)
        self.assertIn("OpenGL cinematic multipass ready", self.source)
        self.assertNotIn("QWebEngineView", self.source)

    def test_bloom_is_two_pass_gaussian_then_composite(self):
        self.assertIn("BLOOM_HORIZONTAL_SHADER", self.source)
        self.assertIn("BLOOM_VERTICAL_SHADER", self.source)
        self.assertIn("COMPOSITE_SHADER", self.source)
        self.assertIn("u_bloom_strength", self.source)
        self.assertIn("u_exposure", self.source)
        self.assertIn("tone-map scene + blurred energy", self.source)

    def test_post_processing_runs_half_resolution(self):
        self.assertIn("self._bloom_scale = 0.50", self.source)
        self.assertIn("int(width * self._bloom_scale)", self.source)
        self.assertIn("int(height * self._bloom_scale)", self.source)

    def test_cinematic_pipeline_is_fail_soft(self):
        self.assertIn("post-processing désactivé; rendu direct conservé", self.source)
        self.assertIn("cinematic multipass indisponible; rendu direct conservé", self.source)
        self.assertIn("if multipass:", self.source)
        self.assertIn("else:\n            self._bind_default_framebuffer", self.source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_filaments_are_organically_dissolved_before_bloom(self):
        self.assertIn("V9 CINEMATIC MATTER", self.source)
        self.assertIn("float organicA", self.source)
        self.assertIn("float organicB", self.source)
        self.assertIn("float organicC", self.source)
        self.assertIn("filament10 *= mix", self.source)

    def test_widget_default_framebuffer_is_restored(self):
        self.assertIn("self.defaultFramebufferObject()", self.source)
        self.assertIn("glBindFramebuffer", self.source)
        self.assertIn("_GL_FRAMEBUFFER", self.source)


if __name__ == "__main__":
    unittest.main()
