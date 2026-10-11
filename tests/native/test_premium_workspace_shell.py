import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class PremiumWorkspaceShellTests(unittest.TestCase):
 def test_common_shell_and_memory_controls(self):
  self.assertTrue((ROOT/'app/qml/components/AuraWorkspacePanel.qml').exists()); self.assertTrue((ROOT/'app/qml/components/AuraTextArea.qml').exists()); self.assertTrue((ROOT/'app/qml/components/AuraButton.qml').exists())
  for name in ('SettingsView.qml','MemoryView.qml'):
   self.assertIn('AuraWorkspacePanel', (ROOT/'app/qml/views'/name).read_text(encoding='utf-8'))
 def test_settings_composer_hidden(self): self.assertIn('visible: bridge.workspace !== "settings"',(ROOT/'app/qml/Main.qml').read_text(encoding='utf-8'))
