import unittest
from pathlib import Path
HARNESS=Path(__file__).parents[0]/'_evidence/lot6b_b421_calendar_e2e_real.py'
class E2EHarnessTests(unittest.TestCase):
 def test_layers_and_flags(self):
  t=HARNESS.read_text(encoding='utf-8')
  for x in ('GoogleAuthProvider','GoogleCalendarProvider','PreparedActionRepository','CalendarService','PendingActionOrchestrator','LocalBus','pending_action.confirm','pending_action.cancel'): self.assertIn(x,t)
  self.assertIn('confirm-real-write',t)
 def test_state_and_no_direct_insert(self):
  t=HARNESS.read_text(encoding='utf-8'); self.assertIn('prepared_action_id',t); self.assertIn('event_id',t); self.assertNotIn('events().insert',t); self.assertNotIn('refresh_token',t); self.assertNotIn('client_secret',t)
 def test_cancel_and_cleanup_paths(self):
  t=HARNESS.read_text(encoding='utf-8'); self.assertIn('CANCEL_TITLE',t); self.assertIn('calendar_cleanup=true',t); self.assertIn('single_write=true',t)
 def test_safety_flag_is_not_an_operation(self):
  t=HARNESS.read_text(encoding='utf-8'); self.assertIn('add_mutually_exclusive_group(required=True)',t); self.assertIn("ap.add_argument('--confirm-real-write'",t)
 def test_operation_matrix_is_explicit(self):
  t=HARNESS.read_text(encoding='utf-8'); self.assertIn("'prepare-confirm','confirm','status-confirm','cleanup-confirm-test','prepare-cancel','cancel','status-cancel'",t); self.assertNotIn('chosen=[',t)
