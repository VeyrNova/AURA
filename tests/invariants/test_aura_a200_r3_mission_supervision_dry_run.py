from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
sys.path.insert(0, str(ROOT))

from runtime.aura_autonomous_supervisor_v200 import (
    ApprovalGrant,
    PlanBlockedError,
    SupervisedPlan,
)
from runtime.aura_mission_supervision_adapter_v200 import (
    A200MissionSupervisionAdapter,
    A200_R3_MARKER,
    AUTONOMOUS_EXECUTION_ENABLED,
    CANONICAL_RECEIPTS_WRITTEN,
    DRY_RUN_ONLY,
    SimulationState,
    assert_execution_disabled,
    inspect_mission_engine_contract,
)

checks = []

def add(name, ok, detail=""):
    ok = bool(ok)
    checks.append((name, ok, str(detail)))
    print(("[PASS] " if ok else "[FAIL] ") + name + (f" :: {detail}" if detail else ""))

def must_raise(name, exc_type, fn):
    try:
        fn()
    except exc_type:
        add(name, True)
    except Exception as exc:
        add(name, False, f"wrong exception {type(exc).__name__}: {exc}")
    else:
        add(name, False, "no exception")

adapter = A200MissionSupervisionAdapter()

add("A200-R3 marker", A200_R3_MARKER == "AURA_A200_R3_MISSION_SUPERVISION_DRY_RUN_V1")
add("R3 dry-run only", DRY_RUN_ONLY is True)
add("autonomous execution disabled", AUTONOMOUS_EXECUTION_ENABLED is False)
add("canonical receipts not written", CANONICAL_RECEIPTS_WRITTEN is False)
add("adapter exposes no execute method", not hasattr(adapter, "execute"))

snapshot = adapter.contract_snapshot()
add("MissionEngine canonical authority", snapshot["canonical_authorities"]["mission"] == "mission_engine.engine.MissionEngine")
add("SecurityPolicy canonical authority", snapshot["canonical_authorities"]["policy"] == "security.policy_engine.SecurityPolicyEngine")
add("ActionReceipt canonical authority", snapshot["canonical_authorities"]["receipt"] == "action_receipts.service.ActionReceiptService")
add("IntegrationRegistry canonical authority", snapshot["canonical_authorities"]["registry"] == "integrations.registry.IntegrationRegistry")

signatures = inspect_mission_engine_contract()
required = {
    "create_mission", "plan_mission", "start_mission", "next_ready_tasks",
    "execute_task", "record_evidence", "retry_task", "replan", "resume",
    "cancel", "complete", "get_mission"
}
add("current MissionEngine method surface complete", required.issubset(signatures), sorted(signatures))

read_plan = SupervisedPlan.from_steps(
    goal="read Windows state without mutation",
    steps=[
        {
            "step_id": "discover",
            "capability_id": "pc.windows.list",
            "action": "list_windows",
            "summary": "List visible windows",
            "risk_tier": "READ_ONLY",
            "side_effect_class": "read_only",
        },
        {
            "step_id": "foreground",
            "capability_id": "pc.windows.foreground",
            "action": "get_foreground_window",
            "summary": "Read foreground window",
            "depends_on": ["discover"],
            "risk_tier": "READ_ONLY",
            "side_effect_class": "read_only",
        },
    ],
)

handoff1 = adapter.prepare_handoff(read_plan)
handoff2 = adapter.prepare_handoff(read_plan)
add("read-only handoff ready", handoff1.status == "ready_for_later_execution_gate")
add("handoff remains execution disabled", handoff1.execution_enabled is False)
add("handoff digest deterministic", handoff1.plan_digest == handoff2.plan_digest)
add("handoff tasks require canonical policy recheck", all(t["canonical_policy_recheck_required"] for t in handoff1.mission_payload["tasks"]))
add("handoff tasks require canonical receipt", all(t["canonical_receipt_required_before_execution"] for t in handoff1.mission_payload["tasks"]))
add("handoff tasks require IntegrationRegistry dispatch", all(t["integration_registry_dispatch_required"] for t in handoff1.mission_payload["tasks"]))

sim1 = adapter.simulate(read_plan)
sim2 = adapter.simulate(read_plan)
add("read-only simulation completes", sim1["terminal_state"] == "simulated_complete")
add("read-only states simulated succeeded", all(v == "simulated_succeeded" for v in sim1["states"].values()), sim1["states"])
add("simulation deterministic states", sim1["states"] == sim2["states"])
add("simulation deterministic trace", sim1["traces"] == sim2["traces"])
add("simulation writes no canonical receipt", sim1["canonical_receipts_written"] is False)
add("simulation mutates no PC/window", sim1["pc_or_window_mutated"] is False)
add("all trace records clearly simulated", all(t["receipt_mode"] == "SIMULATED_ONLY" for t in sim1["traces"]))

rev_plan = SupervisedPlan.from_steps(
    goal="focus exact known window with recovery",
    steps=[
        {
            "step_id": "discover",
            "capability_id": "pc.windows.list",
            "action": "list_windows",
            "summary": "List windows",
            "risk_tier": "READ_ONLY",
            "side_effect_class": "read_only",
        },
        {
            "step_id": "focus",
            "capability_id": "pc.windows.focus",
            "action": "focus_window",
            "summary": "Focus exact HWND",
            "depends_on": ["discover"],
            "risk_tier": "REVERSIBLE",
            "side_effect_class": "window_state",
            "reversible": True,
            "recovery_hint": "restore previous foreground HWND",
        },
        {
            "step_id": "verify",
            "capability_id": "pc.windows.foreground",
            "action": "get_foreground_window",
            "summary": "Verify foreground window",
            "depends_on": ["focus"],
            "risk_tier": "READ_ONLY",
            "side_effect_class": "read_only",
        },
    ],
)

waiting = adapter.simulate(rev_plan)
add("unapproved reversible simulation waits", waiting["terminal_state"] == "waiting_confirmation")
add("read-only dependency may simulate before approval", waiting["states"]["discover"] == "simulated_succeeded")
add("mutation step pauses for confirmation", waiting["states"]["focus"] == "waiting_confirmation")
add("dependent verification blocked", waiting["states"]["verify"] == "blocked_dependency")

approval = ApprovalGrant.explicit_for(rev_plan, approval_scope=["focus"])
approved = adapter.simulate(rev_plan, approval=approval)
add("approved reversible dry-run simulates complete", approved["terminal_state"] == "simulated_complete")
add("approved dry-run still does not execute", approved["execution_enabled"] is False)
add("approved dry-run still writes no receipt", approved["canonical_receipts_written"] is False)
add("approved dry-run still mutates no PC", approved["pc_or_window_mutated"] is False)

destructive = SupervisedPlan.from_steps(
    goal="destructive request",
    steps=[
        {
            "step_id": "kill",
            "capability_id": "pc.process.terminate",
            "action": "terminate_process",
            "summary": "Terminate process",
            "risk_tier": "DESTRUCTIVE",
            "side_effect_class": "destructive",
        }
    ],
)
must_raise("destructive handoff refused", PlanBlockedError, lambda: adapter.prepare_handoff(destructive))
must_raise("destructive simulation refused", PlanBlockedError, lambda: adapter.simulate(destructive))
must_raise("explicit R3 execution assertion fail-closed", RuntimeError, assert_execution_disabled)

# Source-level no-executor proof.
target = ROOT / "runtime" / "aura_mission_supervision_adapter_v200.py"
src = target.read_text(encoding="utf-8-sig", errors="replace")
forbidden = (
    "import subprocess",
    "from subprocess",
    "import ctypes",
    "import win32",
    "os.system(",
    "os.popen(",
    ".execute_integration(",
    ".execute_task(",
)
add("R3 source has no real execution calls", not any(x in src for x in forbidden))
add("R3 source has no shell executable strings", all(x not in src.lower() for x in ("powershell.exe", "cmd.exe", "bash -c", "sh -c")))

failed = [x for x in checks if not x[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
if failed:
    print("failed = " + ", ".join(x[0] for x in failed))
    raise SystemExit(1)
print("[PASS] A200-R3 MissionEngine supervision adapter + dry-run invariant")
