import unittest
from aura_native.providers.credentials import FakeProviderCredentialStore,ProviderConfig,ProviderCredentialError
from aura_native.providers.service import ProviderSettingsService
class ProviderCredentialsCenterTests(unittest.TestCase):
 def setUp(self):
  self.store=FakeProviderCredentialStore(); self.service=ProviderSettingsService(self.store,(ProviderConfig('openai','OpenAI','api',credential_required=True),ProviderConfig('ollama','Ollama','local',credential_required=False)))
 def test_secret_never_enters_config_model(self):
  self.service.save_api_key('openai','test-openai-key'); self.assertTrue(self.service.provider_configured('openai')); self.assertFalse(hasattr(self.service.config('openai'),'secret')); self.assertNotIn('test-openai-key',repr(self.service.config('openai')))
 def test_replace_and_remove(self):
  self.service.save_api_key('openai','first'); self.service.save_api_key('openai','second'); self.assertEqual(self.store.get_secret('openai'),'second'); self.service.remove_api_key('openai'); self.assertFalse(self.service.provider_configured('openai'))
 def test_empty_secret_refused(self):
  with self.assertRaises(ProviderCredentialError): self.service.save_api_key('openai','')
 def test_ollama_has_no_required_secret(self): self.assertFalse(self.service.provider_configured('ollama'))
