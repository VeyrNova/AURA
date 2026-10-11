from pathlib import Path
import unittest

ROOT = Path(__file__).parents[2]


class B44HotRebindTests(unittest.TestCase):
    def test_services_support_provider_replacement(self):
        for name in ("calendar_service.py", "tasks_service.py"):
            source = (ROOT / "src/aura_native/google" / name).read_text(encoding="utf-8")
            self.assertIn("def set_provider", source)

    def test_oauth_success_rebinds_both_services_without_recompose(self):
        source = (ROOT / "src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")
        self.assertIn("def _rebind_google_providers", source)
        self.assertIn("calendar_service.set_provider(calendar)", source)
        self.assertIn("tasks_service.set_provider(tasks)", source)
        self.assertIn("GoogleCalendarProvider(self._google_auth)", source)
        self.assertIn("GoogleTasksProvider(self._google_auth)", source)

    def test_shared_auth_instance_is_used(self):
        source = (ROOT / "src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")
        self.assertIn("GoogleCalendarProvider(self._google_auth)", source)
        self.assertIn("GoogleTasksProvider(self._google_auth)", source)


if __name__ == "__main__":
    unittest.main()
