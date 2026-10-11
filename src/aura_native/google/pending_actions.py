from aura_native.core.contracts import CommandError,CommandResult,Event
from aura_native.google.providers import GoogleProviderError
from datetime import datetime,timezone
from uuid import uuid4

class UiPreparedActionConfirmer:
 def __init__(self, orchestrator): self._orchestrator = orchestrator
 def confirm(self, action_id, session_id='native'):
  return self._orchestrator._confirm_from_ui(str(action_id or ''), session_id)

class PendingActionOrchestrator:
 def __init__(self,repository,calendar_service,tasks_service,local_tasks_service=None,local_reminders_service=None,local_notes_service=None,system_control_service=None,memory_service=None,contacts_service=None):self.repository,self.calendar,self.tasks,self.local_tasks,self.local_reminders,self.local_notes,self.system_control,self.memory,self.contacts=repository,calendar_service,tasks_service,local_tasks_service,local_reminders_service,local_notes_service,system_control_service,memory_service,contacts_service
 def bind(self,bus):
  self.bus=bus;bus.register_handler('pending_action.confirm',self.confirm);bus.register_handler('pending_action.cancel',self.cancel)
 def create_ui_confirmation_port(self): return UiPreparedActionConfirmer(self)
 def payload(self,a,code=''):
  return {'action_id':a.action_id,'tool_name':a.tool_name,'action_type':a.action_type,'state':a.state,'summary':a.summary,'error_code':code or a.error_code}
 def event(self,c,name,a,code=''):self.bus.publish(Event(name=name,payload=self.payload(a,code),correlation_id=c.correlation_id,session_id=c.session_id,source='pending_action'))
 def result(self,c,ok,status,a=None,code=''):
  return CommandResult(c.command_id,ok,status,payload=self.payload(a,code) if a else {},error=None if ok else CommandError(code or 'pending_action_error','Pending action cannot be processed'),correlation_id=c.correlation_id,session_id=c.session_id,source='pending_action')
 def confirm(self,c,_):
  print(f'PENDING_CONFIRM_REJECTED reason=generic_bus_not_authoritative source={c.source}',flush=True)
  return self.result(c,False,'unauthorized_source',None,'ui_authority_required')
 def _confirm_from_ui(self, action_id, session_id='native'):
  command_id=str(uuid4())
  c=type('UiCommand',(),{'command_id':command_id,'payload':{'action_id':action_id},'correlation_id':command_id,'session_id':session_id,'source':'ui-capability'})()
  a=self.repository.get(str(c.payload.get('action_id','')))
  if not a:
   print('PENDING_CONFIRM_REJECTED reason=no_pending_action',flush=True);self.event(c,'pending_action.error',type('A',(),{'action_id':str(c.payload.get('action_id','')),'tool_name':'','action_type':'','state':'missing','summary':'','error_code':'unknown_action'})(),'unknown_action');return self.result(c,False,'not_found',None,'unknown_action')
  print(f'PENDING_CONFIRM_RESOLVED kind={a.action_type} state={a.state} action_id_present=true',flush=True)
  print(f'PENDING_ORCHESTRATOR_ENTER kind={a.action_type}',flush=True)
  if a.expires_at and a.expires_at<=datetime.now(timezone.utc).isoformat():
   self.repository.expire_old(datetime.now(timezone.utc).isoformat());a=self.repository.get(a.action_id);self.event(c,'pending_action.expired',a);return self.result(c,False,'expired',a,'expired')
  try:a=self.repository.confirm(a.action_id)
  except ValueError:
   print(f'PENDING_CONFIRM_REJECTED reason=invalid_state',flush=True);self.event(c,'pending_action.error',a,'invalid_prepared_action_transition');return self.result(c,False,'invalid_state',a,'invalid_prepared_action_transition')
  self.event(c,'pending_action.confirmed',a)
  try:
   target='calendar' if a.action_type.startswith('calendar.') else 'tasks' if a.action_type.startswith('tasks.') else 'local_tasks' if a.action_type.startswith('local_tasks.') else 'local_reminders' if a.action_type.startswith('local_reminders.') else 'local_notes' if a.action_type.startswith('local_notes.') else 'memory' if a.action_type.startswith('memory.') else 'system_control' if a.action_type.startswith('system.window.') else 'contacts' if a.action_type.startswith('contact.') else 'other'
   print(f'PENDING_ORCHESTRATOR_ROUTE kind={a.action_type} target={target}',flush=True)
   if target=='other':
    print(f'PENDING_ORCHESTRATOR_REJECTED kind={a.action_type} reason=unsupported_kind',flush=True);raise ValueError('unsupported_action_type')
   if target=='system_control': self.system_control.execute_prepared_action(a.action_id)
   elif target=='contacts': self.contacts.execute_prepared_action(a.action_id)
   elif target=='memory': self.memory.execute_prepared_action(a.action_id, self.repository)
   elif target=='local_tasks': self.local_tasks.execute_prepared_action(a.action_id, self.repository)
   elif target=='local_reminders': self.local_reminders.execute_prepared_action(a.action_id, self.repository)
   elif target=='local_notes': self.local_notes.execute_prepared_action(a.action_id, self.repository)
   else: (self.calendar if target=='calendar' else self.tasks).execute_prepared_action(a.action_id)
   a=self.repository.get(a.action_id);self.event(c,'pending_action.executed',a);return self.result(c,True,'executed',a)
  except GoogleProviderError as e:
   a=self.repository.get(a.action_id);self.event(c,'pending_action.error',a,e.code);return self.result(c,False,'error',a,e.code)
  except Exception as e:
   print(f'PENDING_ORCHESTRATOR_REJECTED kind={a.action_type} reason=exception type={type(e).__name__}',flush=True)
   try:
    a=self.repository.mark_error(a.action_id, str(e)[:80] or 'execution_failed')
   except Exception: a=self.repository.get(a.action_id)
   self.event(c,'pending_action.error',a,str(e)[:80] or 'execution_failed')
   return self.result(c,False,'error',a,str(e)[:80] or 'execution_failed')
 def cancel(self,c,_):
  a=self.repository.get(str(c.payload.get('action_id','')))
  if not a:return self.result(c,False,'not_found',None,'unknown_action')
  try:a=self.repository.cancel(a.action_id);self.event(c,'pending_action.cancelled',a);return self.result(c,True,'cancelled',a)
  except ValueError:self.event(c,'pending_action.error',a,'invalid_prepared_action_transition');return self.result(c,False,'invalid_state',a,'invalid_prepared_action_transition')
