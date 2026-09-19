import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FinalOrbV0703Tests(unittest.TestCase):
    def test_definitive_orb_is_used_by_final_shell(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("from ui.orb_widget import OrbWidget", main)
        self.assertIn("self.orb = OrbWidget()", main)
        self.assertIn('self.orb.set_state("STARTUP")', main)

    def test_orb_has_dynamic_final_ui_layers(self):
        source = (ROOT / "ui" / "orb_widget.py").read_text(encoding="utf-8")
        for marker in (
            "QConicalGradient",
            "_draw_energy_wave",
            "_draw_telemetry_rings",
            "_draw_sphere",
            "_draw_platform",
            "ÉCOUTE. COMPREND. AGIT.",
            "STATE_ENERGY",
        ):
            self.assertIn(marker, source)

    def test_final_shell_orb_is_hero_sized(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertTrue("self.orb.setMinimumSize(540, 520)" in source or "self.orb.setMinimumSize(520, 500)" in source)
        self.assertIn("QSizePolicy.Expanding", source)


if __name__ == "__main__":
    unittest.main()
