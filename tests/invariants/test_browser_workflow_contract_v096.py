from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION

CONTRACT = ROOT / "ci" / "browser_workflow_contract_v096.json"
COLOR = ROOT / "ci" / "color_charter_lock_v095.json"
DB = ROOT / "database" / "aura.db"

UI_ROOT = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "AURA"
    / "ui"
    / "v0.7.2.2-rc4.2"
)
MAIN_CSS = UI_ROOT / "src" / "aura-p0702-left-rail.css"
P081_PROJECT = ROOT / "aura-p081-event-watchers.css"
P081_DIST = UI_ROOT / "dist" / "assets" / "aura-p081-event-watchers.css"

EXPECTED_CONTRACT_SHA = "9e9f8e32f4671ef7b6409859e27a1384721abbeb1baeeacc43a8604b008c0fda"
EXPECTED_DB = "de473830987af1daca53a90cdba53a6558d5e2494a6556a5de2ff6c7dc4260fb"
EXPECTED_MAIN_CSS = "2162fb9b4f39cd1b0113e2cd06d949fc19bff360251143ef438a37f3b44be4d5"
EXPECTED_ACTIVITY_CSS = "a76481dce897874f5b5912be7176f0655ec15bbe4351e8876bfa49ef7cc3b5d4"

EXPECTED_AUTHORITIES = {
    "runtime/route_contract.py": "556379f6ecac877a13f78159f660c880a1590b538e93ef76c8853200c6d7d5d6",
    "security/permissions.py": "de81fd45114252111c4681fa998ff034f57247b3c30b12e9aa6f797465e90d34",
    "security/policy_engine_v2.py": "61e0a49848b2ba5ff53a80503575f3d77680bc3ba84e9d6f82307958e5d60cd1",
    "tools/safe_http.py": "3d9cfa0c877b03eef3f4dfa4ce7550bf56ef7bf78963db31f24910e2ed2c385c",
    "tools/web_search.py": "12527a9474569ba697cb0d7235a9848ce63ba15dde21b4bbeab766556ca3dc27",
    "tools/web_fetch.py": "68d7eb5f3894b30a5dc15019714311d2435dc0ca64be65a0f02d97ea40d9450f",
    "tools/internet_manager.py": "0cf66aecdb915ba1a0cf30da2541d3c5d5f092378138b960ea323d5c361d66c6",
    "tools/models.py": "a9a08ce878dd68a3feb334b03919ff92b9b19ab42d9b17782a50055ecf6625fc",
    "core/aura_core.py": "a7c3d03e28ec213f496d2c51021b9936c9ef5ee275c1f71a67523d9ff74b848f"
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

assert AURA_VERSION == "0.9.5"
assert CONTRACT.is_file()
assert sha(CONTRACT) == EXPECTED_CONTRACT_SHA
assert sha(DB) == EXPECTED_DB

data = json.loads(CONTRACT.read_text(encoding="utf-8-sig"))

assert data.get("schema") == "aura.browser-workflow-contract.v096.v1"
assert data.get("status") == "LOCKED_FOR_D2_IMPLEMENTATION"
assert data.get("milestone") == "Browser / Web Workflows"
assert data.get("strategy") == "EXTEND_EXISTING_WEB_FOUNDATION_DO_NOT_DUPLICATE"

assert data.get("trust_model", {}).get("external_web_content") == "UNTRUSTED_BY_DEFAULT"
assert data.get("trust_model", {}).get("instructions_inside_web_content") == "DATA_NOT_COMMANDS"
assert data.get("evidence_contract", {}).get("workflow_success_requires_proof") is True
assert data.get("evidence_contract", {}).get("missing_evidence_behavior") == "FAIL_CLOSED"

caps = {item.get("capability"): item for item in data.get("capabilities", [])}
required_caps = {
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
assert set(caps) == required_caps

assert caps["browser.submit"].get("confirmation") == "ALWAYS"
assert caps["browser.workflow"].get("confirmation") == "PER_STATE_CHANGING_STEP"
assert caps["browser.open"].get("policy") == "WEB_READ"
assert caps["browser.read"].get("policy") == "WEB_READ"

confirmation = data.get("confirmation_contract", {})
assert confirmation.get("submit") == "ALWAYS_CONFIRM"
assert confirmation.get("upload") == "ALWAYS_CONFIRM"
assert confirmation.get("multi_step") == "EACH_STATE_CHANGING_STEP_GATED"

mission = data.get("mission_engine_contract", {})
assert mission.get("required_for_browser_workflow") is True
assert mission.get("receipts_linked_to_steps") is True

receipt = data.get("action_receipt_contract", {})
assert receipt.get("required_for_state_changing_actions") is True

out_scope = set(data.get("explicit_out_of_scope_v096", []))
for required in (
    "payments or purchases",
    "banking or financial transfers",
    "credential capture/storage",
    "automatic login credential entry",
    "CAPTCHA bypass",
    "anti-bot bypass",
    "silent background state-changing web actions",
    "unconfirmed form submission",
    "unconfirmed uploads",
    "browser extension installation",
    "remote browser service dependency",
):
    assert required in out_scope

ui = data.get("ui_contract", {})
assert ui.get("new_color_palette") is False
assert ui.get("color_charter") == "LOCKED"
assert ui.get("future_surface_must_inherit_existing_palette") is True
assert ui.get("D1_requires_UI_change") is False

color = json.loads(COLOR.read_text(encoding="utf-8-sig"))
assert color.get("status") == "LOCKED"
assert color.get("future_module_requirement", {}).get("must_inherit_current_palette") is True

assert sha(MAIN_CSS) == EXPECTED_MAIN_CSS
assert sha(P081_PROJECT) == EXPECTED_ACTIVITY_CSS
assert sha(P081_DIST) == EXPECTED_ACTIVITY_CSS

for rel, expected in EXPECTED_AUTHORITIES.items():
    path = ROOT / rel
    assert path.is_file(), rel
    assert sha(path) == expected, rel

rules = data.get("D2_implementation_rules", {})
assert rules.get("do_not_duplicate_web_search") is True
assert rules.get("do_not_duplicate_web_fetch") is True
assert rules.get("external_content_untrusted_by_default") is True
assert rules.get("proof_required_before_step_success") is True
assert rules.get("state_changing_steps_require_policy_and_confirmation") is True
assert rules.get("color_charter_locked") is True
assert rules.get("dry_run_before_D2_write") is True

print("[PASS] AURA v0.9.6 Browser Workflow D1 contract")
print("[PASS] Existing web foundation is authoritative")
print("[PASS] External content is UNTRUSTED_BY_DEFAULT / DATA_NOT_COMMANDS")
print("[PASS] Proof required before workflow success")
print("[PASS] State-changing steps require policy + confirmation")
print("[PASS] Color Charter remains LOCKED / NO COLOR CHANGE")
