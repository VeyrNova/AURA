from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(r"C:\AURA GPT version")
TARGET = ROOT / "runtime" / "aura_autonomous_supervisor_v200.py"

spec = importlib.util.spec_from_file_location("aura_autonomous_supervisor_v200", TARGET)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load A200-R2 module")
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

checks = []

def add(name, ok, detail=""):
    ok = bool(ok)
    checks.append((name, ok, detail))
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

add("A200-R2 marker", m.A200_R2_MARKER == "AURA_A200_R2_SUPERVISED_TASK_PLAN_CONTRACT_V1")
add("execution disabled constant", m.EXECUTION_ENABLED is False)
add("canonical MissionEngine authority preserved", m.CANONICAL_AUTHORITIES["mission"] == "mission_engine.engine.MissionEngine")
add("canonical SecurityPolicyEngine authority preserved", m.CANONICAL_AUTHORITIES["policy"] == "security.policy_engine.SecurityPolicyEngine")
add("canonical ActionReceiptService authority preserved", m.CANONICAL_AUTHORITIES["receipt"] == "action_receipts.service.ActionReceiptService")
add("canonical IntegrationRegistry authority preserved", m.CANONICAL_AUTHORITIES["registry"] == "integrations.registry.IntegrationRegistry")

read_plan = m.SupervisedPlan.from_steps(
    goal="inspect visible Windows state",
    steps=[
        {
            "step_id": "discover",
            "capability_id": "pc.windows.list",
            "action": "list_windows",
            "summary": "List visible windows",
            "risk_tier": "READ_ONLY",
            "side_effect_class": "read_only",
            "evidence_required": True,
        },
        {
            "step_id": "foreground",
            "capability_id": "pc.windows.foreground",
            "action": "get_foreground_window",
            "summary": "Read current foreground window",
            "depends_on": ["discover"],
            "risk_tier": "READ_ONLY",
            "side_effect_class": "read_only",
        },
    ],
)
ra = m.assess_plan(read_plan)
add("read-only plan ALLOW", ra.policy_intent is m.PolicyIntent.ALLOW)
add("read-only plan no confirmation", ra.requires_confirmation is False)
add("deterministic DAG order", ra.topological_order == ("discover", "foreground"), repr(ra.topological_order))
env = m.build_execution_envelope(read_plan)
add("read-only envelope still cannot execute in R2", env["execution_enabled"] is False)
add("read-only envelope later gate marker", env["execution_gate"] == "A200-R3_OR_LATER")
add("read-only evidence preserved", all(t["evidence_required"] for t in env["tasks"]))

rev_plan = m.SupervisedPlan.from_steps(
    goal="focus a known window after discovery",
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
            "step_id": "focus",
            "capability_id": "pc.windows.focus",
            "action": "focus_window",
            "summary": "Focus one exact resolved window",
            "depends_on": ["discover"],
            "risk_tier": "REVERSIBLE",
            "side_effect_class": "window_state",
            "reversible": True,
            "recovery_hint": "restore prior foreground HWND",
        },
    ],
)
rev_assessment = m.assess_plan(rev_plan)
add("reversible plan REQUIRE_CONFIRMATION", rev_assessment.policy_intent is m.PolicyIntent.REQUIRE_CONFIRMATION)
add("reversible plan confirmation required", rev_assessment.requires_confirmation is True)

must_raise(
    "unconfirmed reversible plan denied",
    m.ApprovalError,
    lambda: m.build_execution_envelope(rev_plan),
)

approval = m.ApprovalGrant.explicit_for(rev_plan, approval_scope=["focus"])
rev_env = m.build_execution_envelope(rev_plan, approval=approval)
add("explicit scoped approval accepted", rev_env["approval_bound"] is True)
add("approval scope preserved", rev_env["approval_scope"] == ["focus"])
add("approved envelope remains non-executing", rev_env["execution_enabled"] is False)

modified_plan = m.SupervisedPlan.from_steps(
    goal=rev_plan.goal,
    plan_id=rev_plan.plan_id,
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
            "step_id": "focus",
            "capability_id": "pc.windows.focus",
            "action": "focus_window",
            "summary": "Focus a DIFFERENT target contract",
            "depends_on": ["discover"],
            "risk_tier": "REVERSIBLE",
            "side_effect_class": "window_state",
            "reversible": True,
            "recovery_hint": "restore prior foreground HWND",
        },
    ],
)
must_raise(
    "stale approval rejected by digest",
    m.ApprovalError,
    lambda: m.build_execution_envelope(modified_plan, approval=approval),
)

partial_approval = m.ApprovalGrant.explicit_for(rev_plan, approval_scope=["discover"])
must_raise(
    "approval scope must cover confirmation steps",
    m.ApprovalError,
    lambda: m.build_execution_envelope(rev_plan, approval=partial_approval),
)

destructive_plan = m.SupervisedPlan.from_steps(
    goal="unsafe destructive request",
    steps=[
        {
            "step_id": "close",
            "capability_id": "pc.windows.close",
            "action": "close_window",
            "summary": "Close a window",
            "risk_tier": "DESTRUCTIVE",
            "side_effect_class": "destructive",
        }
    ],
)
da = m.assess_plan(destructive_plan)
add("destructive plan DENY", da.policy_intent is m.PolicyIntent.DENY)
must_raise(
    "destructive execution envelope blocked",
    m.PlanBlockedError,
    lambda: m.build_execution_envelope(destructive_plan),
)

shell_plan = m.SupervisedPlan.from_steps(
    goal="unsafe raw shell request",
    steps=[
        {
            "step_id": "shell",
            "capability_id": "pc.shell",
            "action": "powershell.exe -Command whoami",
            "summary": "Run PowerShell",
            "risk_tier": "MUTATING",
            "side_effect_class": "process",
        }
    ],
)
sa = m.assess_plan(shell_plan)
add("raw shell plan DENY", sa.policy_intent is m.PolicyIntent.DENY)

bad_reversible = m.SupervisedPlan.from_steps(
    goal="invalid reversible plan",
    steps=[
        {
            "step_id": "x",
            "capability_id": "pc.windows.focus",
            "action": "focus_window",
            "summary": "Focus window",
            "risk_tier": "REVERSIBLE",
            "side_effect_class": "window_state",
            "reversible": False,
        }
    ],
)
add("reversible without preimage contract DENY", m.assess_plan(bad_reversible).policy_intent is m.PolicyIntent.DENY)

cycle_plan = m.SupervisedPlan.from_steps(
    goal="cycle test",
    steps=[
        {
            "step_id": "a",
            "capability_id": "x.a",
            "action": "read_a",
            "summary": "A",
            "depends_on": ["b"],
        },
        {
            "step_id": "b",
            "capability_id": "x.b",
            "action": "read_b",
            "summary": "B",
            "depends_on": ["a"],
        },
    ],
)
must_raise("cycle rejected before execution", m.PlanContractError, lambda: m.assess_plan(cycle_plan))

missing_dep = m.SupervisedPlan.from_steps(
    goal="missing dependency test",
    steps=[
        {
            "step_id": "a",
            "capability_id": "x.a",
            "action": "read_a",
            "summary": "A",
            "depends_on": ["missing"],
        }
    ],
)
must_raise("missing dependency rejected", m.PlanContractError, lambda: m.assess_plan(missing_dep))

duplicate_steps = [
    {"step_id": "dup", "capability_id": "x.1", "action": "r1", "summary": "1"},
    {"step_id": "dup", "capability_id": "x.2", "action": "r2", "summary": "2"},
]
dup_plan = m.SupervisedPlan.from_steps(goal="duplicate test", steps=duplicate_steps)
must_raise("duplicate step id rejected", m.PlanContractError, lambda: m.assess_plan(dup_plan))

must_raise("R2 has explicit fail-closed execution assertion", RuntimeError, m.assert_execution_disabled)
add("module exposes no execute function", not hasattr(m, "execute"))
add("plan object exposes no execute method", not hasattr(read_plan, "execute"))

# Verify the source itself doesn't import obvious execution libraries.
src = TARGET.read_text(encoding="utf-8-sig", errors="replace")
forbidden_imports = ("import subprocess", "from subprocess", "import ctypes", "import win32", "import os\n", "os.system(", "os.popen(")
add("A200-R2 module has no raw executor imports/calls", not any(x in src for x in forbidden_imports))

failed = [name for name, ok, _ in checks if not ok]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
if failed:
    print("failed = " + ", ".join(failed))
    raise SystemExit(1)
print("[PASS] A200-R2 supervised task-plan contract invariant")
