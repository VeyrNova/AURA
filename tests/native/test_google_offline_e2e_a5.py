import tempfile,unittest
from pathlib import Path
from aura_native.google.models import PreparedAction,CalendarEvent,TaskItem
from aura_native.google.providers import FakeCalendarProvider,FakeTasksProvider,GoogleProviderError
from aura_native.google.calendar_service import CalendarService
from aura_native.google.tasks_service import TasksService
from aura_native.storage.database import NativeDatabase
from aura_native.storage.prepared_action_repository import PreparedActionRepository

class GoogleOfflineE2ETests(unittest.TestCase):
 def setUp(self):
  self.d=tempfile.TemporaryDirectory();self.r=PreparedActionRepository(NativeDatabase(Path(self.d.name)/'a.db'));self.cp=FakeCalendarProvider([CalendarEvent('e','Dentiste','2026-10-02T15:00','2026-10-02T16:00','Europe/Paris')]);self.tp=FakeTasksProvider([TaskItem('t','Acheter du lait','2026-10-01')]);self.cs=CalendarService(self.cp,self.r);self.ts=TasksService(self.tp,self.r)
 def tearDown(self):self.d.cleanup()
 def test_calendar_read_and_write_lifecycle(self):
  self.assertEqual(self.cs.get_events_for_date('2026-10-02')[0].title,'Dentiste');a=self.cs.prepare_create_event(title='Réunion',start='2026-10-03T10:00',end='2026-10-03T11:00',timezone='Europe/Paris');self.assertEqual(self.r.get(a.action_id).state,'prepared');self.assertEqual(len(self.cp.events),1);self.r.confirm(a.action_id);self.cs.execute_prepared_action(a.action_id);self.assertEqual(self.r.get(a.action_id).state,'executed');self.assertEqual(len(self.cp.events),2)
 def test_cancel_and_tasks_confirmation(self):
  a=self.cs.prepare_delete_event(event_id='e');self.r.cancel(a.action_id);self.assertEqual(len(self.cp.events),1);a=self.ts.prepare_create_task(title='Relancer Marc');self.r.confirm(a.action_id);self.ts.execute_prepared_action(a.action_id);self.assertEqual(len(self.tp.tasks),2)
  for action in (self.ts.prepare_complete_task(task_id='t'),self.ts.prepare_delete_task(task_id='t')): self.r.confirm(action.action_id);self.ts.execute_prepared_action(action.action_id)
  self.assertEqual(len(self.tp.tasks),1)
 def test_restart_and_multiple_pending(self):
  old=self.cs.prepare_create_event(title='Old',start='2026-10-04',end='2026-10-05',timezone='UTC');new=self.cs.prepare_create_event(title='New',start='2026-10-05',end='2026-10-06',timezone='UTC');restored=PreparedActionRepository(self.r.db).get_pending();self.assertEqual(restored[0].action_id,old.action_id);self.r.confirm(old.action_id);self.r.mark_executed(old.action_id);self.assertEqual(PreparedActionRepository(self.r.db).get_pending()[0].action_id,new.action_id)
 def test_summaries_and_expired(self):
  self.assertIn('Créer l’événement',self.cs.prepare_create_event(title='Dentiste').summary);self.assertIn('Créer la tâche',self.ts.prepare_create_task(title='Marc').summary);self.assertIn('terminée',self.ts.prepare_complete_task(task_id='t').summary)
  a=self.r.create(PreparedAction('expired','calendar.prepare_create','calendar.create',{},'x',True,'expired','2020','2020',None,None,''));self.assertEqual(self.r.get(a.action_id).state,'expired')
 def test_provider_error_is_normalized(self):
  self.cp.error='permission_denied';a=self.cs.prepare_create_event(title='x');self.r.confirm(a.action_id)
  with self.assertRaises(GoogleProviderError):self.cs.execute_prepared_action(a.action_id)
  self.assertEqual(self.r.get(a.action_id).state,'error');self.assertEqual(self.r.get(a.action_id).error_code,'permission_denied')
if __name__=='__main__':unittest.main()
