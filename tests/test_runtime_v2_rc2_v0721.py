from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import settings
from core.version import AURA_BUILD, AURA_RELEASE_CHANNEL, AURA_VERSION
from tools.internet_manager import InternetToolManager
from tools.web_search import FreeWebSearchTool


class _FakeDDGSFactory:
    def __init__(self, behavior):
        self.behavior = behavior
        self.calls = []

    def __call__(self, timeout=5):
        outer = self

        class _Client:
            def text(self, query, **kwargs):
                backend = kwargs.get("backend")
                outer.calls.append((backend, query, kwargs))
                value = outer.behavior.get(backend, [])
                if isinstance(value, BaseException):
                    raise value
                return list(value)

        return _Client()


def _result(title="Deftones update", href="https://example.com/deftones", body="Actualité récente sur le groupe."):
    return {"title": title, "href": href, "body": body}


class RuntimeV2RC24Tests(unittest.TestCase):
    def test_release_identity_current_consolidation(self):
        self.assertEqual(AURA_VERSION, "0.7.2.1")
        self.assertEqual(AURA_BUILD, "2026.08.15.9")
        self.assertEqual(AURA_RELEASE_CHANNEL, "consolidation-rc3.2")

    def test_internet_manager_uses_zero_cost_search(self):
        manager = InternetToolManager()
        self.assertIsInstance(manager.search, FreeWebSearchTool)
        self.assertFalse(bool(manager.search.api_key))
        plan = manager.plan("Recherche sur internet les dernières actualités sur Deftones")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.name, "web_search")
        self.assertEqual(plan.args.get("engine"), "free-web-search")

    def test_missing_ddgs_dependency_fails_closed(self):
        with patch("tools.web_search.ddgs_available", return_value=False), \
             patch.object(settings, "WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_ENABLED", True):
            tool = FreeWebSearchTool(ddgs_factory=None)
            result = tool.execute("AURA runtime v2")
        self.assertFalse(result.ok)
        self.assertEqual(result.source, "dependency_missing")
        self.assertIn("INSTALLER_RECHERCHE_WEB_GRATUITE.bat", result.response)

    def test_google_backend_is_tried_first_and_sources_are_exposed(self):
        factory = _FakeDDGSFactory({"google": [_result(), _result("Second", "https://example.org/2", "Deuxième source") ]})
        with patch.object(settings, "WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_SYNTHESIS_ENABLED", False):
            tool = FreeWebSearchTool(backends="google,duckduckgo", ddgs_factory=factory)
            result = tool.execute("dernières actualités Deftones", count=2)
        self.assertTrue(result.ok)
        self.assertEqual(result.source, "free-web-search")
        self.assertEqual(result.data.get("backend"), "google")
        self.assertTrue(result.data.get("zero_cost"))
        self.assertFalse(result.data.get("paid_fallback"))
        self.assertEqual(len(result.sources), 2)
        self.assertEqual(factory.calls[0][0], "google")
        self.assertEqual(len(factory.calls), 1)
        self.assertEqual(factory.calls[0][2].get("timelimit"), "w")

    def test_failed_google_falls_back_to_duckduckgo_independently(self):
        factory = _FakeDDGSFactory({
            "google": RuntimeError("blocked"),
            "duckduckgo": [_result("DDG result", "https://example.net/ddg", "Fallback source")],
        })
        with patch.object(settings, "WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_SYNTHESIS_ENABLED", False):
            tool = FreeWebSearchTool(backends="google,duckduckgo", ddgs_factory=factory)
            result = tool.execute("test", count=1)
        self.assertTrue(result.ok)
        self.assertEqual(result.data.get("backend"), "duckduckgo")
        self.assertEqual([call[0] for call in factory.calls], ["google", "duckduckgo"])

    def test_all_backends_fail_closed_without_model_memory_answer(self):
        factory = _FakeDDGSFactory({
            "google": RuntimeError("blocked"),
            "duckduckgo": [],
            "startpage": RuntimeError("limited"),
            "yahoo": [],
            "mojeek": [],
        })
        with patch.object(settings, "WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_SYNTHESIS_ENABLED", False):
            tool = FreeWebSearchTool(backends="google,duckduckgo,startpage,yahoo,mojeek", ddgs_factory=factory)
            result = tool.execute("test")
        self.assertFalse(result.ok)
        self.assertEqual(result.source, "free_search_unavailable")
        self.assertIn("aucun moteur payant", result.response.lower())

    def test_invalid_source_urls_are_rejected(self):
        factory = _FakeDDGSFactory({"google": [_result(href="javascript:alert(1)")]})
        with patch.object(settings, "WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_SYNTHESIS_ENABLED", False):
            tool = FreeWebSearchTool(backends="google", ddgs_factory=factory)
            result = tool.execute("test")
        self.assertFalse(result.ok)
        self.assertEqual(result.source, "free_search_unavailable")

    def test_no_search_api_key_is_required(self):
        factory = _FakeDDGSFactory({"duckduckgo": [_result()]})
        with patch.object(settings, "WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_ENABLED", True), \
             patch.object(settings, "FREE_WEB_SEARCH_SYNTHESIS_ENABLED", False):
            tool = FreeWebSearchTool(api_key="", backends="duckduckgo", ddgs_factory=factory)
            result = tool.execute("test")
        self.assertTrue(result.ok)
        self.assertEqual(result.data.get("provider"), "ddgs")

    def test_cloud_runtime_keeps_local_llm_optional(self):
        with patch.object(settings, "LOCAL_LLM_ENABLED", False):
            self.assertFalse(settings.LOCAL_LLM_ENABLED)

    def test_rc24_source_markers(self):
        root = Path(__file__).resolve().parents[1]
        main = (root / "ui" / "main_window.py").read_text(encoding="utf-8", errors="replace")
        guardian = (root / "runtime" / "resource_guardian.py").read_text(encoding="utf-8", errors="replace")
        web_search = (root / "tools" / "web_search.py").read_text(encoding="utf-8", errors="replace")
        manager = (root / "tools" / "internet_manager.py").read_text(encoding="utf-8", errors="replace")
        self.assertIn("SEARCH READY", main)
        self.assertIn("INSTALLER DDGS", main)
        self.assertIn("aucun LLM local résident", guardian)
        self.assertIn("class FreeWebSearchTool", web_search)
        self.assertIn('"google", "duckduckgo", "startpage", "yahoo", "mojeek"', web_search)
        self.assertIn("paid_fallback=False", web_search)
        self.assertIn("free_search_unavailable", web_search)
        self.assertIn('"engine": "free-web-search"', manager)


if __name__ == "__main__":
    unittest.main()
