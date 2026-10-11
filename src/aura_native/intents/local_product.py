"""Local deterministic commands; existing services and confirmation storage only."""
from uuid import uuid4
from aura_native.google.models import PreparedAction
from .dispatcher import DispatchResult
from datetime import datetime


class LocalIntentProduct:
    INTENTS = frozenset(('LIST_NOTES','SEARCH_NOTE','LIST_TASKS','LIST_REMINDERS','CREATE_NOTE',
                         'CREATE_TASK','CREATE_REMINDER','COMPLETE_TASK','DELETE_NOTE','DELETE_REMINDER',
                         'CREATE_MEMORY','SEARCH_MEMORY','LIST_MEMORY','FORGET_MEMORY',
                         'CREATE_CONTACT','UPDATE_CONTACT','DELETE_CONTACT'))
    def __init__(self, repository, notes, tasks, reminders, memory=None, contacts=None):
        self.repository = repository
        self.services = {'notes': notes, 'tasks': tasks, 'reminders': reminders}
        self.memory = memory
        self.contacts = contacts

    def dispatch(self, intent):
        if intent.intent in ('CREATE_MEMORY','SEARCH_MEMORY','LIST_MEMORY','FORGET_MEMORY'):
            return self._dispatch_memory(intent)
        if intent.intent in ('CREATE_CONTACT','UPDATE_CONTACT','DELETE_CONTACT'):
            if self.contacts is None: return DispatchResult(True, intent.intent, route='contacts', result_type='UNAVAILABLE')
            try:
                s = intent.slots
                if intent.intent == 'CREATE_CONTACT': a=self.contacts.prepare_create(s.get('display_name'), s.get('emails',()), s.get('phones',()))
                elif intent.intent == 'UPDATE_CONTACT': a=self.contacts.prepare_update(s.get('target'), s.get('display_name'), s.get('emails',()), s.get('phones',()))
                else: a=self.contacts.prepare_delete(s.get('target'))
                return DispatchResult(True,intent.intent,route='contacts',result_type='PREPARED_ACTION_CREATED',data={'action_id':a.action_id,'action_type':a.action_type,'tool_name':a.tool_name,'summary':a.summary,'state':a.state})
            except Exception as e: return DispatchResult(True,intent.intent,route='contacts',result_type='AMBIGUOUS' if getattr(e,'code','')=='AMBIGUOUS' else 'INVALID' if getattr(e,'code','') not in ('NOT_FOUND',) else 'NOT_FOUND',data={'code':getattr(e,'code','invalid_payload')})
        domain = 'notes' if 'NOTE' in intent.intent else 'tasks' if 'TASK' in intent.intent else 'reminders'
        service = self.services[domain]
        def result(status, **data):
            return DispatchResult(True, intent.intent, route=domain, result_type=status, data=data)
        if service is None: return result('UNAVAILABLE')
        if intent.slots.get('error'): return result('INVALID', code=intent.slots['error'])
        try:
            if intent.intent == 'SEARCH_NOTE':
                query = str(intent.slots.get('query','')).strip().casefold()
                items = [row for row in service.list() if query in (str(row.get('title',''))+' '+str(row.get('content',''))).casefold()]
                if not items: return result('NOT_FOUND', query=query)
                return result('READ_ONLY_RESULT', query=query, items=[{'title':r.get('title',''),'content':r.get('content','')} for r in items])
            if intent.intent.startswith('LIST_'):
                fields = {'notes':('title','content'), 'tasks':('title','due','completed'), 'reminders':('content','trigger_at')}[domain]
                return result('READ_ONLY_RESULT', items=[{k:row.get(k) for k in fields} for row in service.list()])
            raw = str(intent.slots.get('raw','')).strip()
            if not raw: return result('INVALID', code='needs_content')
            if intent.intent.startswith('CREATE_'):
                if domain=='notes': payload={'title':raw[:80], 'content':raw}
                elif domain=='tasks': payload={'title':raw,'due':''}
                else:
                    trigger=service._trigger(intent.slots.get('trigger_at'))
                    payload={'content':raw,'trigger_at':trigger}
                label={'notes':'la note','tasks':'la tâche','reminders':'le rappel'}[domain]
                if domain == 'reminders':
                    try:
                        parsed = datetime.strptime(trigger, '%Y-%m-%dT%H:%M')
                        display = parsed.strftime('%d/%m/%Y à %H:%M')
                    except ValueError:
                        display = trigger
                    summary=f'Créer {label} « {raw[:80]} » pour le {display}'
                else:
                    summary=f'Créer {label} « {raw[:80]} »'
                action=PreparedAction(str(uuid4()),'aura.'+domain,'local_'+domain+'.create',payload,summary)
            else:
                id_field={'notes':'note_id','tasks':'task_id','reminders':'reminder_id'}[domain]
                rows=service.list()
                matches=[r for r in rows if r[id_field]==raw]
                if not matches:
                    matches=[r for r in rows if str(r.get('title') or r.get('content') or '').strip().casefold()==raw.casefold()]
                if not matches: return result('NOT_FOUND')
                if len(matches)!=1: return result('AMBIGUOUS', candidates=len(matches))
                row=matches[0]; label=str(row.get('title') or row.get('content') or '')[:80]
                action=(service.prepare_complete if intent.intent=='COMPLETE_TASK' else service.prepare_delete)(row[id_field],label)
                if action is None: return result('INVALID', code='invalid_target_state')
            self.repository.create(action)
            return result('PREPARED_ACTION_CREATED', action_id=action.action_id, action_type=action.action_type,
                          tool_name=action.tool_name, summary=action.summary, state=action.state, error_code='')
        except ValueError:
            return result('INVALID', code='invalid_payload')
        except Exception:
            return result('FAILED', code='local_service_failed')

    def _dispatch_memory(self, intent):
        if self.memory is None:
            return DispatchResult(True, intent.intent, route='memory', result_type='UNAVAILABLE')
        if intent.intent == 'LIST_MEMORY':
            return DispatchResult(True, intent.intent, route='memory', result_type='READ_ONLY_RESULT', data={'items':[r.as_payload() for r in self.memory.repository.list()]})
        if intent.intent == 'SEARCH_MEMORY':
            query = str(intent.slots.get('query','')).strip()
            return DispatchResult(True, intent.intent, route='memory', result_type='READ_ONLY_RESULT', data={'items':[r.as_payload() for r in self.memory.repository.search(query)]})
        raw = str(intent.slots.get('raw','')).strip()
        if not raw: return DispatchResult(True, intent.intent, route='memory', result_type='INVALID', data={'code':'needs_content'})
        if intent.intent == 'CREATE_MEMORY':
            action = PreparedAction(str(uuid4()), 'aura.memory', 'memory.create', {'content': raw}, f'Garder en mémoire « {raw[:80]} »')
        else:
            rows = self.memory.repository.list()
            matches = [r for r in rows if r.memory_id == raw or r.content.casefold() == raw.casefold()]
            if not matches: return DispatchResult(True, intent.intent, route='memory', result_type='NOT_FOUND')
            if len(matches) != 1: return DispatchResult(True, intent.intent, route='memory', result_type='AMBIGUOUS', data={'candidates':len(matches)})
            row = matches[0]
            action = PreparedAction(str(uuid4()), 'aura.memory', 'memory.forget', {'memory_id': row.memory_id}, f'Oublier « {row.content[:80]} »')
        self.repository.create(action)
        return DispatchResult(True, intent.intent, route='memory', result_type='PREPARED_ACTION_CREATED', data={'action_id':action.action_id,'action_type':action.action_type,'tool_name':action.tool_name,'summary':action.summary,'state':action.state})
