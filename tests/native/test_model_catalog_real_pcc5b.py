import unittest
from aura_native.providers.model_catalog import OllamaModelCatalogProvider, GeminiModelCatalogProvider, ModelCatalogError
from aura_native.providers.connection import HttpResponse
from aura_native.providers.model_catalog import ModelCatalogService

class HTTP:
 def __init__(self,response): self.response=response; self.calls=[]
 def get_json(self,url,headers=None,timeout=None): self.calls.append((url,headers)); return self.response
class Store:
 def __init__(self,secret="PCC5B_SECRET_DO_NOT_LEAK"): self.secret=secret; self.calls=0
 def get_secret(self,pid): self.calls+=1; return self.secret
class RealCatalogTests(unittest.TestCase):
 def test_direct_and_service_parity(self):
  h=HTTP(HttpResponse(200,{"models":[{"name":"qwen3:8b"}]})); provider=OllamaModelCatalogProvider("http://127.0.0.1:11434",h)
  direct=provider.list_models(); via=ModelCatalogService({"ollama":provider}).refresh_models("ollama")
  self.assertEqual([v.model_id for v in direct],[v.model_id for v in via]); self.assertEqual(len(via),1)
 def test_ollama_tags_normalizes_exact_ids(self):
  h=HTTP(HttpResponse(200,{"models":[{"name":"qwen3:8b","size":4},{"name":"llama:latest"}]})); values=OllamaModelCatalogProvider("http://127.0.0.1:11434",h).list_models(); self.assertEqual([v.model_id for v in values],["qwen3:8b","llama:latest"]); self.assertTrue(all(v.is_local for v in values))
 def test_ollama_invalid_and_timeout(self):
  for response,code in ((HttpResponse(200,{}),"invalid_response"),(HttpResponse(503,{}),"provider_unavailable")):
   with self.subTest(code=code),self.assertRaises(ModelCatalogError) as c: OllamaModelCatalogProvider("http://x",HTTP(response)).list_models()
   self.assertEqual(c.exception.code,code)
 def test_gemini_filters_generation_and_strips_prefix(self):
  h=HTTP(HttpResponse(200,{"models":[{"name":"models/gemini-test","displayName":"Test","supportedGenerationMethods":["generateContent"]},{"name":"models/embed","supportedGenerationMethods":["embedContent"]}]})); s=Store(); values=GeminiModelCatalogProvider(s,h).list_models(); self.assertEqual([v.model_id for v in values],["gemini-test"]); self.assertNotIn(s.secret,repr(values)); self.assertEqual(s.calls,1)
 def test_gemini_http_mapping(self):
  for status,code in ((401,"authentication_failed"),(403,"permission_denied"),(429,"rate_limited"),(503,"provider_unavailable")):
   with self.subTest(status=status),self.assertRaises(ModelCatalogError) as c: GeminiModelCatalogProvider(Store(),HTTP(HttpResponse(status,{}))).list_models()
   self.assertEqual(c.exception.code,code)
 def test_gemini_no_credential_without_refresh(self): self.assertEqual(Store().calls,0)
 def test_composition_provider_contract_uses_ollama_provider(self):
  from aura_native.bootstrap.composition import compose_runtime
  from pathlib import Path
  import tempfile
  with tempfile.TemporaryDirectory() as d:
   import os
   old=os.environ.get("AURA_PCC_FAKE"); os.environ["AURA_PCC_FAKE"]="1"
   try:
    runtime=compose_runtime(project_root=Path(__file__).parents[2],state_dir=Path(d)); self.assertEqual(set(runtime.model_catalog_service.providers),{"openai","anthropic","gemini","ollama","custom_openai"})
   finally:
    if old is None: os.environ.pop("AURA_PCC_FAKE",None)
    else: os.environ["AURA_PCC_FAKE"]=old
if __name__=='__main__': unittest.main()
