from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations.registry import IntegrationRegistry
from integrations.pc_control import PcControlWindowsProvider
from runtime.aura_autonomous_supervisor_v200 import ApprovalGrant, SupervisedPlan
from runtime.aura_pc_control_windows_v131 import WindowSnapshot, ProcessSnapshot
from runtime.integration_permissions_pc_v131 import evaluate_integration_permission_pc_v131
from runtime.aura_reversible_mutation_binding_v200 import (
    A200ReversibleMutationBinding,
    A200RecoveryToken,
    A200_R5_MARKER,
    AUTONOMOUS_MULTI_MUTATION_ENABLED,
    DESTRUCTIVE_EXECUTION_ENABLED,
    PERMANENTLY_DENIED_CAPABILITIES,
    REVERSIBLE_MUTATION_CAPABILITIES,
    REVERSIBLE_ONE_STEP_EXECUTION_ENABLED,
    RecoveryTokenError,
    ReversibleMutationDenied,
    assert_destructive_execution_disabled,
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


class Security:
    def authorize(self, action, params, *, user_confirmed=False):
        return evaluate_integration_permission_pc_v131(action, params=params).decision


class FakeBackend:
    def __init__(self):
        self.target_hwnd = 7101
        self.other_hwnd = 7102
        self.target_title = "A200 R5 Synthetic Target"
        self.other_title = "A200 R5 Previous Foreground"
        self.states = {
            self.target_hwnd: "normal",
            self.other_hwnd: "normal",
        }
        self.foreground = self.other_hwnd
        self.restore_calls = []
        self.focus_calls = []

    def _snap(self, hwnd):
        title = self.target_title if hwnd == self.target_hwnd else self.other_title
        pid = 8101 if hwnd == self.target_hwnd else 8102
        return WindowSnapshot(
            hwnd=hwnd,
            pid=pid,
            title=title,
            visible=True,
            foreground=(self.foreground == hwnd),
        )

    def discover_windows(self, limit=256):
        return [self._snap(self.target_hwnd), self._snap(self.other_hwnd)]

    def discover_processes(self, limit=512):
        return [
            ProcessSnapshot(8101, "a200-r5-target.exe", 1),
            ProcessSnapshot(8102, "a200-r5-foreground.exe", 1),
        ]

    def foreground_window(self):
        return self._snap(self.foreground) if self.foreground else None

    def window_state(self, hwnd):
        hwnd = int(hwnd)
        if hwnd not in self.states:
            return None
        return {
            "show_state": self.states[hwnd],
            "foreground": self.foreground == hwnd,
        }

    def restore_window_state(self, hwnd, state):
        hwnd = int(hwnd)
        if hwnd not in self.states:
            return False
        show_state = str((state or {}).get("show_state") or "")
        if show_state not in {"normal", "minimized", "maximized"}:
            return False
        self.states[hwnd] = show_state
        self.restore_calls.append((hwnd, show_state))
        return True

    def focus_window(self, hwnd):
        hwnd = int(hwnd)
        if hwnd not in self.states:
            return False
        if self.states[hwnd] == "minimized":
            self.states[hwnd] = "normal"
        self.foreground = hwnd
        self.focus_calls.append(hwnd)
        return True

    def minimize_window(self, hwnd):
        hwnd = int(hwnd)
        if hwnd not in self.states:
            return False
        self.states[hwnd] = "minimized"
        if self.foreground == hwnd:
            self.foreground = self.other_hwnd
        return True

    def maximize_window(self, hwnd):
        hwnd = int(hwnd)
        if hwnd not in self.states:
            return False
        self.states[hwnd] = "maximized"
        return True


def make_plan(capability, *, plan_id=None, title="A200 R5 Synthetic Target"):
    return SupervisedPlan.from_steps(
        goal=f"one supervised reversible {capability} mutation",
        plan_id=plan_id,
        steps=[
            {
                "step_id": "mutate",
                "capability_id": capability,
                "action": capability,
                "summary": f"Execute {capability} on one exact synthetic window",
                "risk_tier": "REVERSIBLE",
                "side_effect_class": "window_state",
                "reversible": True,
                "recovery_hint": "restore exact W132 preimage",
                "params_schema": {"hwnd": 7101, "title": title},
            }
        ],
    )


add("A200-R5 marker", A200_R5_MARKER == "AURA_A200_R5_REVERSIBLE_MUTATION_APPROVAL_RECOVERY_V1")
add("one-step reversible execution enabled", REVERSIBLE_ONE_STEP_EXECUTION_ENABLED is True)
add("multi-mutation disabled", AUTONOMOUS_MULTI_MUTATION_ENABLED is False)
add("destructive execution disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
add(
    "exact reversible mutation allowlist",
    REVERSIBLE_MUTATION_CAPABILITIES
    == frozenset({"pc.focus_window", "pc.minimize_window", "pc.maximize_window"}),
)
add("close permanently denied", "pc.close_window" in PERMANENTLY_DENIED_CAPABILITIES)
add("terminate permanently denied", "pc.terminate_process" in PERMANENTLY_DENIED_CAPABILITIES)

with tempfile.TemporaryDirectory(prefix="aura_a200_r5_") as td:
    store = ActionReceiptStore(Path(td) / "receipts.sqlite3")
    receipts = ActionReceiptService(store=store)
    registry = IntegrationRegistry(
        security_engine=Security(),
        receipt_service=receipts,
    )
    backend = FakeBackend()
    registry.register_provider(PcControlWindowsProvider(backend=backend))
    binding = A200ReversibleMutationBinding(registry=registry, origin="a200-r5-synthetic")

    plan = make_plan("pc.minimize_window")
    approval = ApprovalGrant.explicit_for(plan, approval_scope=["mutate"])

    before_count = len(receipts.list_receipts())
    mutation = binding.execute_one_reversible(plan, approval=approval)
    add("approved one-step mutation succeeded", mutation.status == "succeeded" and mutation.ok)
    add("synthetic target actually mutated", backend.states[7101] == "minimized", backend.states)
    add("mutation owns canonical receipt", bool(mutation.receipt_id), mutation.receipt_id)
    mut_receipt = receipts.get_receipt(mutation.receipt_id)
    add("mutation canonical receipt succeeded", mut_receipt.status == "succeeded")
    add("mutation receipt event lifecycle", store.event_count(mutation.receipt_id) >= 3, store.event_count(mutation.receipt_id))
    add("W132 recovery token captured", isinstance(mutation.recovery_token, A200RecoveryToken))
    token = mutation.recovery_token
    add("recovery token available before restore", binding.recovery_available(token))
    add("recovery tied to exact plan digest", token.plan_digest == plan.digest())
    add("recovery tied to mutation receipt", token.mutation_receipt_id == mutation.receipt_id)

    restore = binding.restore(token)
    add("exact recovery succeeded", restore.status == "succeeded" and restore.ok)
    add("target show-state restored", backend.states[7101] == "normal", backend.states)
    add("previous foreground restored", backend.foreground == 7102, backend.foreground)
    add("restore owns canonical receipt", bool(restore.receipt_id), restore.receipt_id)
    restore_receipt = receipts.get_receipt(restore.receipt_id)
    add("restore canonical receipt succeeded", restore_receipt.status == "succeeded")
    add("restore receipt event lifecycle", store.event_count(restore.receipt_id) >= 3, store.event_count(restore.receipt_id))
    add("recovery token consumed after success", not binding.recovery_available(token))
    must_raise(
        "one-use recovery token rejects second restore",
        RecoveryTokenError,
        lambda: binding.restore(token),
    )

    add(
        "one mutation + one restore created exactly two receipts",
        len(receipts.list_receipts()) == before_count + 2,
        f"before={before_count} after={len(receipts.list_receipts())}",
    )

    # Missing approval must fail BEFORE a canonical receipt exists.
    unapproved_plan = make_plan("pc.focus_window")
    count = len(receipts.list_receipts())
    must_raise(
        "unapproved reversible mutation denied",
        Exception,
        lambda: binding.execute_one_reversible(unapproved_plan, approval=None),
    )
    add("unapproved mutation created no receipt", len(receipts.list_receipts()) == count)

    # Stale approval must fail closed before dispatch.
    stale_base = make_plan("pc.focus_window", plan_id="a200-stale-test")
    stale_approval = ApprovalGrant.explicit_for(stale_base, approval_scope=["mutate"])
    changed = make_plan(
        "pc.focus_window",
        plan_id="a200-stale-test",
        title="A200 R5 DIFFERENT TARGET",
    )
    count = len(receipts.list_receipts())
    must_raise(
        "stale digest approval denied",
        Exception,
        lambda: binding.execute_one_reversible(changed, approval=stale_approval),
    )
    add("stale approval created no receipt", len(receipts.list_receipts()) == count)

    # More than one step is refused even with approval.
    multi = SupervisedPlan.from_steps(
        goal="two mutations are not allowed in R5",
        steps=[
            {
                "step_id": "a",
                "capability_id": "pc.minimize_window",
                "action": "pc.minimize_window",
                "summary": "first mutation",
                "risk_tier": "REVERSIBLE",
                "side_effect_class": "window_state",
                "reversible": True,
                "recovery_hint": "restore exact W132 preimage",
                "params_schema": {"hwnd": 7101, "title": backend.target_title},
            },
            {
                "step_id": "b",
                "capability_id": "pc.maximize_window",
                "action": "pc.maximize_window",
                "summary": "second mutation",
                "depends_on": ["a"],
                "risk_tier": "REVERSIBLE",
                "side_effect_class": "window_state",
                "reversible": True,
                "recovery_hint": "restore exact W132 preimage",
                "params_schema": {"hwnd": 7101, "title": backend.target_title},
            },
        ],
    )
    multi_approval = ApprovalGrant.explicit_for(multi, approval_scope=["a", "b"])
    count = len(receipts.list_receipts())
    must_raise(
        "multi-mutation plan denied",
        ReversibleMutationDenied,
        lambda: binding.execute_one_reversible(multi, approval=multi_approval),
    )
    add("multi-mutation denial created no receipt", len(receipts.list_receipts()) == count)

    # Destructive capabilities are already denied by R2; R5 must not dispatch.
    for cap in ("pc.close_window", "pc.terminate_process"):
        destructive = SupervisedPlan.from_steps(
            goal="destructive denied",
            steps=[
                {
                    "step_id": "mutate",
                    "capability_id": cap,
                    "action": cap,
                    "summary": "destructive denied action",
                    "risk_tier": "DESTRUCTIVE",
                    "side_effect_class": "destructive",
                    "reversible": False,
                    "params_schema": {"hwnd": 7101, "title": backend.target_title},
                }
            ],
        )
        count = len(receipts.list_receipts())
        # No valid ApprovalGrant can make a blocked R2 plan executable.
        fake_approval = ApprovalGrant.explicit_for(
            destructive,
            approval_scope=["mutate"],
        )
        must_raise(
            "R5 denies " + cap,
            Exception,
            lambda destructive=destructive, fake_approval=fake_approval:
                binding.execute_one_reversible(destructive, approval=fake_approval),
        )
        add("destructive denial created no receipt " + cap, len(receipts.list_receipts()) == count)

    raw = make_plan("pc.focus_window")
    # Rebuild with raw execution key to bypass no assumptions about caller labels.
    raw = SupervisedPlan.from_steps(
        goal="raw shell material denied",
        steps=[
            {
                "step_id": "mutate",
                "capability_id": "pc.focus_window",
                "action": "pc.focus_window",
                "summary": "raw key test",
                "risk_tier": "REVERSIBLE",
                "side_effect_class": "window_state",
                "reversible": True,
                "recovery_hint": "restore exact W132 preimage",
                "params_schema": {
                    "hwnd": 7101,
                    "title": backend.target_title,
                    "command": "whoami",
                },
            }
        ],
    )
    raw_approval = ApprovalGrant.explicit_for(raw, approval_scope=["mutate"])
    count = len(receipts.list_receipts())
    must_raise(
        "raw execution material denied before dispatch",
        ReversibleMutationDenied,
        lambda: binding.execute_one_reversible(raw, approval=raw_approval),
    )
    add("raw execution denial created no receipt", len(receipts.list_receipts()) == count)

must_raise(
    "explicit destructive execution assertion fail-closed",
    RuntimeError,
    assert_destructive_execution_disabled,
)

src_path = ROOT / "runtime" / "aura_reversible_mutation_binding_v200.py"
src = src_path.read_text(encoding="utf-8-sig", errors="replace")
add("R5 has no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
add("R5 has no shell/native API", all(x not in src for x in ("os.system(", "os.popen(", "ctypes.", "win32", "WindowsPcControlAdapter(")))
add("R5 uses IntegrationRegistry execution", ".execute_integration(" in src)
add("R5 restore uses canonical capability", 'RESTORE_CAPABILITY = "pc.restore_window_state"' in src)

failed = [x for x in checks if not x[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
if failed:
    print("failed = " + ", ".join(x[0] for x in failed))
    raise SystemExit(1)
print("[PASS] A200-R5 reversible mutation approval + exact recovery invariant")
