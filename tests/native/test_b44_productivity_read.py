from pathlib import Path
import unittest

ROOT = Path(__file__).parents[2]


class B44ProductivityReadTests(unittest.TestCase):
    def test_native_composition_exposes_read_services(self):
        source = (ROOT / "src/aura_native/bootstrap/composition.py").read_text(encoding="utf-8")
        self.assertIn("runtime.calendar_service = calendar", source)
        self.assertIn("runtime.tasks_service = tasks", source)

    def test_bridge_exposes_safe_read_shapes(self):
        source = (ROOT / "src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")
        for name in ("googleTasks", "googleCalendarEvents", "refreshGoogleTasks", "refreshGoogleCalendar"):
            self.assertIn(name, source)
        self.assertIn('_google_calendar_status = "not_connected"', source)

    def test_tasks_view_uses_native_read_model(self):
        source = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        self.assertIn("model: coreBridge.googleTasks", source)
        self.assertNotIn("model: googleTasksModel", source)

    def test_agenda_sync_wires_to_calendar_read_and_feedback(self):
        source = (ROOT / "app/qml/views/AgendaView.qml").read_text(encoding="utf-8")
        self.assertIn("coreBridge.refreshGoogleCalendar(first.toISOString(), end.toISOString())", source)
        self.assertNotIn("coreBridge.refreshGoogleCalendar()", source)
        self.assertIn("calendarSyncing", source)
        self.assertIn("coreBridge.googleCalendarEvents", source)

    def test_fake_provider_never_claims_connected(self):
        source = (ROOT / "src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")
        self.assertIn('provider.__class__.__name__ == "FakeCalendarProvider"', source)
        self.assertIn('self._google_calendar_status = "not_connected"', source)

    def test_calendar_read_preserves_safe_error_diagnostics(self):
        source = (ROOT / "src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")
        self.assertIn("lastGoogleCalendarErrorCode", source)
        self.assertIn("lastGoogleCalendarErrorStage", source)
        self.assertIn("B44_CALENDAR_READ_FAILED", source)

    def test_connect_button_follows_calendar_status(self):
        source = (ROOT / "app/qml/views/AgendaView.qml").read_text(encoding="utf-8")
        self.assertIn('visible: coreBridge.googleCalendarStatus !== "connected"', source)

    def test_calendar_events_rebuild_cells_when_bridge_updates(self):
        source = (ROOT / "app/qml/views/AgendaView.qml").read_text(encoding="utf-8")
        self.assertIn("root.rebuildOfflineCalendar()", source)
        self.assertIn("coreBridge.googleCalendarEvents", source)
        self.assertIn('events[e].dateKey || events[e].start', source)

    def test_calendar_property_has_dedicated_notify_signal(self):
        bridge = (ROOT / "src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")
        view = (ROOT / "app/qml/views/AgendaView.qml").read_text(encoding="utf-8")
        self.assertIn("googleCalendarEventsChanged = Signal()", bridge)
        self.assertIn("notify=googleCalendarEventsChanged", bridge)
        self.assertIn("onGoogleCalendarEventsChanged", view)

    def test_calendar_cell_event_roles_use_model_data(self):
        view = (ROOT / "app/qml/views/AgendaView.qml").read_text(encoding="utf-8")
        self.assertIn("modelData.eventCount > 0", view)
        self.assertIn("modelData.firstEventPayload", view)
        self.assertNotIn("model: eventCount > 0 ?", view)

    def test_calendar_refresh_rejects_unbounded_or_invalid_ranges_before_request(self):
        source = (ROOT / "src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")
        guard = source.index('raw_start = str(start or "").strip()')
        request = source.index("self._calendar_request_id += 1", guard)
        submit = source.index("self._read_executor.submit(self._read_calendar_worker", guard)
        self.assertLess(guard, request)
        self.assertLess(guard, submit)
        self.assertIn("reason=missing_range", source[guard:request])
        self.assertIn("reason=invalid_range", source[guard:request])
        self.assertIn("parsed_start.tzinfo is None", source[guard:request])
        self.assertIn("parsed_start >= parsed_end", source[guard:request])


if __name__ == "__main__":
    unittest.main()
