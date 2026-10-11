import tempfile,unittest
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from aura_native.bootstrap.composition import compose_runtime
from aura_native.core.contracts import Event,CommandResult
from aura_native.ui.qt_bridge import NativeCoreBridge

class PendingBridgeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.app=QGuiApplication.instance() or QGuiApplication([])
 def setUp(self):
  self.d=tempfile.TemporaryDirectory();self.runtime=compose_runtime(project_root=Path(__file__).parents[2],state_dir=Path(self.d.name));self.runtime.start();self.bridge=NativeCoreBridge(self.runtime)
 def tearDown(self): self.bridge.close();self.d.cleanup()
 def event(self,name,**payload):self.runtime.bus.publish(Event(name=name,payload=payload));self.runtime.bus.drain()
 def test_created_and_final_states(self):
  self.event('pending_action.created',action_id='a',tool_name='calendar.prepare_create',action_type='calendar.create',state='prepared',summary='Dentiste');self.assertTrue(self.bridge.hasPendingAction);self.assertEqual(self.bridge.pendingActionId,'a');self.assertEqual(self.bridge.pendingActionSummary,'Dentiste');self.event('pending_action.confirmed',action_id='a',state='confirmed');self.assertEqual(self.bridge.pendingActionState,'confirmed');self.event('pending_action.executed',action_id='a',state='executed');self.assertFalse(self.bridge.hasPendingAction)
 def test_slots_publish_commands_and_empty_is_noop(self):
  self.bridge.confirmPendingAction();self.bridge.cancelPendingAction();self.event('pending_action.created',action_id='a',tool_name='x',action_type='x',state='prepared',summary='x');self.bridge.confirmPendingAction();self.bridge.cancelPendingAction();self.runtime.bus.drain();self.assertEqual(self.runtime.prepared_action_repository.get('a'),None)
if __name__=='__main__':unittest.main()
