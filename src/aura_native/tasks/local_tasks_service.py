from datetime import date
from uuid import uuid4
from aura_native.google.models import PreparedAction

class LocalTasksService:
    def __init__(self, repository): self.repository = repository
    def list(self): return self.repository.list()
    def _due(self, value):
        raw = str(value or '').strip()
        if not raw: return None
        return date.fromisoformat(raw).isoformat()
    def create(self, title, due=''):
        value = str(title or '').strip()
        if not value: return False
        return self.repository.create(value, self._due(due))
    def update(self, task_id, title, due=''):
        identifier, value = str(task_id or '').strip(), str(title or '').strip()
        return bool(identifier and value) and self.repository.update(identifier, value, self._due(due))
    def complete(self, task_id): return self.repository.complete(str(task_id or '').strip())
    def delete(self, task_id): return self.repository.delete(str(task_id or '').strip())
    def prepare_update(self, task_id, title, due=''):
        value=str(title or '').strip(); identifier=str(task_id or '').strip()
        if not identifier or not value: return None
        if not any(x.get('task_id') == identifier for x in self.repository.list()): return None
        return PreparedAction(str(uuid4()), 'local_tasks.prepare_update', 'local_tasks.update', {'task_id':identifier,'title':value,'due':self._due(due)}, f'Modifier la tâche « {value} »')
    def prepare_complete(self, task_id, title=''):
        identifier=str(task_id or '').strip()
        if not identifier: return None
        current = next((x for x in self.repository.list() if x.get('task_id') == identifier), None)
        if not current or current.get('completed'): return None
        label=str(title or '').strip() or 'cette tâche'
        return PreparedAction(str(uuid4()), 'local_tasks.prepare_complete', 'local_tasks.complete', {'task_id':identifier}, f'Marquer la tâche « {label} » comme terminée')
    def prepare_delete(self, task_id, title=''):
        identifier=str(task_id or '').strip()
        if not identifier: return None
        current = next((x for x in self.repository.list() if x.get('task_id') == identifier), None)
        if not current: return None
        label=str(title or '').strip() or 'cette tâche'
        return PreparedAction(str(uuid4()), 'local_tasks.prepare_delete', 'local_tasks.delete', {'task_id':identifier}, f'Supprimer la tâche « {label} »')
    def execute_prepared_action(self, action_id, repository):
        action=repository.get(action_id)
        if not action or action.state != 'confirmed': raise ValueError('confirmation_required')
        if action.action_type=='local_tasks.create':
            if set(action.payload)!= {'title','due'} or not isinstance(action.payload['title'],str) or not isinstance(action.payload['due'],str): raise ValueError('invalid_payload')
            result=self.create(action.payload['title'],action.payload['due'])
            if not result: raise ValueError('invalid_content')
            repository.mark_executed(action_id); return result
        ok = {'local_tasks.update': lambda: self.update(action.payload.get('task_id'), action.payload.get('title'), action.payload.get('due')),
              'local_tasks.complete': lambda: self.complete(action.payload.get('task_id')),
              'local_tasks.delete': lambda: self.delete(action.payload.get('task_id'))}[action.action_type]()
        if not ok: raise ValueError('local_task_not_found')
        repository.mark_executed(action_id)
        return ok
