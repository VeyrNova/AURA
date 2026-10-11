import json,tempfile,unittest
from pathlib import Path
from aura_native.google.auth import *
class AuthB1Tests(unittest.TestCase):
 def test_config_and_scopes_offline(self):
  self.assertEqual(GoogleAuthProvider().get_state().error_code,'google_not_configured');self.assertEqual(GOOGLE_SCOPE_VERSION,'google-scopes-v1')
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'client.json';p.write_text('{bad',encoding='utf8')
   with self.assertRaises(GoogleAuthError) as e:GoogleOAuthConfig(p).validate()
   self.assertEqual(e.exception.code,'google_client_file_invalid');p.write_text(json.dumps({'installed':{'client_id':'x','auth_uri':'a','token_uri':'t'}}),encoding='utf8');self.assertTrue(GoogleOAuthConfig(p).validate())
 def test_fake_store_roundtrip_and_metadata(self):
  s=FakeGoogleCredentialStore();c={'token':'ACCESS','refresh_token':'REFRESH','scopes':list(CALENDAR_SCOPES+TASKS_SCOPES),'account_email':'a@example.com'};s.save('a',c);self.assertEqual(s.load('a'),c);self.assertTrue(s.exists('a'));s.delete('a');self.assertFalse(s.exists('a'));self.assertNotIn('REFRESH',GoogleCredentialMetadata('a',c['scopes'],None,True).__repr__())
 def test_authenticated_scope_and_mismatch(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'c.json';p.write_text(json.dumps({'installed':{'client_id':'x','auth_uri':'a','token_uri':'t'}}),encoding='utf8');s=FakeGoogleCredentialStore();s.save('default',{'scopes':list(CALENDAR_SCOPES+TASKS_SCOPES),'account_email':'a'});self.assertTrue(GoogleAuthProvider(GoogleOAuthConfig(p),s).get_state().authenticated);s.save('default',{'scopes':[]});self.assertEqual(GoogleAuthProvider(GoogleOAuthConfig(p),s).get_state().error_code,'google_scope_mismatch')
if __name__=='__main__':unittest.main()
