from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings
from runtime.memory_policy import MemoryPressureStateMachine

ROOT = Path(__file__).resolve().parents[1]
FOCUS_MODE = "UI_FOCUS_MODE = True" in (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")


class V070156PixelFidelityTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    def test_reference_geometry_is_calibrated(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("self.resize(1672, 941)", source)
        self.assertIn("nav.setFixedWidth(62)", source)
        self.assertIn("conversation.setFixedWidth(378)", source)
        self.assertIn("dashboard.setFixedWidth(440)", source)
        self.assertIn("self.setFixedHeight(64)", source)

    def test_center_hud_has_four_reference_metrics(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        for marker in ("CORE TEMPERATURE", "CONTEXT WINDOW", "REASONING ENGINE", "MEMORY STATUS"):
            self.assertIn(marker, source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_shader_v3_is_dark_core_torus_not_full_marble_disc(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        for marker in ("float coreR", "float crownMid", "float coreDisc", "float crownMask", "float coreHalo", "float outerArcA"):
            self.assertIn(marker, source)
        self.assertIn("Filaments, not a filled sphere", source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_shader_v3_has_reference_wave_rings_and_pedestal(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        for marker in ("float rg1", "float rg9", "float wave1", "float waveCore5", "float beamWide", "float ellipse1", "float ellipse5"):
            self.assertIn(marker, source)
        self.assertIn("gl_FragColor = vec4(finalCol, 1.0);", source)

    def test_results_are_adaptive_not_always_full_screen(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('mode = "small"', source)
        self.assertIn('mode = "medium"', source)
        self.assertIn('mode = "large"', source)
        self.assertIn("chars <= 520", source)
        self.assertIn("chars <= 1800", source)

    def test_adaptive_prewarm_blocks_observed_high_ram_case(self):
        decision = MemoryPressureStateMachine().evaluate(
            ram_percent=65.2,
            available_gib=5.48,
            voice_brain_loaded=False,
            xtts_hot=True,
            predicted_with_voice_percent=90.8,
            predicted_available_after_gib=1.44,
        )
        self.assertFalse(decision.allow_voice_prewarm)

    def test_adaptive_prewarm_keeps_good_startup_case(self):
        decision = MemoryPressureStateMachine().evaluate(
            ram_percent=52.9,
            available_gib=7.4,
            voice_brain_loaded=False,
            xtts_hot=True,
            predicted_with_voice_percent=78.4,
            predicted_available_after_gib=3.4,
        )
        self.assertTrue(decision.allow_voice_prewarm)


if __name__ == "__main__":
    unittest.main()
