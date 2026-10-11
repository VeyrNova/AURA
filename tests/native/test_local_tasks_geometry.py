from pathlib import Path
import unittest

ROOT = Path(__file__).parents[2]

class LocalTasksGeometryTests(unittest.TestCase):
    def test_local_action_column_stays_inside_card(self):
        source = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        block = source[source.index('id: localTask'):source.index('Flickable {', source.index('id: localTask'))]
        self.assertIn('anchors.leftMargin: 14', block)
        self.assertIn('anchors.rightMargin: 14', block)
        self.assertIn('anchors.verticalCenter: parent.verticalCenter', block)
        self.assertIn('height: 38', block)
        self.assertIn('width: parent.width - (done ? 158 : 208)', block)
        self.assertIn('width: 38; height: 38; radius: 12', block)
        self.assertIn('anchors.verticalCenter: parent.verticalCenter', block)
        self.assertNotIn('x:', block)

    def test_local_and_google_action_buttons_share_size(self):
        source = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count('width: 38; height: 38; radius: 12'), 3)
        local = source[source.index('id: localTask'):source.index('Flickable {', source.index('id: localTask'))]
        google = source[source.index('property var googleTask'):source.index('Rectangle { width: parent.width; height: 1', source.index('property var googleTask'))]
        self.assertIn('spacing: 10', google)
        self.assertIn('spacing: 10', local)

    def test_local_edit_reuses_google_pencil_contract(self):
        source = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        local = source[source.index('id: localTask'):source.index('Flickable {', source.index('id: localTask'))]
        self.assertEqual(local.count('PencilIcon {'), 1)
        self.assertNotIn('text: "✎"', local)
        for value in ('width: 21', 'height: 21', 'iconColor: "#8FEAF5"', 'detailColor: "#D7FBFF"'):
            self.assertIn(value, local)

    def test_reminder_delete_matches_task_button_geometry(self):
        source = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        reminder = source[source.index('LOCAL_REMINDER_DELEGATE'):source.index('Rectangle { width: parent.width; height: 1', source.index('LOCAL_REMINDER_DELEGATE'))]
        self.assertIn('anchors.rightMargin: 14', reminder)
        self.assertIn('anchors.verticalCenter: parent.verticalCenter', reminder)
        self.assertIn('height: 38', reminder)
        self.assertIn('width: 38; height: 38; radius: 12', reminder)
        self.assertNotIn('x:', reminder)
        self.assertIn('color: delRemHover.hovered ? "#31FF708F" : "#30500A18"', reminder)
        self.assertIn('border.color: "#2FFF708F"', reminder)

if __name__ == "__main__": unittest.main()
