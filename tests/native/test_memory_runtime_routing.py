import os, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class MemoryRuntimeRoutingTests(unittest.TestCase):
 def test_native_route_instantiates_memory_view_and_excludes_fallback(self):
  s=(ROOT/'app/qml/views/NativeWorkspaceView.qml').read_text(encoding='utf-8')
  self.assertIn('MemoryView {',s); self.assertIn('objectName: "auraPremiumMemoryView"',s)
  self.assertIn('root.workspace !== "memory"',s)
 def test_premium_memory_contract(self):
  s=(ROOT/'app/qml/views/MemoryView.qml').read_text(encoding='utf-8')
  for token in ('auraPremiumMemoryWorkspace','AuraWorkspacePanel','AuraTextArea','AuraTextField','AuraButton','Aucun souvenir enregistré'):
   self.assertIn(token,s)
 def test_fresh_memory_qml_loads(self):
  with tempfile.TemporaryDirectory() as state:
   env=os.environ.copy(); env.update({'PYTHONPATH':str(ROOT/'src'),'PYTHONDONTWRITEBYTECODE':'1','QT_QPA_PLATFORM':'offscreen','AURA_NATIVE_WORKSPACE':'memory'})
   result=subprocess.run([sys.executable,'-B',str(ROOT/'app/main.py'),'--core-mode','native','--state-dir',state,'--qml-self-check'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=20)
   self.assertEqual(result.returncode,0,result.stderr)
