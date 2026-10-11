import unittest
from aura_native.providers.connection import FakeProviderConnectionTester,ProviderConnectionResult,sanitize_error
class ProviderConnectionPcc3Tests(unittest.TestCase):
 def test_fake_results_are_normalized_and_non_secret(self):
  r=FakeProviderConnectionTester({'openai':'authentication_failed'}).test('openai',{'selected_model':'x','secret':'never-return'})
  self.assertFalse(r.success); self.assertEqual(r.status,'authentication_failed'); self.assertNotIn('never-return',repr(r))
 def test_fake_success_and_model(self):
  r=FakeProviderConnectionTester().test('ollama',{'selected_model':'qwen3:8b'}); self.assertTrue(r.success); self.assertEqual(r.tested_model,'qwen3:8b')
 def test_sanitize(self):
  s=sanitize_error('Authorization: Bearer secret-value?key=abc'); self.assertNotIn('secret-value',s); self.assertNotIn('abc',s)
