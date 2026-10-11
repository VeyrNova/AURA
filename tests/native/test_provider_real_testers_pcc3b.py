import unittest
from aura_native.providers.connection import *
from aura_native.providers.credentials import FakeProviderCredentialStore
class MockHttp:
 def __init__(self,status=200,payload=None): self.status=status; self.payload=payload or {'data':[1,2]}; self.calls=[]
 def get_json(self,url,headers,timeout): self.calls.append((url,headers,timeout)); return HttpResponse(self.status,self.payload)
class ProviderRealTesterTests(unittest.TestCase):
 def setUp(self): self.store=FakeProviderCredentialStore(); self.store.set_secret('openai','PCC3_SECRET_SENTINEL_DO_NOT_LEAK'); self.store.set_secret('anthropic','a'); self.store.set_secret('gemini','g')
 def test_openai_mapping_and_no_result_secret(self):
  h=MockHttp(200); r=OpenAIConnectionTester(self.store, h).test(config={'selected_model':'x'}); self.assertTrue(r.success); self.assertNotIn('PCC3_SECRET',repr(r)); self.assertIn('Authorization',h.calls[0][1])
 def test_status_mapping(self):
  for code,status in ((401,'authentication_failed'),(403,'permission_denied'),(429,'rate_limited'),(500,'provider_unavailable')):
   self.assertEqual(OpenAIConnectionTester(self.store,MockHttp(code)).test().status,status)
 def test_anthropic_gemini_ollama_custom(self):
  self.assertTrue(AnthropicConnectionTester(self.store,MockHttp()).test().success); self.assertTrue(GeminiConnectionTester(self.store,MockHttp()).test().success)
  self.assertTrue(OllamaConnectionTester(http=MockHttp()).test(config={'base_url':'http://127.0.0.1:11434','selected_model':'qwen3:8b'}).success)
  self.assertTrue(OpenAICompatibleConnectionTester(self.store,MockHttp()).test(config={'base_url':'https://example.test','selected_model':'m'}).success)
 def test_invalid_custom_and_timeout(self):
  self.assertEqual(OpenAICompatibleConnectionTester(self.store,MockHttp()).test(config={'base_url':'file:///x'}).status,'invalid_configuration')
  class T:
   def get_json(self,*a): raise TimeoutError()
  self.assertEqual(OllamaConnectionTester(http=T()).test(config={'base_url':'http://localhost'}).status,'timeout')
