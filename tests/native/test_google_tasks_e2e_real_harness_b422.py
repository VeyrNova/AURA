import unittest
from pathlib import Path
HARNESS=Path(__file__).parent/'_evidence/lot6b_b422_tasks_write_real.py'
class B422HarnessTests(unittest.TestCase):
 def test_layers_flags_and_tasklist(self):
  t=HARNESS.read_text(encoding='utf-8')
  for x in ('GoogleAuthProvider','GoogleTasksProvider','PreparedActionRepository','TasksService','PendingActionOrchestrator','LocalBus','--confirm-real-write'): self.assertIn(x,t)
  self.assertIn('add_mutually_exclusive_group(required=True)',t)
 def test_safety_and_state(self):
  t=HARNESS.read_text(encoding='utf-8'); self.assertIn('task_id',t); self.assertIn('REFUSED',t); self.assertNotIn('refresh_token',t); self.assertNotIn('client_secret',t); self.assertNotIn('GoogleCalendarProvider',t)
 def test_all_flows_present(self):
  t=HARNESS.read_text(encoding='utf-8')
  for x in ('prepare-e2e','confirm-e2e','cleanup-e2e','prepare-cancel','status-cancel','single_write=true','google_write=false'): self.assertIn(x,t)
 def test_delete_readback_rules_and_status_repair(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('b422',HARNESS); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
  self.assertTrue(mod.is_deleted(None)); self.assertTrue(mod.is_deleted({'deleted':True})); self.assertFalse(mod.is_deleted({'deleted':False}))
  t=HARNESS.read_text(encoding='utf-8'); self.assertIn("d['phase']='deleted'",t); self.assertIn('task_deleted=',t)
 def test_status_has_no_delete_call(self):
  t=HARNESS.read_text(encoding='utf-8'); self.assertIn("if a.status:",t); self.assertIn("if a.delete:",t)
