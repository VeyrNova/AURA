import importlib.util, unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]; PATH=ROOT/'tests/native/_evidence/pcc3_provider_connection_real.py'
spec=importlib.util.spec_from_file_location('pcc3_harness',PATH); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
class Pcc3HarnessParserTests(unittest.TestCase):
 def test_ollama_guard_accepted(self): self.assertEqual(mod.selected_provider(mod.parse_args(['--ollama','--confirm-real-network'])),'ollama')
 def test_state_dir_accepted(self): self.assertEqual(mod.parse_args(['--gemini','--confirm-real-network','--state-dir','profile']).state_dir,'profile')
 def test_other_provider_guard_accepted(self): self.assertEqual(mod.selected_provider(mod.parse_args(['--gemini','--confirm-real-network'])),'gemini')
 def test_missing_provider_rejected(self):
  with self.assertRaises(SystemExit): mod.parse_args(['--confirm-real-network'])
 def test_multiple_providers_rejected(self):
  with self.assertRaises(SystemExit): mod.parse_args(['--ollama','--gemini','--confirm-real-network'])
 def test_guard_required(self):
  with self.assertRaises(SystemExit): mod.parse_args(['--ollama'])
 def test_no_secret_arguments(self):
  text=PATH.read_text(encoding='utf-8'); self.assertNotIn('--api-key',text); self.assertNotIn('--token',text); self.assertNotIn('--secret',text)
 def test_dispatch_executes_selected_fake_tester_once(self):
  class T:
   def __init__(self): self.calls=0
   def test(self,**kwargs): self.calls+=1; from aura_native.providers.connection import ProviderConnectionResult; return ProviderConnectionResult('ollama',True,'ok','Connexion réussie',0,2,'qwen3:8b')
  t=T(); result=mod.execute('ollama',{'ollama':t},{'ollama':{'selected_model':'qwen3:8b'}}); self.assertTrue(result.success); self.assertEqual(t.calls,1)
