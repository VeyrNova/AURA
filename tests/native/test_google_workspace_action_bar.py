import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class GoogleWorkspaceActionBarTests(unittest.TestCase):
 def test_uses_aura_button_and_internal_margins(self):
  s=(ROOT/'app/qml/views/ProviderIntegrationsView.qml').read_text(encoding='utf-8')
  self.assertIn('AuraButton{',s); self.assertIn('anchors.margins:12',s); self.assertIn('IMPORTER UN CLIENT OAUTH',s)
  self.assertNotIn('Text{text:"IMPORTER UN CLIENT OAUTH"',s)
 def test_google_and_language_sections_remain_distinct(self):
  s=(ROOT/'app/qml/views/ProviderIntegrationsView.qml').read_text(encoding='utf-8')
  self.assertIn('GOOGLE WORKSPACE',s); self.assertIn('LANGUE / LANGUAGE',s); self.assertIn('Row{width:parent.width',s)
