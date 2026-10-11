import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class ProviderSelectorPopupTests(unittest.TestCase):
 def test_responsive_popup_and_separate_status(self):
  s=(ROOT/'app/qml/components/ProviderSelectorPopup.qml').read_text(encoding='utf-8'); self.assertIn('Math.min(360',s); self.assertIn('anchors.right:status.left',s); self.assertIn('enabled:modelData.configured',s)
 def test_selection_and_delete_label(self):
  v=(ROOT/'app/qml/views/ProviderIntegrationsView.qml').read_text(encoding='utf-8'); self.assertIn('ProviderSelectorPopup',v); self.assertIn('setActiveProvider',v); self.assertIn('confirmLabel:"SUPPRIMER"',v)
