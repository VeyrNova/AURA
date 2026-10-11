import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class PccSingleSettingsPanelTests(unittest.TestCase):
    def test_legacy_settings_panel_is_not_visible(self):
        s=(ROOT/'app/qml/views/SettingsView.qml').read_text(encoding='utf-8')
        self.assertIn('id: panel',s); self.assertIn('visible: false',s)
    def test_integrations_is_single_visible_settings_content(self):
        s=(ROOT/'app/qml/views/SettingsView.qml').read_text(encoding='utf-8')
        self.assertEqual(s.count('ProviderIntegrationsView {'),1)
        v=(ROOT/'app/qml/views/ProviderIntegrationsView.qml').read_text(encoding='utf-8')
        self.assertIn('LANGUE / LANGUAGE',v); self.assertIn('setLocale',v)
    def test_no_launcher_specific_hiding(self):
        s=(ROOT/'tests/native/_evidence/provider_credentials_center_ui.py').read_text(encoding='utf-8')
        self.assertNotIn('visible:false',s.replace(' ',''))
