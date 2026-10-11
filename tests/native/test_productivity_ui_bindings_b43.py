from pathlib import Path
import unittest

ROOT = Path(__file__).parents[2]


class ProductivityUiBindingTests(unittest.TestCase):
    def setUp(self):
        self.bridge = (ROOT / "src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")
        self.agenda = (ROOT / "app/qml/views/AgendaView.qml").read_text(encoding="utf-8")
        self.tasks = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")

    def test_native_bridge_exposes_safe_productivity_values(self):
        for name in ("googleTasksCount", "googleCalendarCount", "googleTasksStatus", "googleCalendarStatus", "agendaMonthLabel"):
            self.assertIn(f"def {name}", self.bridge)
        self.assertIn('return "not_migrated"', self.bridge)

    def test_agenda_has_deterministic_offline_calendar(self):
        self.assertIn("offlineCalendarModel", self.agenda)
        self.assertIn("rebuildOfflineCalendar", self.agenda)
        self.assertIn("offlineCalendarModel.length ? offlineCalendarModel : agendaCalendarModel", self.agenda)
        self.assertIn("previousOfflineMonth", self.agenda)
        self.assertIn("nextOfflineMonth", self.agenda)

    def test_tasks_and_agenda_use_explicit_native_counts(self):
        self.assertIn("coreBridge.googleTasksCount", self.tasks)
        self.assertIn("coreBridge.googleCalendarCount", self.agenda)
        self.assertNotIn('text: "undefined', self.tasks + self.agenda)


if __name__ == "__main__":
    unittest.main()
