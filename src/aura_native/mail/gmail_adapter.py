"""Read-only Gmail adapter over the existing GoogleAuthProvider identity."""
from .models import MailMessage, MailThread
from aura_native.google.providers import GoogleProviderError
from aura_native.google.transport import build_authorized_service, normalized_transport_error

GMAIL_READ_SCOPE='https://www.googleapis.com/auth/gmail.readonly'

def _error(exc):
    transport = normalized_transport_error(exc)
    if transport: return transport
    status=getattr(exc,'status_code',getattr(getattr(exc,'resp',None),'status',None))
    return {'401':'AUTH_UNAVAILABLE','403':'PERMISSION_REQUIRED','404':'NOT_FOUND','429':'RATE_LIMITED'}.get(str(status),'API_ERROR')

class GmailMailBackend:
    capabilities={'search':True,'list':True,'read_message':True,'read_thread':True,'read_attachment':True,'write':False}
    def __init__(self, auth, *, build=None, page_size=25): self.auth,self.build,self.page_size=auth,build,max(1,min(int(page_size),100))
    def _service(self):
        state=self.auth.get_state()
        if not state.authenticated: raise GoogleProviderError('AUTH_UNAVAILABLE')
        if GMAIL_READ_SCOPE not in state.scopes: raise GoogleProviderError('PERMISSION_REQUIRED')
        try:
            if self.build:return self.build('gmail','v1',credentials=self.auth.get_credentials(),cache_discovery=False)
            return build_authorized_service('gmail','v1',self.auth.get_credentials())
        except GoogleProviderError: raise
        except Exception as exc: raise GoogleProviderError(_error(exc)) from exc
    def _message(self, raw):
        headers={str(h.get('name','')).lower():str(h.get('value','')) for h in (raw.get('payload') or {}).get('headers',()) if isinstance(h,dict)}
        body=str(raw.get('snippet') or '')
        return MailMessage(str(raw.get('id','')),str(raw.get('threadId','')),headers.get('from',''),tuple(x.strip() for x in headers.get('to','').split(',') if x.strip()),headers.get('subject',''),str(raw.get('snippet') or ''),body,headers.get('date',''), 'UNREAD' in (raw.get('labelIds') or ()),())
    def search(self, query):
        try:
            api=self._service(); messages=api.users().messages()
            listing=messages.list(userId='me',q=str(query or ''),maxResults=self.page_size).execute(); out=[]
            for item in listing.get('messages') or ():
                raw=messages.get(userId='me',id=item.get('id'),format='metadata').execute(); out.append(self._message(raw))
            return out
        except GoogleProviderError: raise
        except Exception as exc: raise GoogleProviderError(_error(exc)) from exc
    def list_messages(self):
        return self.search("")
    def get_message(self, message_id):
        try:return self._message(self._service().users().messages().get(userId='me',id=str(message_id),format='full').execute())
        except Exception as exc: raise GoogleProviderError(_error(exc)) from exc
    def get_thread(self, thread_id):
        try:
            raw=self._service().users().threads().get(userId='me',id=str(thread_id),format='full').execute(); return MailThread(str(thread_id),tuple(self._message(x) for x in raw.get('messages') or ()))
        except Exception as exc: raise GoogleProviderError(_error(exc)) from exc
    def fetch_attachment(self, message_id, attachment_id):
        try:
            raw=self._service().users().messages().attachments().get(userId='me',messageId=str(message_id),id=str(attachment_id)).execute(); return {'id':str(attachment_id),'content':raw.get('data'),'size':raw.get('size',0)}
        except Exception as exc: raise GoogleProviderError(_error(exc)) from exc
    def create_draft(self, payload): raise GoogleProviderError('WRITE_NOT_SUPPORTED')
    def send(self, payload): raise GoogleProviderError('WRITE_NOT_SUPPORTED')
