import unittest
from aura_native.mail.gmail_adapter import GmailMailBackend, GMAIL_READ_SCOPE
from aura_native.mail.service import MailService
from aura_native.google.providers import GoogleProviderError

class Resp:
    def __init__(self,value): self.value=value
    def execute(self): return self.value
class Messages:
    def __init__(self): self.raw={'id':'m1','threadId':'t1','snippet':'hello','payload':{'headers':[{'name':'From','value':'a@example.test'},{'name':'Subject','value':'Hello'}]}}
    def list(self,**kw): return Resp({'messages':[{'id':'m1'}]})
    def get(self,**kw): return Resp(self.raw)
    def attachments(self): return self
    def __call__(self,**kw): return self
    def execute(self): return {'data':'abc','size':3}
class Users:
    def __init__(self): self.messages_obj=Messages()
    def messages(self): return self.messages_obj
    def threads(self): return self
    def get(self,**kw): return Resp({'messages':[self.messages_obj.raw]})
class Api:
    def users(self): return Users()
class Auth:
    def __init__(self,scopes=(GMAIL_READ_SCOPE,)): self.scopes=scopes
    def get_state(self): return type('S',(),{'authenticated':True,'scopes':self.scopes})()
    def get_credentials(self): return object()
class GmailAdapterTests(unittest.TestCase):
    def test_read_contract_and_scope(self):
        backend=GmailMailBackend(Auth(),build=lambda *a,**k:Api()); service=MailService(backend)
        self.assertEqual(service.search('hello')[0].subject,'Hello'); self.assertEqual(service.get_message('m1').message_id,'m1'); self.assertEqual(service.get_thread('t1').messages[0].thread_id,'t1')
    def test_scope_is_explicitly_required(self):
        with self.assertRaises(GoogleProviderError) as ctx:GmailMailBackend(Auth(()),build=lambda *a,**k:Api()).search('x')
        self.assertEqual(ctx.exception.code,'PERMISSION_REQUIRED')
if __name__=='__main__':unittest.main()
