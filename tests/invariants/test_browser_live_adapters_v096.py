from __future__ import annotations

import hashlib
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.internet_manager import InternetToolManager
from tools.web_search import FreeWebSearchTool
from tools.web_fetch import WebFetchTool
from tools.models import ToolResult, ToolSource
from runtime.browser_live_adapters_v096 import BrowserLiveToolAdapters
from runtime.browser_wiring_v096 import BrowserIntegrationProviderAdapter

EXPECTED_ADAPTER = "c1d72b36cff27a6509f736132ed64136e3e030ffaae6b7d0d82ecef1f28905e7"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

assert sha(ROOT / "runtime" / "browser_live_adapters_v096.py") == EXPECTED_ADAPTER

calls = {"search": 0, "fetch": 0}

class FakeSearchTool(FreeWebSearchTool):
    def __init__(self):
        pass
    def execute(self, query, *, count=4):
        calls["search"] += 1
        return ToolResult(
            True,
            "Synthetic search answer",
            "web_search",
            "synthetic-search-source",
            (
                ToolSource(
                    "Synthetic result",
                    "example.test",
                    "2026-08-28T00:00:00+00:00",
                    "https://example.test/result",
                ),
            ),
        )

class FakeFetchTool(WebFetchTool):
    def __init__(self):
        pass
    def execute(self, url):
        calls["fetch"] += 1
        return ToolResult(
            True,
            "Synthetic page body",
            "web_fetch",
            "synthetic-fetch-source",
            (
                ToolSource(
                    "Synthetic page",
                    "example.test",
                    "2026-08-28T00:00:00+00:00",
                    str(url),
                ),
            ),
        )

class FakeManager(InternetToolManager):
    def __init__(self):
        self.primary_search = FakeSearchTool()
        self.primary_fetch = FakeFetchTool()

manager = FakeManager()
live = BrowserLiveToolAdapters(
    web_search_tool=manager.primary_search,
    web_fetch_tool=manager.primary_fetch,
    search_invoker=lambda tool, query: tool.execute(query),
    fetch_invoker=lambda tool, url: tool.execute(url),
)

assert live.web_search_tool is manager.primary_search
assert live.web_fetch_tool is manager.primary_fetch

search_payload = live.search("AURA browser workflow")
read_payload = live.read("https://example.test/page")

assert search_payload["answer"] == "Synthetic search answer"
assert search_payload["existing_tool"] == "web_search"
assert search_payload["results"][0]["title"] == "Synthetic result"
assert search_payload["results"][0]["publisher"] == "example.test"
assert search_payload["results"][0]["url"] == "https://example.test/result"

assert read_payload["content"] == "Synthetic page body"
assert read_payload["existing_tool"] == "web_fetch"
assert read_payload["final_url"] == "https://example.test/page"
assert read_payload["sources"][0]["title"] == "Synthetic page"
assert read_payload["sources"][0]["publisher"] == "example.test"
assert calls == {"search": 1, "fetch": 1}

provider = BrowserIntegrationProviderAdapter(
    search_adapter=live.search,
    read_adapter=live.read,
)

search_request = types.SimpleNamespace(
    request_id="d2-r6-search",
    capability_id="browser.search",
    params={"query": "AURA browser workflow"},
)
read_request = types.SimpleNamespace(
    request_id="d2-r6-read",
    capability_id="browser.read",
    params={"url": "https://example.test/page"},
)
click_request = types.SimpleNamespace(
    request_id="d2-r6-click",
    capability_id="browser.click",
    params={"selector": "#submit"},
)

search_result = provider.execute(search_request)
read_result = provider.execute(read_request)
click_result = provider.execute(click_request)

assert search_result.ok is True and search_result.evidence_refs
assert read_result.ok is True and read_result.evidence_refs
assert click_result.ok is False
assert click_result.output["status"] == "CONFIRMATION_REQUIRED"
assert isinstance(click_result.status, str) and click_result.status
assert calls == {"search": 2, "fetch": 2}

print("[PASS] Browser live adapters v0.9.6")
print("[PASS] Certified adapter SHA256 is exact")
print("[PASS] Existing AURA Web tool instances can be reused by identity")
print("[PASS] ToolResult/ToolSource search and fetch translation works")
print("[PASS] BrowserIntegrationProviderAdapter receives evidence")
print("[PASS] State-changing browser execution remains confirmation-only")
print("[PASS] No real network used by invariant")
