import unittest
from aura_native.core.bus import LocalBus
from aura_native.core.contracts import Event
from aura_native.reminders.notification_center import InternalReminderNotificationCenter
from aura_native.reminders.notification_contract import NotificationCapability, NotificationResult
from aura_native.reminders.notification_coordinator import NotificationCoordinator
from aura_native.reminders.window_state import WindowState, WindowStateAdapter


class _Windows:
    def __init__(self, result): self.result = result; self.calls = []
    def notify(self, reminder, *, is_missed=False):
        self.calls.append((dict(reminder), is_missed)); return self.result


class NotificationContract014BTests(unittest.TestCase):
    def reminder(self, ident="r1", trigger="2026-10-02T14:30"):
        return {"reminder_id": ident, "trigger_at": trigger, "content": "test"}

    def setUp(self):
        self.bus = LocalBus()
        self.center = InternalReminderNotificationCenter(self.bus)

    def tearDown(self):
        self.center.close()
        self.bus.close()

    def coordinator(self, state, windows=None):
        window = WindowStateAdapter(); window.state = state
        return NotificationCoordinator(self.center, window, windows)

    def test_capability_states_are_truthful_and_identity_is_stable(self):
        self.assertEqual(NotificationCapability.SUPPORTED.value, "supported")
        first = self.coordinator(WindowState.ACTIVE).notify(self.reminder())
        self.assertTrue(first.accepted)
        self.assertEqual(first.notification_id, "reminder:r1:2026-10-02T14:30:0")

    def test_native_route_when_windows_backend_accepts(self):
        windows = _Windows(NotificationResult(True, NotificationCapability.SUPPORTED, "x", "windows"))
        result = self.coordinator(WindowState.HIDDEN, windows).notify(self.reminder())
        self.assertTrue(result.accepted)
        self.assertEqual(result.channel, "windows")
        self.assertEqual(self.center.queue_size, 0)

    def test_in_app_fallback_when_windows_unavailable(self):
        windows = _Windows(NotificationResult(False, NotificationCapability.UNAVAILABLE, "x", "windows"))
        result = self.coordinator(WindowState.MINIMIZED, windows).notify(self.reminder())
        self.assertTrue(result.accepted)
        self.assertEqual(result.channel, "internal_fallback")
        self.assertEqual(self.center.current["notification_id"], "reminder:r1:2026-10-02T14:30:0")

    def test_active_window_uses_in_app_without_windows(self):
        result = self.coordinator(WindowState.ACTIVE).notify(self.reminder())
        self.assertTrue(result.accepted)
        self.assertEqual(result.channel, "in_app")

    def test_duplicate_same_logical_reminder_is_suppressed(self):
        first = self.coordinator(WindowState.ACTIVE).notify(self.reminder())
        second = self.coordinator(WindowState.ACTIVE).notify(self.reminder())
        self.assertTrue(first.accepted)
        self.assertFalse(second.accepted)
        self.assertEqual(second.reason, "duplicate")
        self.assertEqual(self.center.queue_size, 1)

    def test_new_trigger_is_not_globally_suppressed(self):
        self.coordinator(WindowState.ACTIVE).notify(self.reminder())
        result = self.coordinator(WindowState.ACTIVE).notify(self.reminder(trigger="2026-10-02T14:31"))
        self.assertTrue(result.accepted)
        self.assertEqual(self.center.queue_size, 2)

    def test_invalid_identity_is_unavailable_and_never_legacy(self):
        result = self.coordinator(WindowState.ACTIVE).notify({"content": "bad"})
        self.assertFalse(result.accepted)
        self.assertEqual(result.capability, NotificationCapability.ERROR)
        self.assertEqual(result.channel, "none")

    def test_reminder_bus_route_and_shutdown_are_safe(self):
        self.bus.publish(Event(name="reminder.due", payload=self.reminder()))
        self.bus.drain()
        self.assertEqual(self.center.queue_size, 1)
        self.center.close()
        self.assertFalse(self.center.dismiss())
        self.assertFalse(self.center.enqueue(self.reminder()).accepted)


if __name__ == "__main__":
    unittest.main()
