import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from aura_native.bootstrap.composition import compose_runtime
from aura_native.google.models import TaskItem
from aura_native.ui.qt_bridge import NativeCoreBridge
from aura_native.google.real_providers import GoogleTasksProvider

ROOT = Path(__file__).parents[2]


class _Request:
    def __init__(self, value): self.value = value
    def execute(self): return self.value


class _TasksApi:
    def __init__(self): self.patches = []
    def list(self, **kwargs): return _Request({"items": [{"id": "list-1"}]})
    def patch(self, **kwargs): self.patches.append(kwargs); return _Request({"id": "task-1", "title": "ok", "status": "needsAction"})


class _Service:
    def __init__(self): self.api = _TasksApi()
    def tasklists(self): return self.api
    def tasks(self): return self.api


class _Auth:
    def get_credentials(self): return object()


class GoogleTasksBridgeActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = compose_runtime(project_root=ROOT, state_dir=Path(self.temp.name))
        self.runtime.start()
        self.provider = self.runtime.tasks_service.provider
        self.provider.tasks = [TaskItem("task-1", "Ancien titre", "2026-10-05T09:00:00Z")]
        self.bridge = NativeCoreBridge(self.runtime)

    def tearDown(self):
        self.bridge.close()
        self.runtime.stop()
        self.temp.cleanup()

    def _confirm(self):
        self.bridge.confirmPendingAction()
        self.runtime.bus.drain()

    def test_update_prepares_then_executes_once_on_confirmation(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertTrue(self.bridge.updateGoogleTask("task-1", "Nouveau titre", "2026-10-06T10:00:00Z", True))
            self.runtime.bus.drain()
            self.assertEqual(self.provider.calls, [])
            self._confirm()
        self.assertEqual(self.provider.calls, [("update", {"task_id": "task-1", "title": "Nouveau titre", "due_mode": "value", "due": "2026-10-06T10:00:00.000Z"})])
        self.assertEqual(self.provider.tasks[0].title, "Nouveau titre")
        trace = output.getvalue()
        for marker in ("PENDING_CONFIRM_ENTER", "PENDING_CONFIRM_RESOLVED kind=tasks.update", "PENDING_ORCHESTRATOR_ENTER kind=tasks.update", "PENDING_ORCHESTRATOR_ROUTE kind=tasks.update target=tasks", "TASKS_ACTION_EXECUTE_ENTER kind=tasks.update", "TASKS_UPDATE_PROVIDER_CALL", "TASKS_UPDATE_PROVIDER_ENTER", "TASKS_UPDATE_PROVIDER_SUCCESS", "PENDING_CONFIRM_RESULT success=true kind=tasks.update"):
            self.assertIn(marker, trace)

    def test_complete_prepares_then_executes_once_on_confirmation(self):
        self.assertTrue(self.bridge.completeGoogleTask("task-1"))
        self.runtime.bus.drain()
        self.assertEqual(self.provider.calls, [])
        self._confirm()
        self.assertEqual(self.provider.calls, [("complete", {"task_id": "task-1"})])
        self.assertEqual(self.provider.tasks[0].status, "completed")

    def test_delete_uses_title_for_confirmation_and_id_for_provider(self):
        task_id = "c214ZWxqU2ZHazJ3eXpBeA"
        self.provider.tasks = [TaskItem(task_id, "test2", "2026-10-05T09:00:00Z")]
        self.assertTrue(self.bridge.deleteGoogleTask(task_id, "test2"))
        self.runtime.bus.drain()
        action = self.runtime.prepared_action_repository.get(self.bridge.pendingActionId)
        self.assertEqual(action.summary, "Supprimer la tâche « test2 »")
        self.assertEqual(action.payload["task_id"], task_id)
        self.assertEqual(action.payload["task_title"], "test2")
        self.assertEqual(self.provider.calls, [])
        self._confirm()
        self.assertEqual(self.provider.calls, [("delete", {"task_id": task_id})])
        self.assertEqual(self.provider.tasks, [])
        self.bridge.confirmPendingAction()
        self.runtime.bus.drain()
        self.assertEqual(self.provider.calls, [("delete", {"task_id": task_id})])

    def test_delete_without_title_uses_human_fallback(self):
        task_id = "opaque-id"
        self.assertTrue(self.bridge.deleteGoogleTask(task_id, ""))
        self.runtime.bus.drain()
        action = self.runtime.prepared_action_repository.get(self.bridge.pendingActionId)
        self.assertEqual(action.summary, "Supprimer cette tâche Google")
        self.assertEqual(action.payload["task_id"], task_id)
        self.assertNotIn("task_title", action.payload)
        self.assertEqual(self.provider.calls, [])

    def test_empty_due_can_be_updated_and_duplicate_preparation_is_refused(self):
        self.assertTrue(self.bridge.updateGoogleTask("task-1", "Sans échéance", "", True))
        self.runtime.bus.drain()
        self.assertFalse(self.bridge.completeGoogleTask("task-1"))
        self._confirm()
        self.assertIsNone(self.provider.tasks[0].due)

    def test_provider_error_is_traced_without_unhandled_qml_exception(self):
        self.provider.error = "google_rate_limited"
        output = StringIO()
        with redirect_stdout(output):
            self.assertTrue(self.bridge.updateGoogleTask("task-1", "Refusé", "", True))
            self.runtime.bus.drain()
            self._confirm()
        trace = output.getvalue()
        self.assertIn("TASKS_UPDATE_PROVIDER_ERROR error=google_rate_limited", trace)
        self.assertIn("PENDING_CONFIRM_RESULT success=false kind=tasks.update", trace)

    def test_real_provider_patch_body_is_minimal_for_each_due_mode(self):
        service = _Service()
        provider = GoogleTasksProvider(_Auth(), build=lambda *args, **kwargs: service)
        provider.update_task({"task_id": "task-1", "title": "Titre", "due_mode": "unchanged"})
        provider.update_task({"task_id": "task-1", "title": "Titre", "due_mode": "value", "due": "2026-10-06T00:00:00.000Z"})
        provider.update_task({"task_id": "task-1", "title": "Titre", "due_mode": "clear"})
        self.assertEqual(service.api.patches[0]["body"], {"title": "Titre"})
        self.assertEqual(service.api.patches[1]["body"], {"title": "Titre", "due": "2026-10-06T00:00:00.000Z"})
        self.assertEqual(service.api.patches[2]["body"], {"title": "Titre", "due": None})

    def test_title_only_marks_due_unchanged_and_preserves_original_due(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertTrue(self.bridge.updateGoogleTask("task-1", "Titre seul", "2026-10-05", False))
            self.runtime.bus.drain(); self._confirm()
        self.assertEqual(self.provider.calls[0], ("update", {"task_id": "task-1", "title": "Titre seul", "due_mode": "unchanged"}))
        self.assertEqual(self.provider.tasks[0].due, "2026-10-05T09:00:00Z")
        self.assertIn("due_mode=unchanged", output.getvalue())


if __name__ == "__main__":
    unittest.main()
