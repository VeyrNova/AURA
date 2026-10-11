from aura_native.google.providers import GoogleProviderError
from aura_native.tools.models import ToolResult

class TasksTool:
 def __init__(self,service,name):self.service,self.name=service,name
 def execute(self,payload):
  p=payload or {}
  try:
   if self.name=='tasks.list':return ToolResult(self.name,True,{'tasks':[x.__dict__ for x in self.service.list_tasks()]})
   required={'tasks.create':'title','tasks.complete':'task_id','tasks.delete':'task_id'}[self.name]
   if not p.get(required):return ToolResult(self.name,False,{},'google_invalid_response')
   method={'tasks.create':'prepare_create_task','tasks.complete':'prepare_complete_task','tasks.delete':'prepare_delete_task'}[self.name]
   action=getattr(self.service,method)(**p)
   return ToolResult(self.name,True,{'summary':action.summary},requires_confirmation=True,prepared_action_id=action.action_id)
  except GoogleProviderError as exc:return ToolResult(self.name,False,{},exc.code)