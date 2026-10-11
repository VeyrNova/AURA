import unittest
from aura_native.google.real_providers import GoogleCalendarProvider, GoogleTasksProvider
from aura_native.google.models import CalendarEvent, TaskItem
from aura_native.google.providers import GoogleProviderError, FakeCalendarProvider, FakeTasksProvider
from aura_native.google.calendar_service import CalendarService
from aura_native.google.tasks_service import TasksService
from aura_native.storage.database import NativeDatabase
from aura_native.storage.prepared_action_repository import PreparedActionRepository
import tempfile
from pathlib import Path

class Auth:
 def get_credentials(self):
  from google.oauth2.credentials import Credentials
  return Credentials(token='offline')

class Req:
 def __init__(self,v): self.v=v
 def execute(self): return self.v
class Events:
 def __init__(self): self.calls=[]
 def insert(self,**k): self.calls.append(('insert',k)); return Req({'id':'e1','summary':'Dentiste','start':{'dateTime':'2026-10-02T15:00:00+02:00'},'end':{'dateTime':'2026-10-02T16:00:00+02:00'}})
 def patch(self,**k): self.calls.append(('patch',k)); return Req({'id':'e1','summary':'Updated','start':{'dateTime':'2026-10-02T15:00:00+02:00'},'end':{'dateTime':'2026-10-02T16:00:00+02:00'}})
 def delete(self,**k): self.calls.append(('delete',k)); return Req({})
class CalSvc:
 def __init__(self): self.e=Events()
 def events(self): return self.e
class Tasks:
 def __init__(self): self.calls=[]
 def list(self,**k): return Req({'items':[{'id':'list'}]})
 def insert(self,**k): self.calls.append(('insert',k)); return Req({'id':'t1','title':'Relancer Marc'})
 def patch(self,**k): self.calls.append(('patch',k)); return Req({'id':'t1','title':'Relancer Marc','status':'completed'})
 def delete(self,**k): self.calls.append(('delete',k)); return Req({})
class TaskSvc:
 def __init__(self): self.t=Tasks()
 def tasklists(self): return self
 def list(self,**k): return Req({'items':[{'id':'list'}]})
 def tasks(self): return self.t

class WritesB41(unittest.TestCase):
 def test_calendar_writes(self):
  s=CalSvc(); p=GoogleCalendarProvider(Auth(),build=lambda *a,**k:s)
  e=p.create_event({'title':'Dentiste','start':'2026-10-02T15:00:00+02:00','end':'2026-10-02T16:00:00+02:00','timezone':'Europe/Paris','location':'Cabinet'})
  self.assertIsInstance(e,CalendarEvent); self.assertEqual(s.e.calls[0][0],'insert'); self.assertEqual(s.e.calls[0][1]['calendarId'],'primary')
  p.update_event({'event_id':'e1','title':'Updated'}); p.delete_event({'event_id':'e1'}); self.assertEqual([x[0] for x in s.e.calls],['insert','patch','delete'])
 def test_tasks_writes(self):
  s=TaskSvc(); p=GoogleTasksProvider(Auth(),build=lambda *a,**k:s)
  self.assertIsInstance(p.create_task({'title':'Relancer Marc'}),TaskItem); p.complete_task({'task_id':'t1'}); p.delete_task({'task_id':'t1'})
  self.assertEqual([x[0] for x in s.t.calls],['insert','patch','delete']); self.assertEqual(s.t.calls[1][1]['body']['status'],'completed')
 def test_prepare_never_calls_provider(self):
  with tempfile.TemporaryDirectory() as d:
   repo=PreparedActionRepository(NativeDatabase(Path(d)/'a.db')); c=FakeCalendarProvider(); t=FakeTasksProvider(); cs=CalendarService(c,repo); ts=TasksService(t,repo)
   cs.prepare_create_event(title='x',start='a',end='b',timezone='UTC'); ts.prepare_create_task(title='x')
   self.assertEqual(c.calls,[]); self.assertEqual(t.calls,[])
