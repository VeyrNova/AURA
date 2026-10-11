from aura_native.google.providers import GoogleProviderError
from aura_native.tools.models import ToolResult

class CalendarTool:
 def __init__(self,service,name):self.service,self.name=service,name
 def execute(self,payload):
  p=payload or {}
  try:
   if self.name=='calendar.list_events':return ToolResult(self.name,True,{'events':[x.__dict__ for x in self.service.list_upcoming_events()]})
   if self.name=='calendar.get_day':
    if not p.get('date'):return ToolResult(self.name,False,{},'google_invalid_response')
    return ToolResult(self.name,True,{'events':[x.__dict__ for x in self.service.get_events_for_date(p['date'])]})
   if self.name=='calendar.find_free_time':
    if not p.get('start') or not p.get('end'):return ToolResult(self.name,False,{},'google_invalid_response')
    return ToolResult(self.name,True,{'busy':self.service.find_free_time(p['start'],p['end'])})
   required={'calendar.create':('title','start','end','timezone'),'calendar.update':('event_id',),'calendar.delete':('event_id',)}[self.name]
   if any(not p.get(field) for field in required):return ToolResult(self.name,False,{},'google_invalid_response')
   method={'calendar.create':'prepare_create_event','calendar.update':'prepare_update_event','calendar.delete':'prepare_delete_event'}[self.name]
   action=getattr(self.service,method)(**p)
   return ToolResult(self.name,True,{'summary':action.summary},requires_confirmation=True,prepared_action_id=action.action_id)
  except GoogleProviderError as exc:return ToolResult(self.name,False,{},exc.code)