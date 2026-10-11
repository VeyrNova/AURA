import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class Pcc2dUiPolishTests(unittest.TestCase):
 def test_custom_input_and_compact_card(self):
  self.assertTrue((ROOT/'app/qml/components/AuraTextField.qml').exists()); s=(ROOT/'app/qml/components/ProviderSettingsCard.qml').read_text(encoding='utf-8'); self.assertIn('AuraTextField',s); self.assertNotIn('TextField {',s)
 def test_ollama_local_and_custom_url(self):
  s=(ROOT/'app/qml/components/ProviderSettingsCard.qml').read_text(encoding='utf-8'); self.assertIn('● LOCAL',s); self.assertIn('base_url',s); self.assertIn('ENREGISTRER',s)
 def test_selector_and_composer_settings(self):
  s=(ROOT/'app/qml/views/ProviderIntegrationsView.qml').read_text(encoding='utf-8'); self.assertIn('setActiveProvider',s); self.assertIn('FOURNISSEUR PRINCIPAL',s)
  m=(ROOT/'app/qml/Main.qml').read_text(encoding='utf-8'); self.assertIn('visible: bridge.workspace !== "settings"',m)
 def test_google_and_gemini_are_distinct(self):
  s=(ROOT/'app/qml/views/ProviderIntegrationsView.qml').read_text(encoding='utf-8'); self.assertIn('GOOGLE WORKSPACE',s); c=(ROOT/'app/qml/components/ProviderSettingsCard.qml').read_text(encoding='utf-8'); self.assertIn('Indépendant de Google Workspace',c)
