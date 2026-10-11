import json,tempfile,unittest
from pathlib import Path
from aura_native.google.auth import *
class FakeCredentials:
 token='access';refresh_token='refresh';scopes=CALENDAR_SCOPES+TASKS_SCOPES;expiry=None
class FakeFlow:
 def run_local_server(self,**kwargs):self.kwargs=kwargs;return FakeCredentials()
class OAuthB2Tests(unittest.TestCase):
 def config(self,d):
  p=Path(d)/'client.json';p.write_text(json.dumps({'installed':{'client_id':'x','auth_uri':'a','token_uri':'t'}}),encoding='utf8');return GoogleOAuthConfig(p)
 def test_fake_connect_reload_disconnect(self):
  with tempfile.TemporaryDirectory() as d:
   s=FakeGoogleCredentialStore();p=GoogleAuthProvider(self.config(d),s,lambda c:FakeFlow());state=p.connect();self.assertTrue(state.authenticated);self.assertTrue(s.exists('default'));self.assertTrue(GoogleAuthProvider(self.config(d),s).get_state().authenticated);p.delete_credentials();self.assertFalse(s.exists('default'))
 def test_flow_uses_loopback_dynamic_port_and_scopes(self):
  with tempfile.TemporaryDirectory() as d:
   seen={};s=FakeGoogleCredentialStore();p=GoogleAuthProvider(self.config(d),s,lambda c:FakeFlow());f=FakeFlow();p.flow_factory=lambda c:f;p.connect();self.assertEqual(f.kwargs['host'],'127.0.0.1');self.assertEqual(f.kwargs['port'],0);self.assertTrue(f.kwargs['open_browser'])
 def test_failed_flow_does_not_store(self):
  with tempfile.TemporaryDirectory() as d:
   s=FakeGoogleCredentialStore();p=GoogleAuthProvider(self.config(d),s,lambda c: (_ for _ in ()).throw(RuntimeError('cancelled')))
   with self.assertRaises(GoogleAuthError):p.connect()
   self.assertFalse(s.exists('default'))
if __name__=='__main__':unittest.main()
