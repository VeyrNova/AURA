from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from ai.visual_followup import is_visual_followup_request
from ai.visual_response import apply_visual_followup_context
from config.settings import settings
from ui.response_presentation import for_llm_reply, for_user_request

ROOT = Path(__file__).resolve().parents[1]


class V070154VisualCoreTests(unittest.TestCase):
    def test_version_and_visual_core_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.4")
        self.assertTrue(settings.OPENGL_ORB_ENABLED)
        self.assertGreaterEqual(settings.OPENGL_ORB_FPS, 24)
        self.assertGreater(settings.VISUAL_FOLLOWUP_TTL_SECONDS, 0)

    def test_shader_is_native_qt_opengl_not_webengine(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("QOpenGLWidget", source)
        self.assertIn("QOpenGLShaderProgram", source)
        self.assertIn("FRAGMENT_SHADER", source)
        self.assertIn("fbm", source)
        self.assertNotIn("QWebEngineView", source)

    def test_opengl_profile_logging_does_not_cast_enum_to_int(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertNotIn("int(actual.profile())", source)
        self.assertIn("getattr(actual.profile(), \"name\", str(actual.profile()))", source)

    def test_glsl_120_avoids_builtin_noise2_collision(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("float auraNoise2D(vec2 p)", source)
        self.assertNotIn("float noise2(vec2 p)", source)
        self.assertIn("auraNoise2D(p)", source)


    def test_pyside_scalar_uniforms_use_integer_locations(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("program.uniformLocation(name.encode(\"ascii\"))", source)
        self.assertIn('program.setUniformValue(uniforms["u_time"], float(self._elapsed))', source)
        self.assertIn('program.setUniformValue(uniforms["u_energy"], float(self._energy))', source)
        self.assertNotIn('program.setUniformValue("u_time", float(self._elapsed))', source)
        self.assertNotIn('program.setUniformValue("u_energy", float(self._energy))', source)

    def test_public_orb_keeps_qpainter_fallback(self):
        source = (ROOT / "ui" / "orb_widget.py").read_text(encoding="utf-8")
        self.assertIn("class PainterOrbWidget", source)
        self.assertIn("class OrbWidget", source)
        self.assertIn("_fallback_to_painter", source)
        self.assertIn("backend=opengl-shader", source)

    def test_visual_followup_detects_real_log_case(self):
        self.assertTrue(is_visual_followup_request("Donne les titres en anglais"))
        self.assertTrue(is_visual_followup_request("Traduis-les en anglais"))
        self.assertFalse(is_visual_followup_request("Quel temps fait-il à Tokyo ?"))

    def test_visual_followup_forces_visual_presentation(self):
        decision = for_user_request("Donne les titres en anglais", visual_context_active=True)
        self.assertTrue(decision.visual)
        final = for_llm_reply("1. Neon Divide\n2. Chrome Hearts", "Donne les titres en anglais", force_visual=True)
        self.assertTrue(final.visual)
        self.assertEqual(final.title, "RÉSULTAT STRUCTURÉ")

    def test_visual_followup_context_is_pinned(self):
        messages = [{"role": "system", "content": "AURA"}, {"role": "user", "content": "Donne les titres en anglais"}]
        out = apply_visual_followup_context(messages, "1. Ombre numérique\n2. Nuit chrome")
        self.assertIn("CONTEXTE VISUEL PRÉCÉDENT", out[1]["content"])
        self.assertIn("Ombre numérique", out[1]["content"])


if __name__ == "__main__":
    unittest.main()
