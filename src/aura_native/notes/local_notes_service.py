from uuid import uuid4
from aura_native.google.models import PreparedAction
class LocalNotesService:
    def __init__(self,repository): self.repository=repository
    def list(self): return self.repository.list()
    def create(self,title,content):
        title=str(title or '').strip(); content=str(content or '').strip()
        return self.repository.create(title,content) if content else None
    def prepare_update(self,note_id,title,content):
        nid=str(note_id or '').strip(); title=str(title or '').strip(); content=str(content or '').strip()
        if not nid or not content or not any(x['note_id']==nid for x in self.repository.list()): return None
        summary=f'Mettre à jour la note « {title} »' if title else 'Mettre à jour cette note ?'
        return PreparedAction(str(uuid4()),'aura.notes','local_notes.update',{'note_id':nid,'title':title,'content':content},summary)
    def prepare_delete(self,note_id,title=''):
        nid=str(note_id or '').strip()
        if not nid or not any(x['note_id']==nid for x in self.repository.list()): return None
        label=str(title or '').strip(); summary=f'Supprimer la note « {label} »' if label else 'Supprimer cette note ?'
        return PreparedAction(str(uuid4()),'aura.notes','local_notes.delete',{'note_id':nid},summary)
    def execute_prepared_action(self,action_id,repository):
        a=repository.get(action_id)
        if not a or a.state!='confirmed' or a.action_type not in ('local_notes.create','local_notes.delete','local_notes.update'): raise ValueError('invalid_prepared_action')
        if a.action_type=='local_notes.create':
            if set(a.payload)!= {'title','content'} or not all(isinstance(v,str) for v in a.payload.values()): raise ValueError('invalid_payload')
            result=self.create(a.payload['title'],a.payload['content'])
            if not result: raise ValueError('invalid_content')
            repository.mark_executed(action_id); return result
        ok = self.repository.delete(a.payload.get('note_id')) if a.action_type=='local_notes.delete' else self.repository.update(a.payload.get('note_id'),str(a.payload.get('title','')),str(a.payload.get('content','')))
        if not ok: raise ValueError('local_note_not_found')
        repository.mark_executed(action_id); return True
