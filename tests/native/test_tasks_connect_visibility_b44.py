from pathlib import Path
import unittest

ROOT = Path(__file__).parents[2]


class TasksConnectVisibilityTests(unittest.TestCase):
    def test_create_target_controls_are_real_hit_targets(self):
        source = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        self.assertIn('objectName: "taskCreateTargetLocal"', source)
        self.assertIn('objectName: "taskCreateTargetGoogle"', source)
        self.assertIn("TapHandler { onTapped: root.taskTargetGoogle = false }", source)
        self.assertIn("TapHandler { enabled: parent.enabled; onTapped: root.taskTargetGoogle = true }", source)

    def test_google_create_target_uses_workspace_auth_state(self):
        source = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        task_section = source[source.index('objectName: "taskCreateTargetLocal"'):source.index('height: 42', source.index('objectName: "taskCreateTargetGoogle"'))]
        self.assertIn('enabled: coreBridge.googleWorkspaceStatus === "connected"', task_section)
        self.assertNotIn("enabled: coreBridge.googleSyncActive", task_section)

    def test_create_button_routes_google_target_to_google_slot(self):
        source = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        add_task = source[source.index("function addTask()") : source.index("\n    }", source.index("function addTask()"))]
        self.assertIn('target = root.taskTargetGoogle ? "google" : "local"', add_task)
        self.assertIn("coreBridge.createGoogleTask(clean, taskDue.text.trim())", add_task)
        self.assertNotIn("coreBridge.createTask(clean, taskDue.text.trim())", add_task.split("var ok =", 1)[0])
        self.assertIn("TASK_CREATE_CLICK target=", add_task)

    def test_reminder_and_agenda_calendar_targets_use_workspace_state(self):
        tasks = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        agenda = (ROOT / "app/qml/views/AgendaView.qml").read_text(encoding="utf-8")
        self.assertIn('text: String(remindersModel.count || 0) + " rappel(s)"', tasks)
        self.assertIn('text: String(notesModel.count || 0) + " note(s)"', tasks)
        self.assertIn('objectName: "reminderCreateTargetGoogle"', tasks)
        self.assertIn('enabled: coreBridge.googleWorkspaceStatus === "connected"', tasks)
        self.assertIn('objectName: "agendaCreateTargetGoogle"', agenda)
        self.assertIn('enabled: coreBridge.googleWorkspaceStatus === "connected"', agenda)

    def test_reminder_creation_controls_share_vertical_centering(self):
        source = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        section = source[source.index('id: reminderText'):source.index('Row {', source.index('id: reminderText') + 1)]
        self.assertGreaterEqual(section.count("anchors.verticalCenter: parent.verticalCenter"), 3)

    def test_agenda_navigation_chevrons_share_visual_contract(self):
        source = (ROOT / "app/qml/views/AgendaView.qml").read_text(encoding="utf-8")
        self.assertEqual(source.count('font.pixelSize: 20; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignHCenter'), 2)
        self.assertEqual(source.count('width: 44; height: 38; radius: 11'), 2)

    def test_reminder_creation_row_fits_fixed_date_and_add_button(self):
        source = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        self.assertIn("width: Math.max(40, parent.width - 141 - 42 - 20); height: 32", source)
        self.assertIn("width: 141; height: 32", source)
        self.assertIn("width: 42; height: 32", source)

    def test_connect_button_uses_workspace_auth_state(self):
        source = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        self.assertIn('visible: coreBridge.googleWorkspaceStatus !== "connected"', source)
        self.assertNotIn('visible: !coreBridge.googleSyncActive', source)

    def test_read_error_does_not_reopen_auth_button(self):
        source = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        self.assertIn("googleWorkspaceStatus", source)
        self.assertIn('visible: coreBridge.googleWorkspaceStatus !== "connected"', source)


if __name__ == "__main__": unittest.main()
