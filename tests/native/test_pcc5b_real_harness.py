import contextlib, io, importlib.util, unittest
from unittest.mock import patch
from aura_native.providers.model_catalog import ProviderModelDescriptor

SPEC=importlib.util.spec_from_file_location("pcc5_real_harness","tests/native/_evidence/pcc5_real_model_catalog.py"); MOD=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MOD)
class HarnessTests(unittest.TestCase):
 def test_guard_and_parser(self):
  with self.assertRaises(SystemExit) as c: MOD.main(["--ollama","--state-dir","x"])
  self.assertEqual(c.exception.code,2)
  with self.assertRaises(SystemExit): MOD.main(["--state-dir","x"])
  with self.assertRaises(SystemExit): MOD.main(["--ollama","--gemini","--confirm-real-network","--state-dir","x"])
 def test_ollama_dispatch_once_and_safe_output(self):
  fake=patch.object(MOD.OllamaModelCatalogProvider,"list_models",return_value=(ProviderModelDescriptor("ollama","qwen3:8b","qwen3:8b"),ProviderModelDescriptor("ollama","x","x")))
  with fake as method,contextlib.redirect_stdout(io.StringIO()) as out: self.assertEqual(MOD.main(["--ollama","--confirm-real-network","--state-dir","x"]),0)
  self.assertEqual(method.call_count,1); self.assertIn("models_available=2",out.getvalue()); self.assertNotIn("secret",out.getvalue().lower())
 def test_gemini_dispatch_once(self):
  with patch.object(MOD.GeminiModelCatalogProvider,"list_models",return_value=()) as method,patch.object(MOD,"KeyringProviderCredentialStore",return_value=object()):
   self.assertEqual(MOD.main(["--gemini","--confirm-real-network","--state-dir","x"]),0); self.assertEqual(method.call_count,1)
 def test_no_api_key_option(self):
  with self.assertRaises(SystemExit): MOD.main(["--ollama","--api-key","x","--confirm-real-network","--state-dir","x"])
if __name__=='__main__': unittest.main()
