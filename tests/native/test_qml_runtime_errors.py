from pathlib import Path
import unittest

from PySide6.QtCore import QObject, Property, QUrl, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine

ROOT = Path(__file__).parents[2]


class _GoogleTasksBridge(QObject):
    def __init__(self):
        super().__init__()
        self.actions = []
        self._tasks = [
            {"id": "google-1", "title": "Avec échéance", "status": "needsAction", "due": "2026-10-02T09:30:00Z", "completed": False},
            {"id": "google-2", "title": "Sans échéance", "status": "needsAction", "due": "", "completed": False},
            {"id": "google-3", "title": "Troisième", "status": "completed", "due": None, "completed": True},
        ]

    @Property("QVariantList")
    def googleTasks(self): return self._tasks
    @Property(int)
    def googleTasksCount(self): return len(self._tasks)
    @Property(int)
    def taskCount(self): return 0
    @Property(int)
    def reminderCount(self): return 0
    @Property(int)
    def noteCount(self): return 0
    @Property(int)
    def googleCalendarCount(self): return 0
    @Property(bool)
    def googleConnecting(self): return False
    @Property(bool)
    def googleSyncActive(self): return False
    @Property(str)
    def googleTasksStatus(self): return "connected"
    @Property(str)
    def googleWorkspaceStatus(self): return "connected"
    @Property(str)
    def googleConnectButtonLabel(self): return "CONNECTER GOOGLE"
    @Property("QVariantMap")
    def googleOAuthClientStatus(self): return {"configured": False}

    @Slot(str, str, result=bool)
    def createGoogleTask(self, title, due): self.actions.append(("create", title, due)); return True
    @Slot(str, str, str, result=bool)
    def updateGoogleTask(self, task_id, title, due): self.actions.append(("update", task_id, title, due)); return True
    @Slot(str, result=bool)
    def completeGoogleTask(self, task_id): self.actions.append(("complete", task_id)); return True
    @Slot(str, str, result=bool)
    def deleteGoogleTask(self, task_id, task_title): self.actions.append(("delete", task_id, task_title)); return True


class QmlRuntimeErrorRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
    def setUp(self):
        self.memory = (ROOT / "app/qml/views/MemoryView.qml").read_text(encoding="utf-8")
        self.tasks = (ROOT / "app/qml/views/TasksView.qml").read_text(encoding="utf-8")
        self.agenda = (ROOT / "app/qml/views/AgendaView.qml").read_text(encoding="utf-8")
        self.bridge = (ROOT / "src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")

    def test_memory_uses_exposed_refresh_memories_slot(self):
        self.assertIn("def refreshMemories", self.bridge)
        self.assertNotIn("refreshMemory()", self.memory)
        self.assertEqual(self.memory.count("refreshMemories()"), 3)

    def test_google_task_delegate_uses_provider_due_role(self):
        google_block = self.tasks[self.tasks.index("model: coreBridge.googleTasks"):self.tasks.index("model: tasksModel")]
        self.assertIn("property var googleTask: modelData || ({})", google_block)
        for field in ("title", "status", "due", "id"):
            self.assertIn("googleTask." + field, google_block)
        self.assertNotIn("String(due || \"\")", google_block)
        self.assertNotIn("String(dueDate)", google_block)
        self.assertNotIn("String(externalId)", google_block)

    def test_agenda_event_logs_use_scoped_canonical_date_key(self):
        self.assertIn("property string cellDateKey", self.agenda)
        self.assertIn('padStart(2, "0")', self.agenda)
        self.assertNotIn("B44_EVENT_CONTAINER_GEOMETRY", self.agenda)
        self.assertNotIn("B44_EVENT_DELEGATE_GEOMETRY", self.agenda)

    def test_agenda_refresh_calls_have_required_arguments(self):
        self.assertNotIn("coreBridge.refreshGoogleCalendar()", self.agenda)
        self.assertNotIn("Insufficient arguments", self.agenda)

    def test_tasks_view_fake_google_items_have_no_due_scope_error(self):
        engine = QQmlEngine()
        warnings = []
        engine.warnings.connect(lambda items: warnings.extend(str(item.toString()) for item in items))
        bridge = _GoogleTasksBridge()
        engine.rootContext().setContextProperty("coreBridge", bridge)
        engine.rootContext().setContextProperty("tasksModel", [])
        engine.rootContext().setContextProperty("remindersModel", [])
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(ROOT / "app/qml/views/TasksView.qml")))
        root = component.create()
        for _ in range(4):
            self.app.processEvents()
        all_messages = "\n".join(warnings + [str(error.toString()) for error in component.errors()])
        self.assertIsNotNone(root, all_messages)
        self.assertNotIn("due is not defined", all_messages)
        self.assertNotIn("dueDate is not defined", all_messages)
        self.assertTrue(bridge.updateGoogleTask("google-1", "Nouveau titre", "2026-10-06"))
        self.assertTrue(bridge.completeGoogleTask("google-2"))
        self.assertEqual(bridge.actions, [("update", "google-1", "Nouveau titre", "2026-10-06"), ("complete", "google-2")])
        root.deleteLater()
        engine.deleteLater()


if __name__ == "__main__":
    unittest.main()
