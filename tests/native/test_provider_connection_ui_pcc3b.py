import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class ProviderConnectionUiTests(unittest.TestCase):
 def test_tester_button_and_bridge_api(self):
  c=(ROOT/'app/qml/components/ProviderSettingsCard.qml').read_text(encoding='utf-8'); v=(ROOT/'app/qml/views/ProviderIntegrationsView.qml').read_text(encoding='utf-8'); b=(ROOT/'src/aura_native/ui/qt_bridge.py').read_text(encoding='utf-8')
  self.assertIn('TESTER',c); self.assertIn('testProviderConnection',v); self.assertIn('providerTestStarted',b)
