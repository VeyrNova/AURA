from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]
FOCUS_MODE = "UI_FOCUS_MODE = True" in (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")


class V0701567ReactorCoreTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_reactor_is_annular_not_a_filled_sphere(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("float crownMask = annulus", source)
        self.assertIn("Filaments, not a filled sphere", source)
        self.assertNotIn("float sphereR", source)
        self.assertNotIn("reactorMask = clamp(coreDisc", source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_crown_uses_multilayer_plasma_filaments(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        for token in ("float filament1", "float filament4", "float filament7", "float filament10"):
            self.assertIn(token, source)
        self.assertIn("float plasmaRibbon", source)
        self.assertIn("Sparse moving hot points", source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_no_nonperiodic_polar_hue_seam(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("no polar seam at -PI/+PI", source)
        self.assertIn("radialDir.x", source)
        self.assertNotIn("rang * 1.55", source)
        self.assertNotIn("rang * 2.6", source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_no_continuous_white_outer_rim(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        self.assertIn("float outerArcA", source)
        self.assertIn("float outerArcB", source)
        self.assertIn("continuous white circumference", source)
        self.assertNotIn("float outerRim", source)

    @unittest.skipIf(FOCUS_MODE, "Legacy orb fidelity check paused while UI Focus Mode is active")
    def test_reference_depth_layers_are_present(self):
        source = (ROOT / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
        for token in ("float rg9", "float waveCore5", "float beamWide", "float beamMid", "float beamCore", "float ellipse5", "float emitter"):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
