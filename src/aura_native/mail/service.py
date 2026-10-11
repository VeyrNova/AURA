from .models import MailMessage, MailThread

class MailError(Exception): pass

class PermissionRequiredMailBackend:
    """Production state when Gmail read scope has not been granted."""
    def search(self, query): raise MailError('PERMISSION_REQUIRED')
    def list_messages(self): raise MailError('PERMISSION_REQUIRED')
    def get_message(self, message_id): raise MailError('PERMISSION_REQUIRED')
    def get_thread(self, thread_id): raise MailError('PERMISSION_REQUIRED')
    def fetch_attachment(self, message_id, attachment_id): raise MailError('PERMISSION_REQUIRED')
    def create_draft(self, payload): raise MailError('WRITE_NOT_SUPPORTED')
    def send(self, payload): raise MailError('WRITE_NOT_SUPPORTED')

class FakeMailBackend:
    def __init__(self, messages=None, failure=None):
        self.messages=list(messages or [MailMessage('m1','t1','alice@example.test',('me@example.test',),'Bonjour','Salut','Salut, voici le message.','2026-10-03T09:00:00Z',attachments=({'id':'a1','name':'agenda.txt','size':12},))]); self.failure=failure; self.sent=[]; self.drafts=[]
    def _check(self):
        if self.failure: raise MailError(self.failure)
    def search(self, query):
        self._check(); q=str(query or '').casefold().strip()
        return [m for m in self.messages if not q or q in (m.subject+' '+m.sender+' '+m.snippet+' '+m.body).casefold()]
    def list_messages(self): self._check(); return list(self.messages)
    def get_message(self, message_id):
        self._check(); return next((m for m in self.messages if m.message_id==str(message_id)),None)
    def get_thread(self, thread_id):
        self._check(); return MailThread(str(thread_id),tuple(m for m in self.messages if m.thread_id==str(thread_id)))
    def fetch_attachment(self, message_id, attachment_id):
        self._check(); msg=self.get_message(message_id); return next((a for a in (msg.attachments if msg else ()) if a.get('id')==str(attachment_id)),None)
    def create_draft(self, payload): self._check(); self.drafts.append(dict(payload)); return self.drafts[-1]
    def send(self, payload): self._check(); self.sent.append(dict(payload)); return self.sent[-1]

class MailService:
    def __init__(self, backend): self.backend=backend
    def search(self, query): return tuple(self.backend.search(query))
    def list_messages(self):
        if hasattr(self.backend, 'list_messages'): return tuple(self.backend.list_messages())
        return tuple(self.backend.search(''))
    def get_message(self, message_id): return self.backend.get_message(message_id)
    def get_thread(self, thread_id): return self.backend.get_thread(thread_id)
    def fetch_attachment(self, message_id, attachment_id): return self.backend.fetch_attachment(message_id,attachment_id)
    def prepare_draft(self, payload): return dict(payload)
    def prepare_send(self, payload): return dict(payload)
    def execute_draft(self, payload): return self.backend.create_draft(payload)
    def execute_send(self, payload): return self.backend.send(payload)
