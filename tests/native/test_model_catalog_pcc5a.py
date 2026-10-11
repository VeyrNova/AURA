import unittest
import runpy
from aura_native.providers.model_catalog import FakeModelCatalogProvider, ModelCatalogError, ModelCatalogService


class CatalogTests(unittest.TestCase):
    def test_harness_parser_large_catalog_flag(self):
        ns = runpy.run_path("tests/native/_evidence/pcc5_model_catalog_ui.py", run_name="pcc5_parser_test")
        self.assertTrue(ns["main"](["--headless", "--provider", "gemini", "--large-catalog", "--state-dir", "tests/native/_evidence/parser-state"]) == 0)
    def setUp(self): self.fake=FakeModelCatalogProvider(); self.service=ModelCatalogService({"ollama":self.fake,"gemini":self.fake})
    def test_refresh_is_explicit_and_normalized(self):
        self.assertEqual(self.fake.calls, []); values=self.service.refresh_models("ollama")
        self.assertEqual([v.model_id for v in values], ["qwen3:8b", "llama-test:latest"])
        self.assertTrue(all(v.metadata_safe and v.is_local for v in values)); self.assertEqual(self.service.get_state("ollama"), "success")
    def test_provider_isolation(self):
        self.service.refresh_models("ollama"); self.service.refresh_models("gemini")
        self.assertEqual(self.service.get_models("ollama")[0].provider_id, "ollama")
        self.assertEqual(self.service.get_models("gemini")[0].provider_id, "gemini")
    def test_empty_catalog_does_not_select(self):
        fake=FakeModelCatalogProvider({"gemini": ()}); service=ModelCatalogService({"gemini":fake})
        self.assertEqual(service.refresh_models("gemini"), ()); self.assertEqual(service.get_models("gemini"), ())
    def test_error_preserves_previous_catalog(self):
        self.service.refresh_models("ollama"); self.fake.error="network_error"
        with self.assertRaises(ModelCatalogError) as caught: self.service.refresh_models("ollama")
        self.assertEqual(caught.exception.code, "network_error"); self.assertEqual(len(self.service.get_models("ollama")), 2)
    def test_unknown_provider_and_no_secrets(self):
        with self.assertRaises(ModelCatalogError): self.service.refresh_models("unknown")
        self.assertNotIn("PCC5_SECRET_SENTINEL_DO_NOT_LEAK", repr(self.service.get_models("ollama")))


if __name__ == "__main__": unittest.main()
