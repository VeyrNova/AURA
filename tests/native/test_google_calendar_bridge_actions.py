import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from aura_native.bootstrap.composition import compose_runtime
from aura_native.ui.qt_bridge import NativeCoreBridge

ROOT = Path(__file__).parents[2]


class GoogleCalendarBridgeActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = compose_runtime(project_root=ROOT, state_dir=Path(self.temp.name))
        self.runtime.start()
        self.provider = self.runtime.calendar_service.provider
        self.bridge = NativeCoreBridge(self.runtime)

    def tearDown(self):
        self.bridge.close()
        self.runtime.stop()
        self.temp.cleanup()

    def _confirm(self):
        self.bridge.confirmPendingAction()
        self.runtime.bus.drain()

    def test_create_prepares_without_provider_call_then_executes_once(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertTrue(self.bridge.createGoogleEvent("TEST AURA AGENDA CREATE", "2026-10-02T10:00", "", ""))
            self.runtime.bus.drain()
            self.assertEqual(self.provider.calls, [])
            action = self.runtime.prepared_action_repository.get(self.bridge.pendingActionId)
            self.assertEqual(action.action_type, "calendar.create")
            self.assertEqual(action.payload["timezone"], "Europe/Paris")
            self.assertEqual(action.payload["end"], "2026-10-02T11:00:00+02:00")
            self._confirm()
        self.assertEqual(len([call for call in self.provider.calls if call[0] == "create"]), 1)
        trace = output.getvalue()
        self.assertIn("CALENDAR_UI_CREATE_ENTER title_present=true datetime_present=true", trace)
        self.assertIn("CALENDAR_UI_CREATE_PREPARED kind=calendar.create pending=true", trace)

    def test_invalid_or_duplicate_create_does_not_mutate(self):
        self.assertFalse(self.bridge.createGoogleEvent("", "2026-10-02T10:00", "", ""))
        self.assertTrue(self.bridge.createGoogleEvent("One", "2026-10-02T10:00", "", ""))
        self.runtime.bus.drain()
        self.assertFalse(self.bridge.createGoogleEvent("Two", "2026-10-02T11:00", "", ""))
        self.assertEqual(self.provider.calls, [])


if __name__ == "__main__":
    unittest.main()
