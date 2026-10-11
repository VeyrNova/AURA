from uuid import uuid4
from aura_native.google.models import PreparedAction
from aura_native.google.providers import GoogleProviderError
class TasksService:
 def __init__(self,provider,repository):self.provider,self.repository=provider,repository
 def set_provider(self, provider): self.provider = provider
 def list_tasks(self):return self.provider.list_tasks()
 def list_due_tasks(self):return tuple(x for x in self.list_tasks() if x.status!='completed')
 def _prepare(self,kind,p):
  label=str(p.get('title') or p.get('task_title') or '').strip(); verbs={'create':'Créer la tâche','update':'Modifier la tâche','complete':'Marquer la tâche','delete':'Supprimer la tâche'}; suffix=' comme terminée' if kind=='complete' else ''
  if kind=='delete' and not label:
   summary='Supprimer cette tâche Google'
  else:
   summary=verbs[kind]+' « '+(label or 'cette tâche')+' »'+suffix
  return self.repository.create(PreparedAction(str(uuid4()),'tasks.prepare_'+kind,'tasks.'+kind,dict(p),summary))
 def prepare_create_task(self,**p):return self._prepare('create',p)
 def prepare_update_task(self,**p):return self._prepare('update',p)
 def prepare_complete_task(self,**p):return self._prepare('complete',p)
 def prepare_delete_task(self,**p):return self._prepare('delete',p)
 def execute_prepared_action(self,i):
  a=self.repository.get(i)
  if not a or a.state!='confirmed':raise ValueError('confirmation_required')
  print(f"TASKS_ACTION_EXECUTE_ENTER kind={a.action_type} task_id_present={str(bool(a.payload.get('task_id'))).lower()}",flush=True)
  if a.action_type=='tasks.update':
   due_mode=a.payload.get('due_mode','unchanged');print(f"TASKS_UPDATE_PROVIDER_CALL task_id_present={str(bool(a.payload.get('task_id'))).lower()} title_present={str(bool(a.payload.get('title'))).lower()} due_mode={due_mode}",flush=True)
  provider_payload={'task_id': a.payload.get('task_id')} if a.action_type=='tasks.delete' else a.payload
  try:r={'tasks.create':self.provider.create_task,'tasks.update':self.provider.update_task,'tasks.complete':self.provider.complete_task,'tasks.delete':self.provider.delete_task}[a.action_type](provider_payload)
  except GoogleProviderError as e:self.repository.mark_error(i,e.code);raise
  except Exception as e:
   print(f"TASKS_ACTION_EXECUTE_EXCEPTION kind={a.action_type} type={type(e).__name__}",flush=True);raise
  self.repository.mark_executed(i);return r
