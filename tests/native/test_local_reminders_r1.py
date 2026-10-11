import tempfile, unittest, sqlite3
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from aura_native.bootstrap.composition import compose_runtime
from aura_native.ui.qt_bridge import NativeCoreBridge
ROOT=Path(__file__).parents[2]

class LocalRemindersR1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QGuiApplication.instance() or QGuiApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.state=Path(self.temp.name)
        self.runtime=compose_runtime(project_root=ROOT,state_dir=self.state); self.runtime.start(); self.bridge=NativeCoreBridge(self.runtime)
    def tearDown(self): self.bridge.close(); self.runtime.stop(); self.temp.cleanup()
    def test_schema_and_create_read(self):
        self.assertTrue(self.bridge.createReminder('TEST AURA LOCAL REMINDER','2026-10-02T14:30'))
        self.assertEqual(self.bridge.reminders_model.rowCount(),1)
        self.assertEqual(self.bridge.reminders_model.count, 1)
        self.assertEqual(self.runtime.local_reminders_repository.list()[0]['trigger_at'],'2026-10-02T14:30')
        with sqlite3.connect(self.state/'data'/'aura_native.db') as c:
            from aura_native.storage.migrations import SCHEMA_VERSION
            self.assertEqual(c.execute("select max(version) from schema_migrations").fetchone()[0],SCHEMA_VERSION)
            self.assertEqual(c.execute('select count(*) from local_reminders').fetchone()[0],1)

    def test_model_count_tracks_all_replacements(self):
        model = self.bridge.reminders_model
        model.replace_items([]); self.assertEqual(model.count, 0)
        model.replace_items([{'reminder_id':'1','content':'a','trigger_at':'2026-10-02T14:30'}]); self.assertEqual(model.count, 1)
        model.replace_items([{'reminder_id':str(i),'content':'a','trigger_at':'2026-10-02T14:30'} for i in range(3)]); self.assertEqual(model.count, 3)
        model.replace_items([]); self.assertEqual(model.count, 0)
    def test_invalid_values_do_not_insert(self):
        for content,when in [('','2026-10-02T14:30'),('x',''),('x','bad'),('x','2026-02-30T14:30')]:
            self.assertFalse(self.bridge.createReminder(content,when))
        self.assertEqual(self.runtime.local_reminders_repository.list(),[])
    def test_persistence_after_recreate(self):
        self.assertTrue(self.bridge.createReminder('Persistant','2026-10-02T14:30')); self.bridge.close(); self.runtime.stop()
        runtime=compose_runtime(project_root=ROOT,state_dir=self.state); runtime.start(); bridge=NativeCoreBridge(runtime)
        try: self.assertEqual(bridge.reminders_model.items[0]['content'],'Persistant')
        finally: bridge.close(); runtime.stop()

    def test_delete_is_prepared_then_cancelled_without_mutation(self):
        self.assertTrue(self.bridge.createReminder('Dentiste','2026-10-02T14:30'))
        reminder = self.runtime.local_reminders_repository.list()[0]
        self.assertTrue(self.bridge.deleteReminder(str(reminder['reminder_id']), 'Dentiste'))
        self.runtime.bus.drain()
        action = self.runtime.prepared_action_repository.get(self.bridge.pendingActionId)
        self.assertEqual(action.action_type, 'local_reminders.delete')
        self.assertEqual(action.payload['reminder_id'], reminder['reminder_id'])
        self.assertEqual(action.summary, 'Supprimer le rappel « Dentiste »')
        self.assertEqual(len(self.runtime.local_reminders_repository.list()), 1)
        self.bridge.cancelPendingAction(); self.runtime.bus.drain()
        self.assertEqual(len(self.runtime.local_reminders_repository.list()), 1)

    def test_confirm_deletes_once_and_refreshes_model(self):
        self.assertTrue(self.bridge.createReminder('Dentiste','2026-10-02T14:30'))
        reminder = self.runtime.local_reminders_repository.list()[0]
        self.assertTrue(self.bridge.deleteReminder(str(reminder['reminder_id']), 'Dentiste'))
        self.runtime.bus.drain(); self.bridge.confirmPendingAction(); self.runtime.bus.drain()
        self.assertEqual(self.runtime.local_reminders_repository.list(), [])
        self.assertEqual(self.bridge.reminders_model.count, 0)
        self.bridge.confirmPendingAction(); self.runtime.bus.drain()
        self.assertEqual(self.runtime.local_reminders_repository.list(), [])

    def test_missing_id_and_empty_title_are_safe(self):
        self.assertFalse(self.bridge.deleteReminder('missing-id', 'Titre'))
        self.assertTrue(self.bridge.createReminder('','2026-10-02T14:30') is False)
        self.assertTrue(self.bridge.createReminder('Rappel','2026-10-02T14:30'))
        reminder = self.runtime.local_reminders_repository.list()[0]
        self.assertTrue(self.bridge.deleteReminder(str(reminder['reminder_id']), ''))
        self.runtime.bus.drain()
        action = self.runtime.prepared_action_repository.get(self.bridge.pendingActionId)
        self.assertEqual(action.summary, 'Supprimer ce rappel AURA')

if __name__=='__main__': unittest.main()



