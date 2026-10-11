from datetime import datetime
from uuid import uuid4
from aura_native.google.models import PreparedAction

class LocalRemindersService:
    def __init__(self, repository, scheduler=None): self.repository = repository; self.scheduler = scheduler
    def _trigger(self, value):
        raw = str(value or '').strip()
        if not raw: raise ValueError('trigger_at_required')
        try: return datetime.strptime(raw, '%Y-%m-%dT%H:%M').strftime('%Y-%m-%dT%H:%M')
        except ValueError: raise ValueError('invalid_trigger_at')
    def list(self): return self.repository.list()
    def create(self, content, trigger_at):
        value = str(content or '').strip()
        if not value: return None
        result = self.repository.create(value, self._trigger(trigger_at))
        if self.scheduler: self.scheduler.reschedule()
        return result
    def delete(self, reminder_id):
        identifier = str(reminder_id or '').strip()
        result = bool(identifier) and self.repository.delete(identifier)
        if result and self.scheduler: self.scheduler.reschedule()
        return result
    def prepare_delete(self, reminder_id, content=''):
        identifier = str(reminder_id or '').strip()
        if not identifier or not any(row.get('reminder_id') == identifier for row in self.repository.list()):
            return None
        label = str(content or '').strip()
        summary = f'"Supprimer le rappel « {label} »"' if label else '"Supprimer ce rappel AURA"'
        return PreparedAction(str(uuid4()), 'aura.reminders', 'local_reminders.delete', {'reminder_id': identifier}, summary.strip('"'), True)
    def execute_prepared_action(self, action_id, repository):
        action = repository.get(action_id)
        if action and action.state=='confirmed' and action.action_type=='local_reminders.create':
            if set(action.payload)!= {'content','trigger_at'} or not all(isinstance(v,str) for v in action.payload.values()): raise ValueError('invalid_payload')
            result=self.create(action.payload['content'],action.payload['trigger_at'])
            if not result: raise ValueError('invalid_content')
            repository.mark_executed(action_id); return result
        if not action or action.state != 'confirmed' or action.action_type != 'local_reminders.delete':
            raise ValueError('invalid_prepared_action')
        if not self.delete(action.payload.get('reminder_id')):
            raise ValueError('local_reminder_not_found')
        repository.mark_executed(action_id)
        return True
