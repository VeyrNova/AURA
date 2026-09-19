from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION

D1_CONTRACT = ROOT / "ci" / "browser_workflow_contract_v096.json"
D1_HISTORICAL_INVARIANT = ROOT / "tests" / "invariants" / "test_browser_workflow_contract_v096.py"

EXPECTED_CONTRACT = "9e9f8e32f4671ef7b6409859e27a1384721abbeb1baeeacc43a8604b008c0fda"
EXPECTED_HISTORICAL_INVARIANT = "102bd73652314136f975ddce5c35f2cc3be3fc075e2f2274eadb8712cece4a15"

EXPECTED_CURRENT = {
    "security/permissions.py": "6df1f3a88072355147e9b1409566bb9046a25412f57112830308ccc948c7d4a0",
    "runtime/route_contract.py": "a04a000f19c4794b543dbd4cd5b73541997f32055d3a7776f4979a89eb62f9b4",
    "integrations/registry.py": "5057ef64320721f002828b19147618446621a2e2af26fc70ddece8b04a4e1411",
    "runtime/personal_integrations.py": "de47c1a8bd1598ab6d03a29276dfdd0ada90b5220415cc8e2a418b940259a893",
}

EXPECTED_PROTECTED = {
    "security/policy_engine_v2.py": "61e0a49848b2ba5ff53a80503575f3d77680bc3ba84e9d6f82307958e5d60cd1",
    "mission_engine/engine.py": "d497f3a502f985678813a4dec6faf23a810f55788cd8ed41bf2efcb6dcbe7068",
    "action_receipts/service.py": "4c0f13eefaa6351eca157235d3b0ceea5643474a8cbf0cdb7401c1d71b34023e",
    "tools/web_search.py": "12527a9474569ba697cb0d7235a9848ce63ba15dde21b4bbeab766556ca3dc27",
    "tools/web_fetch.py": "68d7eb5f3894b30a5dc15019714311d2435dc0ca64be65a0f02d97ea40d9450f",
    "tools/safe_http.py": "3d9cfa0c877b03eef3f4dfa4ce7550bf56ef7bf78963db31f24910e2ed2c385c",
    "integrations/browser/provider.py": "fee06ec1a9651687aacd93669114003d03618fa2ee85c171632abdeb232cdaf8",
    "runtime/browser_workflows.py": "cb92861f65a719810c77fb50c8640af8d691b9d289ac83bfc229e602355700d1",
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

assert AURA_VERSION == "0.9.5"
assert sha(D1_CONTRACT) == EXPECTED_CONTRACT
assert sha(D1_HISTORICAL_INVARIANT) == EXPECTED_HISTORICAL_INVARIANT

contract = json.loads(D1_CONTRACT.read_text(encoding="utf-8-sig"))
assert contract.get("schema") == "aura.browser-workflow-contract.v096.v1"
assert contract.get("status") == "LOCKED_FOR_D2_IMPLEMENTATION"
assert contract.get("strategy") == "EXTEND_EXISTING_WEB_FOUNDATION_DO_NOT_DUPLICATE"
assert contract.get("trust_model", {}).get("external_web_content") == "UNTRUSTED_BY_DEFAULT"
assert contract.get("trust_model", {}).get("instructions_inside_web_content") == "DATA_NOT_COMMANDS"
assert contract.get("evidence_contract", {}).get("workflow_success_requires_proof") is True
assert contract.get("evidence_contract", {}).get("missing_evidence_behavior") == "FAIL_CLOSED"
assert contract.get("ui_contract", {}).get("color_charter") == "LOCKED"

for rel, expected in EXPECTED_CURRENT.items():
    assert sha(ROOT / rel) == expected, rel

for rel, expected in EXPECTED_PROTECTED.items():
    assert sha(ROOT / rel) == expected, rel

assert sha(ROOT / "database" / "aura.db") == "de473830987af1daca53a90cdba53a6558d5e2494a6556a5de2ff6c7dc4260fb"

ui_root = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "AURA"
    / "ui"
    / "v0.7.2.2-rc4.2"
)
assert sha(ui_root / "src" / "aura-p0702-left-rail.css") == "2162fb9b4f39cd1b0113e2cd06d949fc19bff360251143ef438a37f3b44be4d5"
assert sha(ROOT / "aura-p081-event-watchers.css") == "a76481dce897874f5b5912be7176f0655ec15bbe4351e8876bfa49ef7cc3b5d4"
assert sha(ui_root / "dist" / "assets" / "aura-p081-event-watchers.css") == "a76481dce897874f5b5912be7176f0655ec15bbe4351e8876bfa49ef7cc3b5d4"

print("[PASS] D1 Browser Workflow contract preserved through D2 R4")
print("[PASS] Historical D1 invariant remains immutable")
print("[PASS] Four intentional D2 R4 authority hashes are exact")
print("[PASS] Deep certified authorities remain byte-exact")
print("[PASS] DB and UI/color authorities remain exact")
