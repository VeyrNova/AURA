from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai.llm_manager import GeminiProvider, LLMProviderError
from config.settings import settings
from runtime.hybrid_runtime import choose_document_route, choose_llm_route
from services.document_analysis import DocumentContext, extract_document, select_document_context


class Patch2683MultiBrainRoutingTests(unittest.TestCase):
    def cloud_settings(self):
        return (
            patch.object(settings, "AURA_RUNTIME_MODE", "hybrid"),
            patch.object(settings, "GROQ_ENABLED", True),
            patch.object(settings, "GROQ_API_KEY", "gsk_test_key_abcdefghijklmnopqrstuvwxyz"),
            patch.object(settings, "GEMINI_ENABLED", True),
            patch.object(settings, "GEMINI_API_KEY", "AIzaSy_test_key_abcdefghijklmnopqrstuvwxyz"),
            patch.object(settings, "DOCUMENT_CLOUD_ENABLED", True),
            patch.object(settings, "DOCUMENT_ANALYSIS_PROVIDER", "auto"),
        )

    def test_normal_conversation_prefers_groq(self):
        patches = self.cloud_settings()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            route = choose_llm_route("Explique-moi cette panne", voice_output=True)
        self.assertEqual(route.provider, "groq")

    def test_document_analysis_prefers_gemini(self):
        patches = self.cloud_settings()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            route = choose_document_route("analyse ce rapport")
        self.assertEqual(route.provider, "gemini")
        self.assertEqual(route.model, settings.GEMINI_DOCUMENT_MODEL)

    def test_document_falls_back_to_groq_when_gemini_missing(self):
        with patch.object(settings, "AURA_RUNTIME_MODE", "hybrid"), \
             patch.object(settings, "GROQ_ENABLED", True), \
             patch.object(settings, "GROQ_API_KEY", "gsk_test_key_abcdefghijklmnopqrstuvwxyz"), \
             patch.object(settings, "GEMINI_ENABLED", True), \
             patch.object(settings, "GEMINI_API_KEY", ""), \
             patch.object(settings, "DOCUMENT_CLOUD_ENABLED", True), \
             patch.object(settings, "DOCUMENT_ANALYSIS_PROVIDER", "auto"):
            route = choose_document_route("analyse ce rapport")
        self.assertEqual(route.provider, "groq")

    def test_explicit_local_document_stays_local(self):
        marker = next(iter(settings.HYBRID_LOCAL_ONLY_MARKERS))
        patches = self.cloud_settings()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            route = choose_document_route(f"{marker} analyse ce document")
        self.assertEqual(route.provider, "local")


class Patch2683GeminiProviderTests(unittest.TestCase):
    def test_gemini_host_is_fail_closed(self):
        with self.assertRaises(LLMProviderError):
            GeminiProvider("https://example.com/v1beta", "https://generativelanguage.googleapis.com/upload/v1beta", "test")

    def test_payload_supports_native_file_reference(self):
        provider = GeminiProvider(
            "https://generativelanguage.googleapis.com/v1beta",
            "https://generativelanguage.googleapis.com/upload/v1beta",
            "test-key",
        )
        payload = provider._payload(
            [{"role": "system", "content": "Analyse précisément."}, {"role": "user", "content": "Résume."}],
            model=settings.GEMINI_DOCUMENT_MODEL,
            num_predict=300,
            temperature=0.2,
            top_p=0.9,
            file_uri="https://generativelanguage.googleapis.com/v1beta/files/test",
            file_mime="application/pdf",
        )
        self.assertIn("systemInstruction", payload)
        parts = payload["contents"][-1]["parts"]
        self.assertTrue(any("file_data" in part for part in parts))
        self.assertEqual(payload["generationConfig"]["maxOutputTokens"], 300)


class Patch2683DocumentContextTests(unittest.TestCase):
    def test_long_log_preserves_recent_errors_and_tail(self):
        head = "START AURA\n" * 1000
        middle = "routine line\n" * 15000
        tail = "ERROR attachment analysis failed\nTraceback boom\nFINAL RECENT EVENT\n"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "aura.log"
            path.write_text(head + middle + tail, encoding="utf-8")
            doc = extract_document(str(path))
        self.assertIn("FINAL RECENT EVENT", doc.text)
        self.assertIn("ERROR attachment analysis failed", doc.text)
        self.assertGreater(doc.text_chars, 0)

    def test_log_query_selects_error_context(self):
        doc = DocumentContext(
            path="x.log", name="x.log", mime_type="text/plain", size_bytes=1,
            text="INFO normal\nERROR document crash\nTraceback fail\nINFO tail", truncated=False, text_chars=60,
        )
        selected = select_document_context(doc, query="analyse les erreurs du document", max_chars=5000)
        self.assertIn("ERROR document crash", selected.text)

    def test_scanned_pdf_can_be_marked_native_required_without_local_parser(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "scan.pdf"
            path.write_bytes(b"%PDF-1.4\nminimal")
            with patch("services.document_analysis._read_pdf", return_value=""):
                doc = extract_document(str(path))
        self.assertTrue(doc.native_required)
        self.assertEqual(doc.mime_type, "application/pdf")


class Patch2683UiInvariants(unittest.TestCase):
    def test_document_route_not_forced_local_and_shutdown_is_guarded(self):
        source = Path(__file__).resolve().parents[1].joinpath("ui", "main_window.py").read_text(encoding="utf-8")
        doc_idx = source.index("profile = self.aura_core.document_request_profile(user_text=text)")
        self.assertNotIn("force_local=True", source[doc_idx:doc_idx + 650])
        self.assertIn('provider_name == "gemini"', source[doc_idx:doc_idx + 900])
        self.assertIn('if self._closing:', source[source.index("def _on_llm_finished"):source.index("def _on_llm_failed")])
        self.assertIn('and not bool(profile.get("native_document"))', source)

    def test_hud_has_multi_brain_state(self):
        source = Path(__file__).resolve().parents[1].joinpath("ui", "main_window.py").read_text(encoding="utf-8")
        self.assertIn("NEURAL LINK · MULTI", source)
        self.assertIn("GROQ + GEMINI + LOCAL", source)


if __name__ == "__main__":
    unittest.main()
