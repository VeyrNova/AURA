import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication
from aura_native.bootstrap.composition import compose_runtime
from aura_native.core.runtime import BackgroundLifecycle
from aura_native.reminders.notification_coordinator import NotificationCoordinator
from aura_native.reminders.notification_contract import NotificationCapability, NotificationResult
from aura_native.reminders.notification_center import InternalReminderNotificationCenter
from aura_native.reminders.window_state import WindowState, WindowStateAdapter


class _WindowsUnavailable:
    def notify(self, reminder, *, is_missed=False):
        return NotificationResult(False, NotificationCapability.UNAVAILABLE, "x", "windows")


class BackgroundTray014CTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def test_real_composition_background_owner_is_idempotent(self):
        temp = tempfile.TemporaryDirectory(prefix="aura-014c-")
        try:
            runtime = compose_runtime(project_root=Path(__file__).parents[2], state_dir=Path(temp.name))
            runtime.start()
            self.assertEqual(runtime.background_state, BackgroundLifecycle.STOPPED)
            self.assertTrue(runtime.start_background())
            self.assertFalse(runtime.start_background())
            self.assertEqual(runtime.background_state, BackgroundLifecycle.RUNNING)
            self.assertTrue(runtime.stop_background())
            self.assertFalse(runtime.stop_background())
            self.assertEqual(runtime.background_state, BackgroundLifecycle.STOPPED)
            runtime.stop()
        finally:
            temp.cleanup()

    def test_hidden_window_routes_one_reminder_to_native_fallback(self):
        bus = __import__("aura_native.core.bus", fromlist=["LocalBus"]).LocalBus()
        center = InternalReminderNotificationCenter(bus)
        state = WindowStateAdapter(); state.state = WindowState.HIDDEN
        coordinator = NotificationCoordinator(center, state, _WindowsUnavailable())
        reminder = {"reminder_id": "hidden-1", "trigger_at": "2026-10-02T14:30", "content": "hidden"}
        first = coordinator.notify(reminder)
        second = coordinator.notify(reminder)
        self.assertTrue(first.accepted)
        self.assertEqual(first.channel, "internal_fallback")
        self.assertFalse(second.accepted)
        self.assertEqual(center.queue_size, 1)
        center.close(); bus.close()

    def test_native_self_check_uses_one_real_qt_application(self):
        self.assertIsNotNone(QGuiApplication.instance())


if __name__ == "__main__":
    unittest.main()
