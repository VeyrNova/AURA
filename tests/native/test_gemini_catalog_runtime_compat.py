from pathlib import Path
import unittest

ROOT = Path(__file__).parents[2]


class GeminiCatalogRuntimeCompatibilityTests(unittest.TestCase):
    def test_catalog_uses_generate_content_capability(self):
        source = (ROOT / "src/aura_native/providers/model_catalog.py").read_text(encoding="utf-8")
        self.assertIn('"generateContent" not in methods', source)
        self.assertIn('raw.removeprefix("models/")', source)

    def test_runtime_strips_resource_prefix_once(self):
        source = (ROOT / "src/aura_native/agent/provider.py").read_text(encoding="utf-8")
        self.assertIn('model_path=self.model.removeprefix("models/")', source)
        self.assertNotIn("models/models/", source)


if __name__ == "__main__": unittest.main()
