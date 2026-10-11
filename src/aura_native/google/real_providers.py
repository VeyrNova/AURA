from __future__ import annotations
import importlib
from aura_native.google.models import CalendarEvent,CalendarBusyInterval,TaskItem
from aura_native.google.providers import GoogleProviderError
from aura_native.google.auth import GoogleAuthError
from aura_native.google.transport import build_authorized_service, normalized_transport_error

def map_google_error(exc):
 code=getattr(exc,'status_code',getattr(getattr(exc,'resp',None),'status',None))
 try: numeric=int(code) if code is not None else None
 except (TypeError,ValueError): numeric=None
 return {'400':'google_invalid_request','401':'google_auth_expired','403':'google_permission_denied','404':'google_resource_not_found','409':'google_conflict','429':'google_rate_limited'}.get(str(code),'google_network_error' if numeric is not None and numeric>=500 else 'google_invalid_response')

class GoogleCalendarProvider:
 def __init__(self,auth,build=None):self.auth=auth;self._build=build
 def _service(self):
  creds=self.auth.get_credentials()
  if not creds:raise GoogleProviderError('google_auth_required')
  if self._build:return self._build('calendar','v3',credentials=creds,cache_discovery=False)
  try:return build_authorized_service('calendar','v3',creds)
  except Exception as e:raise GoogleProviderError('google_provider_unavailable') from e
 def list_events(self,start=None,end=None):
  try:
   service=self._service();items=[];token=None
   while True:
    kwargs={'calendarId':'primary','singleEvents':True,'orderBy':'startTime'}
    if start:kwargs['timeMin']=start
    if end:kwargs['timeMax']=end
    if token:kwargs['pageToken']=token
    body=service.events().list(**kwargs).execute();items.extend(body.get('items',()));token=body.get('nextPageToken')
    if not token:break
   return tuple(self._event(x) for x in items)
  except (GoogleProviderError, GoogleAuthError) as e:
   if isinstance(e, GoogleAuthError): raise GoogleProviderError(e.code) from e
   raise
  except GoogleAuthError as e:raise GoogleProviderError(e.code) from e
  except Exception as e:raise GoogleProviderError(normalized_transport_error(e) or map_google_error(e)) from e
 def _event(self,x):
  begin=x.get('start') or {};finish=x.get('end') or {};all_day='date' in begin
  return CalendarEvent(str(x.get('id','')),str(x.get('summary') or 'Sans titre'),str(begin.get('date') or begin.get('dateTime') or ''),str(finish.get('date') or finish.get('dateTime') or ''),str(begin.get('timeZone') or x.get('timeZone') or 'UTC'),str(x.get('location') or ''),str(x.get('description') or ''),tuple(str(a.get('email','')) for a in x.get('attendees',()) if a.get('email')),str(x.get('status') or 'confirmed'))
 def find_free_time(self,start,end):
  try:
   body=self._service().freebusy().query(body={'timeMin':start,'timeMax':end,'items':[{'id':'primary'}]}).execute();busy=body.get('calendars',{}).get('primary',{}).get('busy',());return tuple(CalendarBusyInterval(str(x.get('start','')),str(x.get('end','')),'UTC') for x in busy)
  except GoogleAuthError as e:raise GoogleProviderError(e.code) from e
  except Exception as e:raise GoogleProviderError(map_google_error(e)) from e
 def _write(self, operation, payload):
  try:
   s=self._service(); p=dict(payload or {})
   if operation=='delete': s.events().delete(calendarId='primary',eventId=str(p['event_id'])).execute(); return {'deleted':str(p['event_id'])}
   body={}
   if p.get('title'): body['summary']=p['title']
   if p.get('location'): body['location']=p['location']
   if p.get('description'): body['description']=p['description']
   for side in ('start','end'):
    if p.get(side): body[side]={'dateTime':p[side], 'timeZone':p.get('timezone','UTC')}
   if operation=='create': raw=s.events().insert(calendarId='primary',body=body).execute()
   else: raw=s.events().patch(calendarId='primary',eventId=str(p['event_id']),body=body).execute()
   return self._event(raw)
  except GoogleProviderError: raise
  except GoogleAuthError as e: raise GoogleProviderError(e.code) from e
  except Exception as e: raise GoogleProviderError(map_google_error(e)) from e
 def create_event(self,payload): return self._write('create',payload)
 def update_event(self,payload): return self._write('update',payload)
 def delete_event(self,payload): return self._write('delete',payload)

class GoogleTasksProvider:
 def __init__(self,auth,build=None):self.auth=auth;self._build=build
 def _service(self):
  creds=self.auth.get_credentials()
  if not creds:raise GoogleProviderError('google_auth_required')
  if self._build:return self._build('tasks','v1',credentials=creds,cache_discovery=False)
  try:return build_authorized_service('tasks','v1',creds)
  except Exception as e:raise GoogleProviderError('google_provider_unavailable') from e
 def _tasklist(self,s):
  body=s.tasklists().list(maxResults=100).execute();items=body.get('items') or []
  if not items or not items[0].get('id'): raise GoogleProviderError('google_invalid_response')
  return str(items[0]['id'])
 def list_tasks(self):
  try:
   s=self._service();tid=self._tasklist(s);items=[];token=None
   while True:
    kw={'tasklist':tid,'showCompleted':True,'showHidden':False,'maxResults':100};
    if token:kw['pageToken']=token
    body=s.tasks().list(**kw).execute();items.extend(body.get('items',()));token=body.get('nextPageToken')
    if not token:break
   return tuple(TaskItem(str(x.get('id','')),str(x.get('title') or 'Sans titre'),x.get('due'),str(x.get('status') or 'needsAction'),str(x.get('notes') or ''),x.get('completed')) for x in items)
  except (GoogleProviderError, GoogleAuthError) as e:
   if isinstance(e, GoogleAuthError): raise GoogleProviderError(e.code) from e
   raise
  except Exception as e:
   if operation=='update': print(f'TASKS_UPDATE_PROVIDER_EXCEPTION type={type(e).__name__}',flush=True)
   raise GoogleProviderError(normalized_transport_error(e) or map_google_error(e)) from e
 def _write(self, operation, payload):
  try:
   s=self._service(); tid=self._tasklist(s); p=dict(payload or {})
   if operation=='delete': s.tasks().delete(tasklist=tid,task=str(p['task_id'])).execute(); return {'deleted':str(p['task_id'])}
   if operation=='complete': raw=s.tasks().patch(tasklist=tid,task=str(p['task_id']),body={'status':'completed'}).execute()
   elif operation=='update':
    body={'title':p['title']}
    if p.get('notes'): body['notes']=p['notes']
    if p.get('due_mode')=='value': body['due']=p['due']
    elif p.get('due_mode')=='clear': body['due']=None
    raw=s.tasks().patch(tasklist=tid,task=str(p['task_id']),body=body).execute()
   else:
    body={'title':p['title']}
    if p.get('notes'): body['notes']=p['notes']
    if p.get('due'): body['due']=p['due']
    raw=s.tasks().insert(tasklist=tid,body=body).execute()
   return TaskItem(str(raw.get('id','')),str(raw.get('title') or 'Sans titre'),raw.get('due'),str(raw.get('status') or 'needsAction'),str(raw.get('notes') or ''),raw.get('completed'))
  except GoogleProviderError: raise
  except GoogleAuthError as e: raise GoogleProviderError(e.code) from e
  except Exception as e: raise GoogleProviderError(map_google_error(e)) from e
 def create_task(self,payload): return self._write('create',payload)
 def update_task(self,payload):
  print('TASKS_UPDATE_PROVIDER_ENTER',flush=True)
  try:
   result=self._write('update',payload)
  except GoogleProviderError as e:
   print(f'TASKS_UPDATE_PROVIDER_ERROR error={e.code} http_status=',flush=True);raise
  print('TASKS_UPDATE_PROVIDER_SUCCESS',flush=True);return result
 def complete_task(self,payload): return self._write('complete',payload)
 def delete_task(self,payload): return self._write('delete',payload)
