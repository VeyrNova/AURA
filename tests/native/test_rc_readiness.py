import sqlite3, tempfile, unittest
from pathlib import Path
from aura_native.bootstrap.composition import compose_runtime
from aura_native.storage.database import NativeDatabase
from aura_native.storage.migrations import SCHEMA_VERSION

ROOT=Path(__file__).parents[2]

class RCReadinessTests(unittest.TestCase):
 def test_migrations_reach_version_and_integrity(self):
  with tempfile.TemporaryDirectory() as d:
   db=NativeDatabase(Path(d)/'aura_native.db'); conn=db.connect()
   self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')
   self.assertEqual(conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0],SCHEMA_VERSION)
   self.assertTrue(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='local_notes'").fetchone()); conn.close()
   conn=db.connect(); self.assertEqual(conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0],SCHEMA_VERSION); conn.close()
 def test_productivity_models_are_separate_and_persistent(self):
  with tempfile.TemporaryDirectory() as d:
   rt=compose_runtime(project_root=ROOT,state_dir=d); rt.start()
   self.assertIsNot(rt.local_tasks_repository,rt.local_reminders_repository); self.assertIsNot(rt.local_reminders_repository,rt.local_notes_repository)
   task=rt.local_tasks_service.create('t',''); reminder=rt.local_reminders_service.create('r','2030-01-01T10:00'); note=rt.local_notes_service.create('n','body')
   self.assertTrue(task and reminder and note)
   rt.stop(); rt=compose_runtime(project_root=ROOT,state_dir=d)
   self.assertEqual(len(rt.local_tasks_repository.list()),1); self.assertEqual(len(rt.local_reminders_repository.list()),1); self.assertEqual(len(rt.local_notes_repository.list()),1); rt.stop()

if __name__=='__main__': unittest.main()
