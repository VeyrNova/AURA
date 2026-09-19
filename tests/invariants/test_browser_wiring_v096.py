from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION
from runtime.browser_wiring_v096 import (
    BrowserIntegrationProviderAdapter,
    BrowserWiringAdapter,
)
from runtime.personal_integrations import (
    build_browser_wiring_adapter_v096,
    register_browser_provider_v096,
)

assert AURA_VERSION == "0.9.5"

calls = {"search": 0, "read": 0}

def fake_search(query):
    calls["search"] += 1
    return [{"title": "Synthetic", "url": "https://example.test/result", "query": query}]

def fake_read(url):
    calls["read"] += 1
    return {"final_url": url, "content": "<html>fixture</html>", "status": 200}

provider_adapter = BrowserIntegrationProviderAdapter(
    search_adapter=fake_search,
    read_adapter=fake_read,
)

assert provider_adapter.manifest.provider_id == "browser.provider"
assert len(provider_adapter.manifest.capabilities) == 10
assert all(cap.evidence_required for cap in provider_adapter.manifest.capabilities)

request = types.SimpleNamespace(
    request_id="req-001",
    capability_id="browser.read",
    params={"url": "https://example.test/page"},
)
result = provider_adapter.execute(request)
assert result.ok is True
assert result.evidence_refs
assert calls["read"] == 1

events = {"authorize": 0, "receipt": 0, "confirm": 0}

adapter = build_browser_wiring_adapter_v096(
    provider=provider_adapter.provider,
    authorize_read=lambda capability, args: (
        events.__setitem__("authorize", events["authorize"] + 1) or True
    ),
    create_receipt=lambda capability, payload: (
        events.__setitem__("receipt", events["receipt"] + 1)
        or {"receipt_id": "receipt-001"}
    ),
    request_confirmation=lambda capability, payload: (
        events.__setitem__("confirm", events["confirm"] + 1)
        or {"confirmation_id": "confirm-001"}
    ),
)

read = adapter.execute("browser.read", url="https://example.test/read")
assert read.ok is True
assert read.evidence

submit = adapter.execute("browser.submit", selector="form#contact")
assert submit.ok is False
assert submit.status == "WAITING_CONFIRMATION"
assert submit.receipt_id == "receipt-001"
assert submit.confirmation_id == "confirm-001"
assert submit.provider_result["status"] == "CONFIRMATION_REQUIRED"
assert submit.provider_result["state_changed"] is False
assert events["receipt"] == 1
assert events["confirm"] == 1

class FakeRegistry:
    def __init__(self):
        self.providers = []
    def register_provider(self, provider):
        self.providers.append(provider)

registry = FakeRegistry()
registered = register_browser_provider_v096(
    registry,
    search_adapter=fake_search,
    read_adapter=fake_read,
)
assert registered.manifest.provider_id == "browser.provider"
assert registry.providers == [registered]

denied = BrowserWiringAdapter(
    provider=provider_adapter.provider,
    authorize_read=lambda capability, args: False,
    create_receipt=lambda capability, payload: {"receipt_id": "no"},
    request_confirmation=lambda capability, payload: {"confirmation_id": "no"},
).execute("browser.read", url="https://example.test/denied")

assert denied.ok is False
assert denied.status == "DENIED_BY_POLICY"

print("[PASS] Browser wiring v0.9.6")
print("[PASS] Registry-compatible provider exposes 10 capabilities")
print("[PASS] Read-only integration returns evidence")
print("[PASS] State-changing request waits for confirmation with no side effect")
print("[PASS] Runtime registration helper works")
print("[PASS] No real network used")
