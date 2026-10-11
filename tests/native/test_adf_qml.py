import unittest
from pathlib import Path
class ADFQmlTests(unittest.TestCase):
 def setUp(self): self.qml=Path('app/qml/views/DeveloperFabricView.qml').read_text(encoding='utf-8')
 def test_surface_and_no_webengine(self):
  for token in ('AURA DEVELOPER FABRIC','NOUVELLE DEMANDE','JOBS','WORKFLOW','AGENTS / PROVIDERS'): self.assertIn(token,self.qml)
  for token in ('WebEngine','fetch(','localhost','<html>'): self.assertNotIn(token,self.qml)
 def test_safe_controls(self):
  self.assertIn('developerFabricBridge.enableDeveloperMode()',self.qml); self.assertIn('developerFabricBridge.disableDeveloperMode()',self.qml)
 def test_mode_gates_request(self): self.assertIn('developerFabricBridge.developerModeEnabled && developerFabricBridge.hasActiveProject',self.qml)
 def test_agents_model(self): self.assertIn('developerAgentsModel',self.qml)
 def test_native_navigation_view(self): self.assertTrue(Path('app/qml/views/NativeWorkspaceView.qml').exists())
if __name__=='__main__': unittest.main()
