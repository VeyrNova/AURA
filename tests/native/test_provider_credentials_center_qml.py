import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class PCCQmlTests(unittest.TestCase):
 def test_components_and_secret_safety(self):
  card=(ROOT/'app/qml/components/ProviderSettingsCard.qml').read_text(encoding='utf-8'); dlg=(ROOT/'app/qml/components/ProviderSecretDialog.qml').read_text(encoding='utf-8')
  self.assertIn('echoMode:TextInput.Password',dlg); self.assertNotIn('storedSecret',card+dlg); self.assertIn('secret.clear()',dlg)
 def test_integrations_view_and_bridge_only(self):
  view=(ROOT/'app/qml/views/ProviderIntegrationsView.qml').read_text(encoding='utf-8'); self.assertIn('providerConfigs',view); self.assertIn('saveProviderSecret',view); self.assertIn('GOOGLE WORKSPACE',view); self.assertNotIn('getApiKey',view)
 def test_settings_navigation_uses_existing_view(self):
  s=(ROOT/'app/qml/views/SettingsView.qml').read_text(encoding='utf-8'); self.assertIn('ProviderIntegrationsView',s)
