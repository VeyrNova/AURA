import tempfile,unittest
from pathlib import Path
from aura_native.core.bus import LocalBus
from aura_native.core.contracts import Command
from aura_native.google.models import PreparedAction,TaskItem
from aura_native.google.providers import FakeCalendarProvider,FakeTasksProvider
from aura_native.google.calendar_service import CalendarService
from aura_native.google.tasks_service import TasksService
from aura_native.google.pending_actions import PendingActionOrchestrator
from aura_native.storage.database import NativeDatabase
from aura_native.storage.prepared_action_repository import PreparedActionRepository

class Tests(unittest.TestCase):
 def setUp(self):
  self.d=tempfile.TemporaryDirectory();self.r=PreparedActionRepository(NativeDatabase(Path(self.d.name)/'a.db'));self.cp=FakeCalendarProvider();self.tp=FakeTasksProvider([TaskItem('t1','Milk','2026-10-01')]);self.o=PendingActionOrchestrator(self.r,CalendarService(self.cp,self.r),TasksService(self.tp,self.r));self.b=LocalBus();self.o.bind(self.b);self.events=[];self.b.subscribe(self.events.append)
 def tearDown(self):self.d.cleanup()
 def cmd(self,n,a,source='ui',payload=None):return Command(name=n,payload=payload or {'action_id':a.action_id},session_id='native',source=source)
 def cal(self):return self.o.calendar.prepare_create_event(title='x',start='2026-10-01T10:00',end='2026-10-01T11:00',timezone='UTC')
 def test_generic_bus_confirm_is_non_authoritative(self):
  a=self.cal();self.b.submit(self.cmd('pending_action.confirm',a));self.b.drain();self.assertEqual(self.r.get(a.action_id).state,'prepared');self.assertEqual(len(self.cp.events),0)
 def test_forged_sources_and_confirmed_payload_are_non_authoritative(self):
  for source in ('qml','agent','voice','tool'):
   a=self.cal();self.b.submit(self.cmd('pending_action.confirm',a,source=source,payload={'action_id':a.action_id,'confirmed':True}));self.b.drain();self.assertEqual(self.r.get(a.action_id).state,'prepared')
 def test_cancel_expired_idempotent(self):
  a=self.cal();self.b.submit(self.cmd('pending_action.cancel',a));self.b.drain();self.assertEqual(self.r.get(a.action_id).state,'cancelled');self.assertEqual(len(self.cp.events),0);self.b.submit(self.cmd('pending_action.cancel',a));self.b.drain();self.assertEqual(len(self.cp.events),0)
  old=self.r.create(PreparedAction('old','calendar.prepare_create','calendar.create',{},'old',True,'prepared','2020-01-01','2020-01-02',None,None,''));self.b.submit(self.cmd('pending_action.confirm',old));self.b.drain();self.assertEqual(self.r.get('old').state,'prepared')
 def test_provider_error_and_task_create(self):
  self.cp.error='google_permission_denied';a=self.cal();self.b.submit(self.cmd('pending_action.confirm',a));self.b.drain();self.assertEqual(self.r.get(a.action_id).state,'prepared');self.cp.error=None;a=self.o.tasks.prepare_create_task(title='New');self.b.submit(self.cmd('pending_action.confirm',a));self.b.drain();self.assertEqual(self.r.get(a.action_id).state,'prepared');self.assertEqual(len(self.tp.tasks),1)

 def test_ui_capability_confirms_exactly_once(self):
  a=self.cal();port=self.o.create_ui_confirmation_port();result=port.confirm(a.action_id);self.assertTrue(result.ok);self.assertEqual(self.r.get(a.action_id).state,'executed');self.assertEqual(len(self.cp.events),1);self.assertFalse(port.confirm(a.action_id).ok)

if __name__=='__main__':unittest.main()
