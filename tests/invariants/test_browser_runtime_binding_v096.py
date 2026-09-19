from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CORE = ROOT / "core" / "aura_core.py"
ADAPTER = ROOT / "runtime" / "browser_live_adapters_v096.py"

EXPECTED_CORE = "f74fd9c810828c71ef39321df875b6828d8510b72a105c9d0eef51fc4af87816"
EXPECTED_ADAPTER = "c1d72b36cff27a6509f736132ed64136e3e030ffaae6b7d0d82ecef1f28905e7"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

assert sha(CORE) == EXPECTED_CORE, sha(CORE)
assert sha(ADAPTER) == EXPECTED_ADAPTER, sha(ADAPTER)

source = CORE.read_text(encoding="utf-8-sig")
ast.parse(source)

assert source.count("# AURA_V096_LIVE_BROWSER_RUNTIME_BIND_BEGIN") == 1
assert source.count("# AURA_V096_LIVE_BROWSER_RUNTIME_BIND_END") == 1
assert "_aura_browser_manager = self.internet_tools" in source
assert "web_search_tool=getattr(_aura_browser_manager, 'search')" in source
assert "web_fetch_tool=getattr(_aura_browser_manager, 'fetch')" in source
assert "_aura_browser_registry.get_provider('browser.provider') is None" in source
assert "register_browser_provider_v096(" in source

assert "FreeWebSearchTool(" not in source
assert "WebFetchTool(" not in source
assert "SafeHTTPClient(" not in source

from runtime.browser_live_adapters_v096 import BrowserLiveToolAdapters
from runtime.personal_integrations import register_browser_provider_v096
from tools.models import ToolResult, ToolSource

class SearchTool:
    def __init__(self):
        self.calls = 0
    def execute(self, query):
        self.calls += 1
        return ToolResult(
            ok=True,
            response="runtime binding synthetic search",
            category="web_search",
            source="fixture",
            sources=(ToolSource(
                name="Synthetic search",
                host="example.test",
                checked_at="2026-08-28T00:00:00+00:00",
                url="https://example.test/search",
            ),),
        )

class FetchTool:
    def __init__(self):
        self.calls = 0
    def execute(self, url):
        self.calls += 1
        return ToolResult(
            ok=True,
            response="runtime binding synthetic page",
            category="web_fetch",
            source="fixture",
            sources=(ToolSource(
                name="Synthetic page",
                host="example.test",
                checked_at="2026-08-28T00:00:00+00:00",
                url=str(url),
            ),),
        )

search_tool = SearchTool()
fetch_tool = FetchTool()
live = BrowserLiveToolAdapters(
    web_search_tool=search_tool,
    web_fetch_tool=fetch_tool,
    search_invoker=lambda tool, query: tool.execute(query),
    fetch_invoker=lambda tool, url: tool.execute(url),
)

class Registry:
    def __init__(self):
        self.providers = {}
    def register_provider(self, provider):
        pid = provider.manifest.provider_id
        if pid in self.providers:
            raise RuntimeError("duplicate provider:" + pid)
        self.providers[pid] = provider
        return provider
    def get_provider(self, provider_id):
        return self.providers.get(str(provider_id))

registry = Registry()
provider = register_browser_provider_v096(
    registry,
    search_adapter=live.search,
    read_adapter=live.read,
)

assert registry.get_provider("browser.provider") is provider

search = provider.execute(SimpleNamespace(
    request_id="binding-search",
    capability_id="browser.search",
    params={"query": "AURA"},
))
read = provider.execute(SimpleNamespace(
    request_id="binding-read",
    capability_id="browser.read",
    params={"url": "https://example.test/page"},
))
click = provider.execute(SimpleNamespace(
    request_id="binding-click",
    capability_id="browser.click",
    params={"selector": "#submit"},
))

assert search.ok is True and search.evidence_refs
assert read.ok is True and read.evidence_refs
assert click.ok is False
assert click.output["status"] == "CONFIRMATION_REQUIRED"
assert click.output["state_changed"] is False
assert search_tool.calls == 1
assert fetch_tool.calls == 1
assert live.web_search_tool is search_tool
assert live.web_fetch_tool is fetch_tool

print("[PASS] Browser runtime binding v0.9.6")
print("[PASS] core/aura_core.py exact transactional SHA")
print("[PASS] existing InternetToolManager search/fetch instances are reused")
print("[PASS] browser.provider registration is idempotently guarded")
print("[PASS] search/read evidence survives registry adapter")
print("[PASS] state-changing browser action remains confirmation-only")
print("[PASS] no duplicate network stack in AuraCore")
print("[PASS] no real network used")
