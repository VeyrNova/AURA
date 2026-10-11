from datetime import datetime
from uuid import uuid4
from aura_native.google.models import CalendarEvent,CalendarBusyInterval,TaskItem
class GoogleProviderError(Exception):
    def __init__(self,code): self.code=code; super().__init__(code)
class FakeCalendarProvider:
    def __init__(self,events=(),error=None): self.events=list(events);self.error=error;self.calls=[]
    def _ok(self):
        if self.error: raise GoogleProviderError(self.error)
    def list_events(self,start=None,end=None): self._ok();self.calls.append(('list',start,end));return tuple(self.events)
    def create_event(self,p): self._ok();self.calls.append(('create',dict(p))); x=CalendarEvent(str(uuid4()),p['title'],p['start'],p['end'],p['timezone'],p.get('location',''),p.get('description',''));self.events.append(x);return x
    def update_event(self,p):
        self._ok();self.calls.append(('update',dict(p))); found=next(x for x in self.events if x.event_id==p['event_id']); value=CalendarEvent(found.event_id,p.get('title',found.title),p.get('start',found.start),p.get('end',found.end),p.get('timezone',found.timezone),p.get('location',found.location),p.get('description',found.description),found.attendees,found.status);self.events=[value if x.event_id==value.event_id else x for x in self.events];return value
    def delete_event(self,p): self._ok();self.calls.append(('delete',dict(p)));self.events=[x for x in self.events if x.event_id!=p['event_id']]
class FakeTasksProvider:
    def __init__(self,tasks=(),error=None): self.tasks=list(tasks);self.error=error;self.calls=[]
    def _ok(self):
        if self.error:raise GoogleProviderError(self.error)
    def list_tasks(self):self._ok();return tuple(self.tasks)
    def create_task(self,p):self._ok();self.calls.append(('create',dict(p)));x=TaskItem(str(uuid4()),p['title'],p.get('due'),notes=p.get('notes',''));self.tasks.append(x);return x
    def update_task(self,p):
        print('TASKS_UPDATE_PROVIDER_ENTER',flush=True)
        try:
            self._ok();self.calls.append(('update',dict(p)));found=next(x for x in self.tasks if x.task_id==p['task_id']);mode=p.get('due_mode','unchanged');due=found.due if mode=='unchanged' else None if mode=='clear' else p.get('due');value=TaskItem(found.task_id,p.get('title',found.title),due,found.status,p.get('notes',found.notes),found.completed_at);self.tasks=[value if x.task_id==value.task_id else x for x in self.tasks]
        except GoogleProviderError as e:
            print(f'TASKS_UPDATE_PROVIDER_ERROR error={e.code} http_status=',flush=True);raise
        except Exception as e:
            print(f'TASKS_UPDATE_PROVIDER_EXCEPTION type={type(e).__name__}',flush=True);raise
        print('TASKS_UPDATE_PROVIDER_SUCCESS',flush=True);return value
    def complete_task(self,p):self._ok();self.calls.append(('complete',dict(p)));self.tasks=[TaskItem(x.task_id,x.title,x.due,'completed',x.notes,datetime.now().isoformat()) if x.task_id==p['task_id'] else x for x in self.tasks]
    def delete_task(self,p):self._ok();self.calls.append(('delete',dict(p)));self.tasks=[x for x in self.tasks if x.task_id!=p['task_id']]
