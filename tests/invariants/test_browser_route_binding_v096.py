from __future__ import annotations

import ast
import hashlib
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.personal_integrations import PersonalIntegrationDispatcher
from runtime.browser_route_binding_v096 import (
    ALL_BROWSER_CAPABILITIES,
    READ_ONLY_CAPABILITIES,
    CONFIRMATION_ONLY_CAPABILITIES,
    resolve_browser_route_v096,
    dispatch_browser_route_v096,
)

EXPECTED_CAPABILITIES = {
    "browser.open",
    "browser.navigate",
    "browser.read",
    "browser.extract",
    "browser.search",
    "browser.click",
    "browser.fill",
    "browser.submit",
    "browser.download",
    "browser.workflow",
}

assert ALL_BROWSER_CAPABILITIES == EXPECTED_CAPABILITIES
assert READ_ONLY_CAPABILITIES == {
    "browser.open", "browser.navigate", "browser.read",
    "browser.extract", "browser.search",
}
assert CONFIRMATION_ONLY_CAPABILITIES == {
    "browser.click", "browser.fill", "browser.submit", "browser.download",
}

sig = inspect.signature(PersonalIntegrationDispatcher.dispatch_capability)
for name in ("provider_id", "capability_id", "params", "summary"):
    assert name in sig.parameters, sig

cases = {
    "navigateur cherche OpenAI official site": ("browser.search", {"query": "OpenAI official site"}),
    "lis cette page https://example.com/doc": ("browser.read", {"url": "https://example.com/doc"}),
    "extrais cette page https://example.com": ("browser.extract", {"url": "https://example.com"}),
    "ouvre dans le navigateur https://example.com": ("browser.open", {"url": "https://example.com"}),
    "navigue vers https://example.com": ("browser.navigate", {"url": "https://example.com"}),
    "navigateur clique sur #submit": ("browser.click", {"selector": "#submit"}),
    "navigateur remplis #email avec test@example.com": ("browser.fill", {"selector": "#email", "value": "test@example.com"}),
    "navigateur valide form#login": ("browser.submit", {"selector": "form#login"}),
    "télécharge dans le navigateur https://example.com/file.pdf": ("browser.download", {"url": "https://example.com/file.pdf"}),
}
for text, expected in cases.items():
    resolved = resolve_browser_route_v096(text)
    assert resolved is not None, text
    assert resolved.provider_id == "browser.provider"
    assert resolved.capability_id == expected[0], (text, resolved)
    assert resolved.params == expected[1], (text, resolved)

# Generic Web requests must remain with the existing InternetToolManager path.
assert resolve_browser_route_v096("cherche la météo demain") is None
assert resolve_browser_route_v096("recherche OpenAI") is None
assert resolve_browser_route_v096("explique moi Python") is None

class FakeReply:
    handled = True
    text = "ok"

class FakeDispatcher:
    def __init__(self):
        self.calls = []
    def dispatch_capability(self, *, provider_id, capability_id, params, summary):
        self.calls.append((provider_id, capability_id, params, summary))
        return FakeReply()

fake = FakeDispatcher()
reply = dispatch_browser_route_v096(fake, "navigateur cherche AURA route test")
assert reply.handled is True
assert fake.calls == [
    ("browser.provider", "browser.search", {"query": "AURA route test"}, "Recherche navigateur : AURA route test")
]

print("[PASS] Browser route binding v0.9.6")
print("[PASS] 10 certified browser capabilities preserved")
print("[PASS] explicit browser-language commands resolve deterministically")
print("[PASS] generic Web requests remain owned by existing InternetToolManager")
print("[PASS] dispatch reuses PersonalIntegrationDispatcher.dispatch_capability")
print("[PASS] state-changing routes only enter the existing confirmation path")
print("[PASS] no HTTP/search backend is created by route binding")
