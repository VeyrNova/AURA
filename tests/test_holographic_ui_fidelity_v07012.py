from regression_compat import assert_version_at_least
import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]


class HolographicUiFidelityV07012Tests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.12")

    def test_target_desktop_columns_are_explicit(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("nav.setFixedWidth(62)", source)
        self.assertIn("conversation.setFixedWidth(378)", source)
        self.assertIn("dashboard.setFixedWidth(440)", source)

    def test_target_navigation_uses_vector_icons(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("class HudIconButton", source)
        for icon in ('"chat"', '"grid"', '"brain"', '"folder"', '"chart"', '"settings"'):
            self.assertIn(icon, source)

    def test_boot_progress_is_inside_permanent_state_tray(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        start = source.index("status_panel = QFrame()")
        boot = source.index("self.boot_banner = QFrame()", start)
        add_status = source.index("hero_layout.addWidget(status_panel)", start)
        self.assertLess(start, boot)
        self.assertLess(boot, add_status)
        self.assertIn("status_panel.setFixedHeight(156)", source)

    def test_legacy_chat_utility_bar_is_hidden(self):
        source = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn("self.utility_controls.setVisible(False)", source)

    def test_orb_is_organic_plasma_not_only_uniform_rings(self):
        source = (ROOT / "ui" / "orb_widget.py").read_text(encoding="utf-8")
        for marker in (
            "_draw_plasma_torus",
            "_draw_electric_arcs",
            "_draw_inner_filaments",
            "Short, variable-width arclets",
            "Smaller dark intelligence core",
        ):
            self.assertIn(marker, source)

    def test_state_hud_has_target_emitters(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("class StatusPulseWidget", source)
        self.assertIn("class ActivityRingWidget", source)
        self.assertIn("self.status_pulse = StatusPulseWidget()", source)
        self.assertIn("self.activity_ring = ActivityRingWidget()", source)


if __name__ == "__main__":
    unittest.main()
