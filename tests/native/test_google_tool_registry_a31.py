import tempfile
import unittest
from pathlib import Path
from aura_native.google.models import CalendarEvent, TaskItem
from aura_native.google.providers import FakeCalendarProvider, FakeTasksProvider
from aura_native.google.calendar_service import CalendarService
from aura_native.google.tasks_service import TasksService
from aura_native.storage.database import NativeDatabase
from aura_native.storage.prepared_action_repository import PreparedActionRepository
from aura_native.tools.registry import ToolRegistry, ToolDefinition, register_google_offline_tools

class GoogleToolRegistryA31Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); repo=PreparedActionRepository(NativeDatabase(Path(self.tmp.name)/'a.db'))
  self.calendar_provider=FakeCalendarProvider([CalendarEvent('e1','Meeting','2026-10-01T09:00:00+02:00','2026-10-01T10:00:00+02:00','Europe/Paris')])
  self.tasks_provider=FakeTasksProvider([TaskItem('t1','Milk','2026-10-01T00:00:00+02:00')])
  self.registry=ToolRegistry(); register_google_offline_tools(self.registry,CalendarService(self.calendar_provider,repo),TasksService(self.tasks_provider,repo))
 def tearDown(self): self.tmp.cleanup()
 def test_all_google_contracts_are_registered_with_weather_contract(self):
  weather=ToolRegistry(); weather.register(ToolDefinition('weather.get_forecast','weather',{},'weather',object()))
  expected={'calendar.list_events','calendar.get_day','calendar.find_free_time','calendar.create','calendar.update','calendar.delete','tasks.list','tasks.create','tasks.complete','tasks.delete'}
  self.assertEqual(expected,{x.name for x in self.registry.definitions})
  self.assertIn('weather.get_forecast',{x.name for x in weather.definitions})
  for definition in self.registry.definitions:
   self.assertEqual(definition.input_schema['type'],'object')
 def test_reads_are_successful_and_do_not_require_confirmation(self):
  for name,payload in (('calendar.list_events',{}),('calendar.get_day',{'date':'2026-10-01'}),('calendar.find_free_time',{'start':'2026-10-01T08:00:00+02:00','end':'2026-10-01T12:00:00+02:00'}),('tasks.list',{})):
   result=self.registry.execute(name,payload); self.assertTrue(result.success); self.assertFalse(result.requires_confirmation); self.assertIsNone(result.prepared_action_id)
 def test_writes_prepare_only_and_return_confirmation_contract(self):
  before_events=list(self.calendar_provider.events); before_tasks=list(self.tasks_provider.tasks)
  cases=(('calendar.create',{'title':'New','start':'2026-10-02T09:00:00+02:00','end':'2026-10-02T10:00:00+02:00','timezone':'Europe/Paris'}),('calendar.update',{'event_id':'e1','title':'Changed'}),('calendar.delete',{'event_id':'e1'}),('tasks.create',{'title':'New task'}),('tasks.complete',{'task_id':'t1'}),('tasks.delete',{'task_id':'t1'}))
  for name,payload in cases:
   result=self.registry.execute(name,payload); self.assertTrue(result.success); self.assertTrue(result.requires_confirmation); self.assertIsNotNone(result.prepared_action_id)
  self.assertEqual(before_events,self.calendar_provider.events); self.assertEqual(before_tasks,self.tasks_provider.tasks)
 def test_provider_errors_and_invalid_input_are_structured(self):
  self.calendar_provider.error='auth_required'; self.assertEqual('auth_required',self.registry.execute('calendar.list_events',{}).error_code)
  self.tasks_provider.error='permission_denied'; self.assertEqual('permission_denied',self.registry.execute('tasks.list',{}).error_code)
  self.assertEqual('google_invalid_response',self.registry.execute('calendar.create',{}).error_code)
  self.assertEqual('google_invalid_response',self.registry.execute('tasks.complete',{}).error_code)

if __name__=='__main__': unittest.main()