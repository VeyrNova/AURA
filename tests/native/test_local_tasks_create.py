import tempfile
import unittest
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from aura_native.bootstrap.composition import compose_runtime
from aura_native.ui.qt_bridge import NativeCoreBridge

ROOT = Path(__file__).parents[2]

class LocalTasksCreateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QGuiApplication.instance() or QGuiApplication([])
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.state = Path(self.temp.name)
        self.runtime = compose_runtime(project_root=ROOT, state_dir=self.state); self.runtime.start(); self.bridge = NativeCoreBridge(self.runtime)
    def tearDown(self): self.bridge.close(); self.runtime.stop(); self.temp.cleanup()
    def test_create_without_due_persists_once(self):
        self.assertTrue(self.bridge.createTask("TEST AURA LOCAL CREATE", ""))
        self.assertEqual(self.bridge.tasks_model.rowCount(), 1)
        self.assertIsNone(self.bridge.tasks_model.items[0]["due"])
        self.assertEqual(len(self.runtime.local_tasks_repository.list()), 1)
    def test_create_with_valid_due_normalizes(self):
        self.assertTrue(self.bridge.createTask("Échéance", "2026-10-02"))
        self.assertEqual(self.runtime.local_tasks_repository.list()[0]["due"], "2026-10-02")
    def test_empty_title_rejected_without_insert(self):
        self.assertFalse(self.bridge.createTask("  ", ""))
        self.assertEqual(self.runtime.local_tasks_repository.list(), [])
    def test_reopen_reads_persisted_task(self):
        self.assertTrue(self.bridge.createTask("Persistante", "")); self.bridge.close(); self.runtime.stop()
        runtime = compose_runtime(project_root=ROOT, state_dir=self.state); runtime.start(); bridge = NativeCoreBridge(runtime)
        try: self.assertEqual(bridge.tasks_model.items[0]["title"], "Persistante")
        finally: bridge.close(); runtime.stop()

    def test_full_crud_and_missing_id(self):
        self.assertTrue(self.bridge.createTask("CRUD", "2026-10-02"))
        item_id = self.bridge.tasks_model.items[0]["task_id"]
        self.assertTrue(self.bridge.updateTask(item_id, "Modifiée", "2026-10-03")); self.runtime.bus.drain(); self.bridge.confirmPendingAction(); self.runtime.bus.drain()
        self.assertEqual(self.bridge.tasks_model.items[0]["title"], "Modifiée")
        self.assertTrue(self.bridge.completeTask(item_id)); self.runtime.bus.drain(); self.bridge.confirmPendingAction(); self.runtime.bus.drain()
        self.assertEqual(self.bridge.tasks_model.items[0]["completed"], 1)
        self.assertFalse(self.bridge.completeTask(item_id))
        self.assertTrue(self.bridge.deleteTask(item_id)); self.runtime.bus.drain(); self.bridge.confirmPendingAction(); self.runtime.bus.drain()
        self.assertFalse(self.bridge.deleteTask(item_id))
        self.assertFalse(self.bridge.updateTask("missing", "X", ""))
        self.assertEqual(self.bridge.tasks_model.rowCount(), 0)

if __name__ == "__main__": unittest.main()
