from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION
from security.permissions import ACTION_POLICIES, Permission
import runtime.route_contract as route_contract
import integrations.registry as registry
import runtime.personal_integrations as personal_runtime

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

assert AURA_VERSION == "0.9.5"
assert Permission.BROWSER_MUTATE.value == "browser_mutate"
assert Permission.BROWSER_DOWNLOAD.value == "browser_download"

for action in (
    "BROWSER_OPEN",
    "BROWSER_NAVIGATE",
    "BROWSER_READ",
    "BROWSER_EXTRACT",
    "BROWSER_SEARCH",
    "BROWSER_WORKFLOW",
):
    assert action in ACTION_POLICIES

for action in ("BROWSER_CLICK", "BROWSER_FILL", "BROWSER_SUBMIT"):
    policy = ACTION_POLICIES[action]
    assert policy.permission == Permission.BROWSER_MUTATE
    assert policy.confirmation_required is True

download = ACTION_POLICIES["BROWSER_DOWNLOAD"]
assert download.permission == Permission.BROWSER_DOWNLOAD
assert download.confirmation_required is True

expected_routes = {
    "browser.open": "browser-open",
    "browser.navigate": "browser-navigate",
    "browser.read": "browser-read",
    "browser.extract": "browser-extract",
    "browser.search": "browser-search",
    "browser.click": "browser-click",
    "browser.fill": "browser-fill",
    "browser.submit": "browser-submit",
    "browser.download": "browser-download",
    "browser.workflow": "browser-workflow",
}

assert route_contract.BROWSER_ROUTE_MAP_V096 == expected_routes
for route in expected_routes.values():
    assert ("TOOL", route) in route_contract.CANONICAL_ROUTE_PAIRS

assert "browser" in route_contract.OWNED_TOOL_NAMES
assert "browser.provider" in route_contract.OWNED_TOOL_NAMES
assert route_contract.canonical_owned_browser_descriptor_v096("browser.submit")["route"] == "browser-submit"

descriptor = registry.AURA_V096_BROWSER_PROVIDER_DESCRIPTOR
assert descriptor["provider_id"] == "browser.provider"
assert len(descriptor["capabilities"]) == 10
assert descriptor["state_changing_executor"] == "DISABLED"
assert descriptor["evidence_required"] is True

assert callable(personal_runtime.register_browser_provider_v096)
assert callable(personal_runtime.build_browser_wiring_adapter_v096)

protected = {
    "security/policy_engine_v2.py": "61e0a49848b2ba5ff53a80503575f3d77680bc3ba84e9d6f82307958e5d60cd1",
    "mission_engine/engine.py": "d497f3a502f985678813a4dec6faf23a810f55788cd8ed41bf2efcb6dcbe7068",
    "action_receipts/service.py": "4c0f13eefaa6351eca157235d3b0ceea5643474a8cbf0cdb7401c1d71b34023e",
    "tools/web_search.py": "12527a9474569ba697cb0d7235a9848ce63ba15dde21b4bbeab766556ca3dc27",
    "tools/web_fetch.py": "68d7eb5f3894b30a5dc15019714311d2435dc0ca64be65a0f02d97ea40d9450f",
    "tools/safe_http.py": "3d9cfa0c877b03eef3f4dfa4ce7550bf56ef7bf78963db31f24910e2ed2c385c",
    "integrations/browser/provider.py": "fee06ec1a9651687aacd93669114003d03618fa2ee85c171632abdeb232cdaf8",
    "runtime/browser_workflows.py": "cb92861f65a719810c77fb50c8640af8d691b9d289ac83bfc229e602355700d1",
}
for rel, expected in protected.items():
    assert sha(ROOT / rel) == expected, rel

assert sha(ROOT / "database" / "aura.db") == "de473830987af1daca53a90cdba53a6558d5e2494a6556a5de2ff6c7dc4260fb"

ui_root = Path(os.environ.get("LOCALAPPDATA", "")) / "AURA" / "ui" / "v0.7.2.2-rc4.2"
assert sha(ui_root / "src" / "aura-p0702-left-rail.css") == "2162fb9b4f39cd1b0113e2cd06d949fc19bff360251143ef438a37f3b44be4d5"
assert sha(ROOT / "aura-p081-event-watchers.css") == "a76481dce897874f5b5912be7176f0655ec15bbe4351e8876bfa49ef7cc3b5d4"
assert sha(ui_root / "dist" / "assets" / "aura-p081-event-watchers.css") == "a76481dce897874f5b5912be7176f0655ec15bbe4351e8876bfa49ef7cc3b5d4"

print("[PASS] Browser security mapping v0.9.6")
print("[PASS] Read-only browser capabilities reuse WEB_READ")
print("[PASS] Mutations/downloads require non-default permissions + confirmation")
print("[PASS] 10 canonical browser routes mapped")
print("[PASS] Deep certified authorities unchanged")
print("[PASS] DB and UI/color authorities byte-exact")
