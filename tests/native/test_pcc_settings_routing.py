import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class PccSettingsRoutingTests(unittest.TestCase):
    def test_native_settings_uses_settings_view(self):
        s=(ROOT/'app/qml/views/NativeWorkspaceView.qml').read_text(encoding='utf-8')
        self.assertIn('SettingsView {',s); self.assertIn('root.workspace === "settings"',s)
        self.assertIn('root.workspace !== "settings"',s)
    def test_settings_integrations_view_is_provider_view(self):
        s=(ROOT/'app/qml/views/SettingsView.qml').read_text(encoding='utf-8')
        self.assertIn('ProviderIntegrationsView {',s)
    def test_launcher_requests_settings_workspace(self):
        s=(ROOT/'tests/native/_evidence/provider_credentials_center_ui.py').read_text(encoding='utf-8')
        self.assertIn("'AURA_NATIVE_WORKSPACE':'settings'",s)
    def test_memory_route_remains_separate(self):
        s=(ROOT/'app/qml/views/NativeWorkspaceView.qml').read_text(encoding='utf-8')
        self.assertIn('root.workspace === "memory"',s)

    def test_settings_has_no_obsolete_refresh_locale_bridge_call(self):
        s=(ROOT/'app/qml/views/SettingsView.qml').read_text(encoding='utf-8')
        self.assertNotIn('refreshLocale()',s)
