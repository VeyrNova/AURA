import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class MemoryPremiumWorkspaceTests(unittest.TestCase):
 def test_memory_uses_aura_controls_and_empty_state(self):
  s=(ROOT/'app/qml/views/MemoryView.qml').read_text(encoding='utf-8')
  self.assertIn('AuraWorkspacePanel',s); self.assertIn('AuraTextArea',s); self.assertIn('AuraTextField',s); self.assertIn('Aucun souvenir enregistré',s)
 def test_composer_hidden_for_memory(self):
  self.assertIn('bridge.workspace !== "memory"',(ROOT/'app/qml/Main.qml').read_text(encoding='utf-8'))
