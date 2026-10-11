from __future__ import annotations

import io
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QUrl, QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView

from aura_native.search.duckduckgo import DuckDuckGoHtmlBackend
from aura_native.search.qt_bridge import NativeSearchBridge
from aura_native.search.service import SearchError, SearchService, safe_web_url

ROOT = Path(__file__).parents[2]


class FakeBackend:
    def __init__(self, rows=(), error=None): self.rows, self.error, self.calls = rows, error, []
    def search(self, query, *, limit, timeout):
        self.calls.append((query, limit, timeout))
        if self.error: raise self.error
        return self.rows


class SearchServiceTests(unittest.TestCase):
    def test_normalizes_deduplicates_rejects_unsafe_and_keeps_order(self):
        backend = FakeBackend([
            {"title":" First  result ","url":"https://example.com/a","snippet":" x  y ","provider":"fake"},
            {"title":"duplicate","url":"https://example.com/a"},
            {"title":"unsafe","url":"javascript:alert(1)"},
            {"title":"Second","url":"http://openai.com/b"},
        ])
        rows = SearchService(backend, limit=10).search("  Qt   docs ")
        self.assertEqual([x.title for x in rows], ["First result", "Second"])
        self.assertEqual(rows[0].domain, "example.com")
        self.assertEqual(rows[0].snippet, "x y")
        self.assertEqual(backend.calls[0][0], "Qt docs")

    def test_empty(self): self.assertEqual(SearchService(FakeBackend()).search("   "), ())
    def test_limit(self):
        rows=[{"title":str(i),"url":f"https://example.com/{i}"} for i in range(30)]
        self.assertEqual(len(SearchService(FakeBackend(rows), limit=12).search("x")), 12)
    def test_timeout(self):
        with self.assertRaises(SearchError) as caught: SearchService(FakeBackend(error=TimeoutError())).search("x")
        self.assertEqual(caught.exception.code, "timeout")
    def test_network_error(self):
        with self.assertRaises(SearchError) as caught: SearchService(FakeBackend(error=OSError())).search("x")
        self.assertEqual(caught.exception.code, "network_unavailable")
    def test_provider_error(self):
        with self.assertRaises(SearchError) as caught: SearchService(FakeBackend(error=RuntimeError())).search("x")
        self.assertEqual(caught.exception.code, "provider_error")
    def test_url_policy(self):
        self.assertEqual(safe_web_url("https://example.com/x"), "https://example.com/x")
        for value in ("file:///x", "javascript:x", "data:text/plain,x", "custom:x", "broken", "https://user:pass@example.com"):
            self.assertEqual(safe_web_url(value), "")


class _Response:
    def __init__(self, body): self._body=body; self.headers=self
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def get_content_type(self): return "text/html"
    def read(self, _limit): return self._body


class SearchBackendTests(unittest.TestCase):
    def test_parses_duckduckgo_results_and_redirect(self):
        body=b'<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdoc.qt.io%2Fqt-6%2F">Qt Docs</a><a class="result__snippet">Official Qt documentation</a>'
        with patch("aura_native.search.duckduckgo.urlopen", return_value=_Response(body)) as call:
            rows=DuckDuckGoHtmlBackend().search("Qt 6",limit=10,timeout=4)
        self.assertEqual(rows[0]["url"], "https://doc.qt.io/qt-6/")
        self.assertEqual(rows[0]["snippet"], "Official Qt documentation")
        self.assertEqual(call.call_args.kwargs["timeout"], 4)


class SearchBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QGuiApplication.instance() or QGuiApplication([])
    def wait(self, bridge):
        until=time.time()+2
        while bridge.loading and time.time()<until: self.app.processEvents(); time.sleep(.005)
        self.app.processEvents()
    def test_state_ready_empty_timeout_offline_error(self):
        cases=[([{"title":"Qt","url":"https://qt.io"}],None,"ready"),([],None,"empty"),([],SearchError("timeout"),"timeout"),([],SearchError("network_unavailable"),"offline"),([],SearchError("invalid_response"),"error")]
        for rows,error,state in cases:
            with self.subTest(state=state):
                bridge=NativeSearchBridge(SearchService(FakeBackend(rows,error)))
                self.assertEqual(bridge.state,"idle"); bridge.search("query"); self.wait(bridge); self.assertEqual(bridge.state,state)
    def test_stale_result_cannot_replace_newer_result(self):
        bridge=NativeSearchBridge(SearchService(FakeBackend()))
        bridge._generation=2
        bridge._apply_result([{"title":"old"}],"",1)
        self.assertEqual(bridge.results,[])
    def test_cancel_invalidates_worker(self):
        bridge=NativeSearchBridge(SearchService(FakeBackend()))
        bridge.search("query"); bridge.cancel(); generation=bridge._generation
        bridge._apply_result([{"title":"late"}],"",generation-1)
        self.assertEqual(bridge.state,"idle"); self.assertEqual(bridge.results,[])
    def test_open_only_safe_url(self):
        opened=[]; bridge=NativeSearchBridge(SearchService(FakeBackend()),opener=lambda url: opened.append(url.toString()) or True)
        self.assertFalse(bridge.openResult("file:///secret")); self.assertTrue(bridge.openResult("https://example.com")); self.assertEqual(opened,["https://example.com"])


class SearchQmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QGuiApplication.instance() or QGuiApplication([])
    def test_view_loads_at_supported_sizes_without_qml_errors(self):
        bridge=NativeSearchBridge(SearchService(FakeBackend()))
        for width,height in ((1100,700),(1280,720),(1440,900),(1920,1080)):
            view=QQuickView(); warnings=[]; view.engine().warnings.connect(lambda values:warnings.extend(x.toString() for x in values)); view.rootContext().setContextProperty("searchBridge",bridge); view.resize(QSize(width,height)); view.setSource(QUrl.fromLocalFile(str(ROOT/"app/qml/views/SearchView.qml")))
            try:
                self.assertEqual(view.status(),QQuickView.Ready,warnings); self.assertFalse(any("ReferenceError" in x or "TypeError" in x for x in warnings),warnings); self.assertLessEqual(view.rootObject().implicitWidth(),width)
            finally: view.setSource(QUrl())
    def test_native_routing_replaces_conversation_prefill(self):
        modules=(ROOT/"app/qml/views/ModulesView.qml").read_text(encoding="utf-8")
        subdock=(ROOT/"app/qml/components/ModulesSubdock.qml").read_text(encoding="utf-8")
        workspace=(ROOT/"app/qml/views/NativeWorkspaceView.qml").read_text(encoding="utf-8")
        self.assertNotIn('openConversationPrefill("Recherche : ")',modules)
        self.assertNotIn('prefillRequested("Recherche : ")',subdock)
        self.assertIn('navigateRequested("search")',modules); self.assertIn('navigateRequested("search")',subdock)
        self.assertIn('source: "SearchView.qml"',workspace)


if __name__ == "__main__": unittest.main()
