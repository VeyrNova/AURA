import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class ProviderTestUiWiringTests(unittest.TestCase):
 def test_card_calls_bridge_and_handles_states(self):
  c=(ROOT/'app/qml/components/ProviderSettingsCard.qml').read_text(encoding='utf-8'); v=(ROOT/'app/qml/views/ProviderIntegrationsView.qml').read_text(encoding='utf-8')
  self.assertIn('testProvider',c); self.assertIn('onProviderTestStarted',c); self.assertIn('onProviderTestFinished',c); self.assertIn('bridge.testProviderConnection(id)',v)
 def test_bridge_slot_and_safe_signal(self):
  b=(ROOT/'src/aura_native/ui/qt_bridge.py').read_text(encoding='utf-8'); self.assertIn('@Slot(str)',b); self.assertIn('Signal(str, "QVariantMap")',b); self.assertNotIn('get_secret',b)
 def test_debug_qml_marker_is_safe_and_opt_in(self):
  c=(ROOT/'app/qml/components/ProviderSettingsCard.qml').read_text(encoding='utf-8'); b=(ROOT/'src/aura_native/ui/qt_bridge.py').read_text(encoding='utf-8')
  marker=c[c.index('PCC3_QML_FINISHED provider='):c.index('PCC3_QML_FINISHED provider=')+160]
  self.assertIn('pcc3DebugEnabled',c); self.assertIn('PCC3_QML_FINISHED provider=',marker); self.assertIn('AURA_PCC3_DEBUG',b); self.assertNotIn('result.message',marker)
