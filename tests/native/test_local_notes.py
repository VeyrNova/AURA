import tempfile, unittest
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from aura_native.bootstrap.composition import compose_runtime
from aura_native.ui.qt_bridge import NativeCoreBridge
ROOT=Path(__file__).parents[2]
class LocalNotesTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.app=QGuiApplication.instance() or QGuiApplication([])
 def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.runtime=compose_runtime(project_root=ROOT,state_dir=self.tmp.name); self.runtime.start(); self.bridge=NativeCoreBridge(self.runtime)
 def tearDown(self): self.bridge.close(); self.runtime.stop(); self.tmp.cleanup()
 def test_create_count_persistence_and_delete_confirmation(self):
  self.assertTrue(self.bridge.createNote('Titre','Contenu')); self.assertEqual(self.bridge.notes_model.count,1); note=self.runtime.local_notes_repository.list()[0]
  self.assertTrue(self.bridge.deleteNote(note['note_id'],'Titre')); self.runtime.bus.drain(); self.bridge.cancelPendingAction(); self.runtime.bus.drain(); self.assertEqual(len(self.runtime.local_notes_repository.list()),1)
  self.assertTrue(self.bridge.deleteNote(note['note_id'],'Titre')); self.runtime.bus.drain(); self.bridge.confirmPendingAction(); self.runtime.bus.drain(); self.assertEqual(self.bridge.notes_model.count,0); self.bridge.confirmPendingAction(); self.runtime.bus.drain(); self.assertEqual(self.runtime.local_notes_repository.list(),[])
 def test_empty_and_missing(self):
  self.assertFalse(self.bridge.createNote('','')); self.assertFalse(self.bridge.deleteNote('missing','x'))
 def test_three_count(self):
  for i in range(3): self.assertTrue(self.bridge.createNote('',f'n{i}'))
  self.assertEqual(self.bridge.notes_model.count,3)
 def test_update_is_prepared_then_executes_once_and_persists(self):
  self.assertTrue(self.bridge.createNote('Avant','Ancien')); note=self.runtime.local_notes_repository.list()[0]; nid=note['note_id']
  self.assertTrue(self.bridge.updateNote(nid,'Après','Nouveau')); self.runtime.bus.drain()
  self.assertEqual(self.runtime.local_notes_repository.list()[0]['content'],'Ancien')
  self.bridge.cancelPendingAction(); self.runtime.bus.drain(); self.assertEqual(self.runtime.local_notes_repository.list()[0]['title'],'Avant')
  self.assertTrue(self.bridge.updateNote(nid,'Après','Nouveau')); self.runtime.bus.drain(); self.bridge.confirmPendingAction(); self.runtime.bus.drain()
  row=self.runtime.local_notes_repository.list()[0]; self.assertEqual((row['title'],row['content']),('Après','Nouveau'))
  self.bridge.confirmPendingAction(); self.runtime.bus.drain(); self.assertEqual(self.runtime.local_notes_repository.list()[0]['content'],'Nouveau')
if __name__=='__main__': unittest.main()
