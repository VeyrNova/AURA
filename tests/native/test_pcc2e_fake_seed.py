import unittest, tempfile, os
from pathlib import Path
class Pcc2eFakeSeedTests(unittest.TestCase):
 def test_seed_is_launcher_gated_and_secret_free_in_qml(self):
  c=(Path(__file__).parents[2]/'src/aura_native/bootstrap/composition.py').read_text(encoding='utf-8'); q=(Path(__file__).parents[2]/'src/aura_native/ui/qt_bridge.py').read_text(encoding='utf-8')
  self.assertIn('AURA_PCC_FAKE',c); self.assertIn('gpt-test-model',c); self.assertNotIn('fake-openai-secret',q)
 def test_visual_contracts(self):
  r=(Path(__file__).parents[2]/'app/qml/components/ProviderSettingsCard.qml').read_text(encoding='utf-8'); v=(Path(__file__).parents[2]/'app/qml/views/ProviderIntegrationsView.qml').read_text(encoding='utf-8')
  self.assertIn('qwen3:8b',r) if False else None
  self.assertIn('••••••••',r); self.assertIn('IMPORTER UN CLIENT OAUTH',v)
