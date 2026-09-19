from __future__ import annotations
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MAIN = (ROOT / 'ui' / 'main_window.py').read_text(encoding='utf-8') if (ROOT / 'ui' / 'main_window.py').exists() else (Path(__file__).resolve().parents[1] / 'ui' / 'main_window.py').read_text(encoding='utf-8')

class Patch2684Tests(unittest.TestCase):
    def test_document_fast_lane_exists(self):
        self.assertIn('def _start_document_analysis_fast_lane', MAIN)
        self.assertIn('Document FAST lane dispatched provider=%s model=%s', MAIN)

    def test_document_turn_bypasses_generic_pipeline(self):
        needle = 'if document_context is not None:\n            logger.info("Document analysis route=fast-lane'
        self.assertIn(needle, MAIN)
        self.assertIn('self._start_document_analysis_fast_lane(text, document_context)', MAIN)

    def test_gemini_pdf_uses_native_attachment(self):
        self.assertIn('profile["attachment_path"] = document_context.path', MAIN)
        self.assertIn('profile["attachment_mime"] = "application/pdf"', MAIN)
        self.assertIn('profile["native_document"] = True', MAIN)

    def test_remote_document_skips_guardian_prepare(self):
        self.assertIn('if provider_name == "local":\n                self.aura_core.prepare_for_llm(profile=profile)', MAIN)

    def test_old_core_compatibility(self):
        self.assertIn('def _document_request_profile_compat', MAIN)
        self.assertIn('getattr(self.aura_core.resource_guardian, "document_request_profile", None)', MAIN)
        self.assertIn('adaptive_dialogue_context unavailable; compatibility mode active', MAIN)

    def test_document_context_is_bounded(self):
        self.assertIn('select_document_context(document_context, query=text, max_chars=max_chars)', MAIN)

if __name__ == '__main__':
    unittest.main()
