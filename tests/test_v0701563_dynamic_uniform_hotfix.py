from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]


class V0701563DynamicUniformHotfixTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    def test_dynamic_uniforms_use_native_gl_calls(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn('funcs.glUniform1f(uniforms["u_time"]', source)
        self.assertIn('funcs.glUniform1f(uniforms["u_speed"]', source)
        self.assertIn('funcs.glUniform1f(uniforms["u_state"]', source)
        self.assertIn('funcs.glUniform2f(uniforms["u_resolution"]', source)
        self.assertIn('funcs.glUniform3f(uniforms["u_primary"]', source)
        self.assertIn('funcs.glFlush()', source)

    def test_runtime_dynamic_framebuffer_self_test_is_diagnostic_only(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("self.grabFramebuffer()", source)
        self.assertIn("OpenGL dynamic output self-test", source)
        self.assertIn("OpenGL cinematic lock retained", source)
        block = source[source.index("def _validate_dynamic_output"):source.index("def _set_adaptive_visual_quality")]
        self.assertNotIn("self.initialization_failed.emit(reason)", block)

    def test_probe_samples_actual_gl_framebuffer(self):
        probe = (ROOT / "scripts" / "opengl_orb_probe.py").read_text(encoding="utf-8")
        self.assertIn('surface.grabFramebuffer()', probe)
        self.assertIn('AURA_OPENGL_ORB_ANIMATION=', probe)
        self.assertIn('fallback-active', probe)

    def test_startup_unlock_forces_idle_visual_state(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('self.orb.set_state("STARTUP")', source)
        self.assertIn('self.orb.set_state("IDLE")', source)
        self.assertIn('self.waveform.set_state("IDLE")', source)


if __name__ == "__main__":
    unittest.main()
