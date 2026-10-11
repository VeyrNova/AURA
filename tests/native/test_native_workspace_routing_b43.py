from pathlib import Path
import unittest

ROOT=Path(__file__).parents[2]
class NativeWorkspaceRoutingTests(unittest.TestCase):
 def setUp(self): self.source=(ROOT/'app/qml/views/NativeWorkspaceView.qml').read_text(encoding='utf-8')
 def test_memory_route_is_separate(self):
  self.assertIn('root.workspace === "memory"',self.source); self.assertIn('MemoryView',self.source)
 def test_agenda_route_loads_agenda_view(self):
  self.assertIn('AgendaView',self.source); self.assertIn('root.workspace === "agenda"',self.source)
 def test_tasks_route_loads_tasks_view(self):
  self.assertIn('TasksView',self.source); self.assertIn('root.workspace === "tasks"',self.source)
 def test_foundation_excludes_functional_routes(self):
  self.assertIn('root.workspace !== "agenda"',self.source); self.assertIn('root.workspace !== "tasks"',self.source)
if __name__=='__main__': unittest.main()
