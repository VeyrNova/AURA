import tempfile,unittest
from pathlib import Path
from aura_native.google.models import CalendarEvent,TaskItem
from aura_native.google.providers import FakeCalendarProvider,FakeTasksProvider,GoogleProviderError
from aura_native.google.calendar_service import CalendarService
from aura_native.google.tasks_service import TasksService
from aura_native.storage.database import NativeDatabase
from aura_native.storage.prepared_action_repository import PreparedActionRepository
class Tests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();r=PreparedActionRepository(NativeDatabase(Path(self.t.name)/'a.db'));self.cp=FakeCalendarProvider([CalendarEvent('e','Dentiste','2026-10-01T10:00:00+00:00','2026-10-01T11:00:00+00:00','UTC')]);self.tp=FakeTasksProvider([TaskItem('t','Lait','2026-10-01T00:00:00+00:00')]);self.c=CalendarService(self.cp,r);self.s=TasksService(self.tp,r);self.r=r
 def tearDown(self):self.t.cleanup()
 def test_calendar_read_prepare_confirm_execute(self):
  self.assertEqual(self.c.get_next_event().timezone,'UTC');self.assertEqual(len(self.c.get_events_for_date('2026-10-01')),1);a=self.c.prepare_create_event(title='X',start='2026-10-02T10:00:00+00:00',end='2026-10-02T11:00:00+00:00',timezone='UTC');self.assertEqual(len(self.cp.events),1)
  with self.assertRaises(ValueError):self.c.execute_prepared_action(a.action_id)
  self.r.confirm(a.action_id);self.c.execute_prepared_action(a.action_id);self.assertEqual(len(self.cp.events),2)
  with self.assertRaises(ValueError):self.c.execute_prepared_action(a.action_id)
 def test_calendar_update_delete_and_expiry(self):
  a=self.c.prepare_update_event(event_id='e',title='Y');self.r.confirm(a.action_id);self.c.execute_prepared_action(a.action_id);self.assertEqual(self.cp.events[0].title,'Y');a=self.c.prepare_delete_event(event_id='e');self.r.confirm(a.action_id);self.c.execute_prepared_action(a.action_id);self.assertEqual(self.cp.events,[])
 def test_tasks_confirmed_mutations_only(self):
  a=self.s.prepare_create_task(title='X');self.assertEqual(len(self.tp.tasks),1);self.r.confirm(a.action_id);self.s.execute_prepared_action(a.action_id);self.assertEqual(len(self.tp.tasks),2);a=self.s.prepare_complete_task(task_id='t');self.r.confirm(a.action_id);self.s.execute_prepared_action(a.action_id);self.assertEqual(self.tp.tasks[0].status,'completed');a=self.s.prepare_delete_task(task_id='t');self.r.confirm(a.action_id);self.s.execute_prepared_action(a.action_id);self.assertEqual(len(self.tp.tasks),1)
 def test_tasks_update_is_confirmed_and_preserves_empty_due(self):
  a=self.s.prepare_update_task(task_id='t',title='Nouveau titre',due='',due_mode='clear');self.assertEqual(self.tp.tasks[0].title,'Lait');self.r.confirm(a.action_id);self.s.execute_prepared_action(a.action_id);self.assertEqual(self.tp.calls,[('update',{'task_id':'t','title':'Nouveau titre','due':'','due_mode':'clear'})]);self.assertEqual(self.tp.tasks[0].title,'Nouveau titre');self.assertIsNone(self.tp.tasks[0].due)
