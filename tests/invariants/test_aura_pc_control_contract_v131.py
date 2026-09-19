from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"

from runtime.aura_pc_control_contract_v131 import (
    ACTION_SPECS,
    PcControlContractError,
    capability_snapshot,
    normalize_request,
    plan_request,
)
from runtime.route_contract import OWNED_SAFE_DESKTOP_APPS


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


roadmap_sha = sha(ROADMAP)

snapshot = capability_snapshot()
assert snapshot["native_executor_bound"] is False
assert snapshot["arbitrary_shell_input"] is False
assert snapshot["arbitrary_executable_input"] is False
assert set(snapshot["canonical_safe_apps"]) == {
    str(x).strip().casefold() for x in OWNED_SAFE_DESKTOP_APPS
}
assert snapshot["file_operations_owner"] == "integrations.files.provider"

# Read-only discovery is typed and never requires confirmation.
for action in ("DISCOVER_WINDOWS", "DISCOVER_PROCESSES", "GET_FOREGROUND_WINDOW"):
    req = normalize_request(action)
    assert req["requires_confirmation"] is False
    assert req["mutating"] is False
    plan = plan_request(req)
    assert plan["can_execute_here"] is False
    assert plan["status"] == "CONTRACT_READY_EXECUTOR_UNBOUND"

# Existing safe-app launcher remains delegated to its canonical owner.
safe_app = sorted(snapshot["canonical_safe_apps"])[0]
req = normalize_request("OPEN_SAFE_APP", {"app": safe_app})
plan = plan_request(req)
assert plan["status"] == "DELEGATE_EXISTING_OWNER"
assert plan["owner"] == "route_contract.system-safe-app"

# Arbitrary executable/shell material remains denied.
for payload in (
    {"app": r"C:\Windows\System32\cmd.exe"},
    {"app": "calculator", "command": "whoami"},
    {"app": "calculator", "arguments": ["/c", "whoami"]},
):
    try:
        normalize_request("OPEN_SAFE_APP", payload)
    except PcControlContractError:
        pass
    else:
        raise AssertionError(f"unsafe app payload accepted: {payload}")

# Window mutations require a stable hwnd plus human-readable title.
focus = normalize_request("FOCUS_WINDOW", {"hwnd": 1234, "title": "Notepad"})
assert focus["requires_confirmation"] is False
assert focus["reversible"] is True

try:
    normalize_request("FOCUS_WINDOW", {"hwnd": 1234})
except PcControlContractError:
    pass
else:
    raise AssertionError("window action accepted without title evidence")

# Potentially destructive actions require exact confirmation phrases.
close_req = normalize_request("CLOSE_WINDOW", {"hwnd": 1234, "title": "Unsaved document"})
assert close_req["requires_confirmation"] is True
assert close_req["confirmation_phrase"].startswith("CONFIRM PC pcr_")
assert plan_request(close_req)["status"] == "WAITING_CONFIRMATION"

kill_req = normalize_request(
    "TERMINATE_PROCESS",
    {"pid": 4242, "image_name": "example.exe"},
)
assert kill_req["risk_tier"] == "critical"
assert kill_req["requires_confirmation"] is True
assert kill_req["reversible"] is False

try:
    normalize_request("TERMINATE_PROCESS", {"pid": 4, "image_name": "System"})
except PcControlContractError:
    pass
else:
    raise AssertionError("protected/system PID range accepted")

# Request identity is tamper-evident.
tampered = dict(focus)
tampered["params"] = {"hwnd": 9999, "title": "Other"}
try:
    plan_request(tampered)
except PcControlContractError:
    pass
else:
    raise AssertionError("tampered request identity accepted")

# No canonical Roadmap mutation during the contract invariant.
assert sha(ROADMAP) == roadmap_sha

print("[PASS] W131-1 typed read-only/desktop/process action contract")
print("[PASS] canonical safe-app ownership reused")
print("[PASS] arbitrary shell/executable input denied")
print("[PASS] stable target + human-readable evidence enforced")
print("[PASS] destructive confirmation contract enforced")
print("[PASS] native executor intentionally unbound")
print("[PASS] file operations delegated to existing files provider")
print("[PASS] live Roadmap unchanged")
