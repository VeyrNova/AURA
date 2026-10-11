import unittest
from pathlib import Path
from aura_native.providers.credentials import FakeProviderCredentialStore, ProviderConfig
from aura_native.providers.service import ProviderSettingsService
class ProviderModelIsolationTests(unittest.TestCase):
 def test_model_change_does_not_switch_provider(self):
  s=ProviderSettingsService(FakeProviderCredentialStore(),[ProviderConfig('openai','OpenAI','api',selected_model='gpt'),ProviderConfig('ollama','Ollama','local',selected_model='qwen3:8b')]); s.set_active('ollama','qwen3:8b'); s.set_active_model('openai','other'); self.assertEqual(s.get_active_provider(),'ollama'); self.assertEqual(s.get_active_model(),'qwen3:8b'); self.assertEqual(s.config('openai').selected_model,'other')
 def test_modal_contract(self):
  s=(Path(__file__).parents[2]/'app/qml/components/ProviderSecretDialog.qml').read_text(encoding='utf-8'); self.assertIn('AuraTextField',s); self.assertIn('passwordMode:true',s); self.assertIn('AuraButton',s)
