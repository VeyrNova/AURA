import tempfile, unittest
from pathlib import Path
from aura_native.tools.router import ToolRouter
from aura_native.google.providers import FakeCalendarProvider
from aura_native.google.calendar_service import CalendarService
from aura_native.storage.database import NativeDatabase
from aura_native.storage.prepared_action_repository import PreparedActionRepository

class B43PreparationTests(unittest.TestCase):
 def test_exact_phrase_parses_without_write(self):
  route=ToolRouter(None).route("Ajoute demain à 14h un rendez-vous TEST AURA UI CALENDAR pendant 30 minutes.")
  self.assertEqual(route.tool_name,"calendar.prepare_create_event"); self.assertEqual(route.arguments["title"],"TEST AURA UI CALENDAR"); self.assertTrue(route.arguments["start"].endswith("T14:00:00+02:00")); self.assertTrue(route.arguments["end"].endswith("T14:30:00+02:00"))
 def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.provider=FakeCalendarProvider(); self.repo=PreparedActionRepository(NativeDatabase(Path(self.tmp.name)/"a.db")); self.service=CalendarService(self.provider,self.repo)
 def tearDown(self): self.tmp.cleanup()
 def test_confirm_exactly_once_and_cancel_zero_write(self):
  action=self.service.prepare_create_event(title="TEST AURA UI CALENDAR",start="2026-10-01T14:00:00+02:00",end="2026-10-01T14:30:00+02:00",timezone="Europe/Paris"); self.assertEqual(self.provider.calls,[]); self.repo.confirm(action.action_id); self.service.execute_prepared_action(action.action_id); self.assertEqual(len(self.provider.calls),1)
  with self.assertRaises(Exception): self.service.execute_prepared_action(action.action_id)
  cancel=self.service.prepare_create_event(title="cancel",start="a",end="b",timezone="UTC"); self.repo.cancel(cancel.action_id); self.assertEqual(len(self.provider.calls),1)
if __name__=='__main__': unittest.main()
