from __future__ import annotations

import concurrent.futures
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations.registry import IntegrationRegistry
from mission_engine import MissionEngine, SQLiteMissionStore
from runtime.aura_autonomous_supervisor_v200 import ApprovalGrant, SupervisedPlan
from runtime.aura_crash_recovery_v200 import A200CrashRecoveryJournal
from runtime.aura_execution_idempotency_v200 import (
    A200ExecutionIntentLedger,
    A200IdempotentMissionGuard,
    A200_R10_MARKER,
    AUTONOMOUS_MUTATION_ENABLED,
    AUTONOMOUS_RETRY_ENABLED,
    ConcurrencyConflict,
    DESTRUCTIVE_EXECUTION_ENABLED,
    DUPLICATE_SUCCESS_REDISPATCH_ENABLED,
    IdempotencyConflict,
    LEASE_STEAL_ENABLED,
    LEDGER_REQUIRED,
    ONE_ACTIVE_OWNER_PER_KEY,
    TerminalIntentError,
    assert_r10_safety_contract,
    logical_key,
    request_digest,
)
from runtime.aura_pc_control_registry_binding_v131 import register_pc_control_provider_v131
from runtime.aura_pc_control_windows_v131 import WindowSnapshot, ProcessSnapshot
from runtime.aura_readonly_pc_execution_binding_v200 import A200ReadOnlyPcExecutionBinding
from runtime.aura_reversible_mutation_binding_v200 import A200ReversibleMutationBinding
from runtime.integration_permissions_pc_v131 import evaluate_integration_permission_pc_v131


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


class PcSecurity:
    def authorize(self, action, params, *, user_confirmed=False):
        return evaluate_integration_permission_pc_v131(action, params=params).decision


class MissionSecurity:
    def authorize(self, action, params, user_confirmed=False):
        action = str(action or "")
        if action in {"pc.get_foreground_window", "pc.discover_windows", "pc.discover_processes"}:
            return "ALLOW"
        if action == "pc.minimize_window":
            return "ALLOW" if user_confirmed else "REQUIRE_CONFIRMATION"
        if action == "pc.restore_window_state":
            return "ALLOW"
        return "DENY"


class FakeBackend:
    def __init__(self):
        self.target_hwnd = 12101
        self.other_hwnd = 12102
        self.target_title = "A200 R10 Synthetic Idempotency Target"
        self.other_title = "A200 R10 Synthetic Other"
        self.states = {self.target_hwnd: "normal", self.other_hwnd: "normal"}
        self.foreground = self.target_hwnd
        self.minimize_calls = 0
        self.foreground_calls = 0

    def _snap(self, hwnd):
        title = self.target_title if hwnd == self.target_hwnd else self.other_title
        pid = 12201 if hwnd == self.target_hwnd else 12202
        return WindowSnapshot(
            hwnd=hwnd, pid=pid, title=title, visible=True,
            foreground=(self.foreground == hwnd),
        )

    def discover_windows(self, limit=256):
        return [self._snap(self.target_hwnd), self._snap(self.other_hwnd)]

    def discover_processes(self, limit=512):
        return [
            ProcessSnapshot(12201, "a200-r10-target.exe", 1),
            ProcessSnapshot(12202, "a200-r10-other.exe", 1),
        ]

    def foreground_window(self):
        self.foreground_calls += 1
        return self._snap(self.foreground)

    def window_state(self, hwnd):
        hwnd = int(hwnd)
        return {"show_state": self.states[hwnd], "foreground": self.foreground == hwnd}

    def restore_window_state(self, hwnd, state):
        hwnd = int(hwnd)
        self.states[hwnd] = str((state or {}).get("show_state") or "normal")
        return True

    def focus_window(self, hwnd):
        hwnd = int(hwnd)
        if self.states[hwnd] == "minimized":
            self.states[hwnd] = "normal"
        self.foreground = hwnd
        return True

    def minimize_window(self, hwnd):
        self.minimize_calls += 1
        hwnd = int(hwnd)
        self.states[hwnd] = "minimized"
        if self.foreground == hwnd:
            self.foreground = self.other_hwnd
        return True

    def maximize_window(self, hwnd):
        self.states[int(hwnd)] = "maximized"
        return True


def build_runtime(root):
    backend = FakeBackend()
    receipts = ActionReceiptService(store=ActionReceiptStore(root / "receipts.sqlite3"))
    registry = IntegrationRegistry(
        security_engine=PcSecurity(),
        receipt_service=receipts,
    )
    register_pc_control_provider_v131(registry, backend=backend)

    read_binding = A200ReadOnlyPcExecutionBinding(registry=registry, origin="a200-r10-read")
    mutation_binding = A200ReversibleMutationBinding(registry=registry, origin="a200-r10-mutation")
    ledger = A200ExecutionIntentLedger(root / "idempotency.sqlite3")
    guard = A200IdempotentMissionGuard(ledger=ledger)

    store = SQLiteMissionStore(root / "missions.sqlite3")
    engine = MissionEngine(
        security_engine=MissionSecurity(),
        tool_executor=lambda call: {},
        store=store,
    )
    return backend, receipts, registry, read_binding, mutation_binding, ledger, guard, store, engine


def one_task_identity(engine, *, goal, action, params):
    mission = engine.create_mission(goal)
    planned = engine.plan_mission(
        mission.mission_id,
        [
            {
                "key": "task",
                "title": goal,
                "tool_name": "a200-r10-test",
                "action": action,
                "params": dict(params),
                "max_attempts": 1,
            }
        ],
    )
    task = next(iter(planned.tasks.values()))
    return planned, task


add("A200-R10 marker", A200_R10_MARKER == "AURA_A200_R10_CONCURRENCY_LOCKING_IDEMPOTENCY_V1")
add("durable ledger mandatory", LEDGER_REQUIRED is True)
add("one active owner mandatory", ONE_ACTIVE_OWNER_PER_KEY is True)
add("duplicate redispatch disabled", DUPLICATE_SUCCESS_REDISPATCH_ENABLED is False)
add("lease stealing disabled", LEASE_STEAL_ENABLED is False)
add("autonomous retry disabled", AUTONOMOUS_RETRY_ENABLED is False)
add("autonomous mutation disabled", AUTONOMOUS_MUTATION_ENABLED is False)
add("destructive execution disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
assert_r10_safety_contract()
add("R10 safety contract assertion", True)

# ---------------------------------------------------------------------------
# Actual SQLite contention: two logical workers race for the same intent.
with tempfile.TemporaryDirectory(prefix="aura_a200_r10_lock_") as td:
    root = Path(td)
    ledger1 = A200ExecutionIntentLedger(root / "ledger.sqlite3")
    ledger2 = A200ExecutionIntentLedger(root / "ledger.sqlite3")
    key = logical_key(
        mission_id="mis_lock",
        task_id="task_lock",
        action="pc.get_foreground_window",
        plan_revision=1,
    )
    req = request_digest(
        action="pc.get_foreground_window",
        params={},
        plan_digest="a" * 64,
    )
    barrier = threading.Barrier(2)

    def contender(owner):
        barrier.wait()
        ledger = ledger1 if owner == "worker-A" else ledger2
        try:
            result = ledger.claim(
                intent_key=key,
                mission_id="mis_lock",
                task_id="task_lock",
                action="pc.get_foreground_window",
                plan_revision=1,
                request_digest=req,
                owner_id=owner,
            )
            return ("acquired", result.record.owner_id)
        except ConcurrencyConflict:
            return ("blocked", owner)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(contender, ["worker-A", "worker-B"]))
    add("real SQLite contention has exactly one winner", sum(1 for x in outcomes if x[0] == "acquired") == 1, outcomes)
    add("real SQLite contention blocks exactly one peer", sum(1 for x in outcomes if x[0] == "blocked") == 1, outcomes)
    add("ledger stores exactly one running intent", ledger1.count(state="running") == 1)

# ---------------------------------------------------------------------------
# Canonical read dispatch happens once; duplicate reuses prior receipt.
with tempfile.TemporaryDirectory(prefix="aura_a200_r10_read_") as td:
    root = Path(td)
    backend, receipts, registry, read_binding, mutation_binding, ledger, guard, store, engine = build_runtime(root)
    mission, task = one_task_identity(
        engine,
        goal="A200-R10 duplicate read suppression",
        action="pc.get_foreground_window",
        params={},
    )
    plan_revision = mission.plan.revision

    def dispatch_read():
        r = read_binding.execute_capability(
            "pc.get_foreground_window",
            params={},
            step_id=task.task_id,
        )
        return {
            "status": r.status,
            "ok": r.ok,
            "receipt_id": r.receipt_id,
            "output": r.output,
        }

    first = guard.execute_once(
        mission_id=mission.mission_id,
        task_id=task.task_id,
        action="pc.get_foreground_window",
        params={},
        plan_revision=plan_revision,
        plan_digest="b" * 64,
        owner_id="worker-1",
        dispatch=dispatch_read,
    )
    add("first guarded read dispatched", first.dispatched is True and first.disposition == "executed")
    add("first guarded read owns canonical receipt", bool(first.receipt_id))
    add("provider foreground called once", backend.foreground_calls == 1)
    add("one canonical receipt after first read", len(receipts.list_receipts()) == 1)

    second = guard.execute_once(
        mission_id=mission.mission_id,
        task_id=task.task_id,
        action="pc.get_foreground_window",
        params={},
        plan_revision=plan_revision,
        plan_digest="b" * 64,
        owner_id="worker-2",
        dispatch=dispatch_read,
    )
    add("successful duplicate suppressed", second.dispatched is False and second.disposition == "duplicate_suppressed")
    add("duplicate reuses original receipt id", second.receipt_id == first.receipt_id)
    add("duplicate caused no second provider call", backend.foreground_calls == 1)
    add("duplicate caused no second canonical receipt", len(receipts.list_receipts()) == 1)
    add("ledger intent terminal succeeded", ledger.get(first.intent_key).state == "succeeded")

    # Changed exact payload under same logical mission/task/action must conflict.
    must_raise(
        "changed request digest under same task rejected",
        IdempotencyConflict,
        lambda: guard.execute_once(
            mission_id=mission.mission_id,
            task_id=task.task_id,
            action="pc.get_foreground_window",
            params={"unexpected": "changed"},
            plan_revision=plan_revision,
            plan_digest="b" * 64,
            owner_id="worker-3",
            dispatch=dispatch_read,
        ),
    )
    add("digest conflict created no receipt", len(receipts.list_receipts()) == 1)

# ---------------------------------------------------------------------------
# Reversible mutation is also dispatch-once; duplicate cannot repeat side effect.
with tempfile.TemporaryDirectory(prefix="aura_a200_r10_mutation_") as td:
    root = Path(td)
    backend, receipts, registry, read_binding, mutation_binding, ledger, guard, store, engine = build_runtime(root)
    mission, task = one_task_identity(
        engine,
        goal="A200-R10 duplicate reversible mutation suppression",
        action="pc.minimize_window",
        params={"hwnd": backend.target_hwnd, "title": backend.target_title},
    )
    plan_revision = mission.plan.revision

    r2_plan = SupervisedPlan.from_steps(
        goal="A200-R10 exactly-once reversible minimize",
        plan_id="a200-r10-mutation-plan",
        steps=[
            {
                "step_id": "mutate",
                "capability_id": "pc.minimize_window",
                "action": "pc.minimize_window",
                "summary": "one exact reversible minimize",
                "risk_tier": "REVERSIBLE",
                "side_effect_class": "window_state",
                "reversible": True,
                "recovery_hint": "restore exact W132 preimage",
                "params_schema": {
                    "hwnd": backend.target_hwnd,
                    "title": backend.target_title,
                },
            }
        ],
    )
    approval = ApprovalGrant.explicit_for(r2_plan, approval_scope=["mutate"])
    holder = {}

    def dispatch_mutation():
        m = mutation_binding.execute_one_reversible(r2_plan, approval=approval)
        holder["mutation"] = m
        return {
            "status": m.status,
            "ok": m.ok,
            "receipt_id": m.receipt_id,
            "recovery_token_id": m.recovery_token.token_id if m.recovery_token else None,
        }

    first = guard.execute_once(
        mission_id=mission.mission_id,
        task_id=task.task_id,
        action="pc.minimize_window",
        params={"hwnd": backend.target_hwnd, "title": backend.target_title},
        plan_revision=plan_revision,
        plan_digest=r2_plan.digest(),
        owner_id="mut-worker-1",
        dispatch=dispatch_mutation,
    )
    add("first reversible mutation dispatched", first.dispatched is True)
    add("synthetic mutation happened once", backend.minimize_calls == 1 and backend.states[backend.target_hwnd] == "minimized")
    add("mutation created exactly one canonical receipt", len(receipts.list_receipts()) == 1)

    second = guard.execute_once(
        mission_id=mission.mission_id,
        task_id=task.task_id,
        action="pc.minimize_window",
        params={"hwnd": backend.target_hwnd, "title": backend.target_title},
        plan_revision=plan_revision,
        plan_digest=r2_plan.digest(),
        owner_id="mut-worker-2",
        dispatch=dispatch_mutation,
    )
    add("duplicate reversible mutation suppressed", second.dispatched is False)
    add("duplicate mutation reuses receipt id", second.receipt_id == first.receipt_id)
    add("duplicate mutation did not repeat side effect", backend.minimize_calls == 1)
    add("duplicate mutation did not create receipt", len(receipts.list_receipts()) == 1)

    restore = mutation_binding.restore(holder["mutation"].recovery_token)
    add("single exact restore succeeds", restore.status == "succeeded" and restore.ok)
    add("window restored after exactly-once mutation", backend.states[backend.target_hwnd] == "normal")
    add("restore creates second canonical receipt only", len(receipts.list_receipts()) == 2)

# ---------------------------------------------------------------------------
# Interrupted running claim is never auto-stolen; R9 recovery can reconcile it.
with tempfile.TemporaryDirectory(prefix="aura_a200_r10_crash_") as td:
    root = Path(td)
    ledger = A200ExecutionIntentLedger(root / "idempotency.sqlite3")
    key = logical_key(
        mission_id="mis_crash",
        task_id="task_mutate",
        action="pc.minimize_window",
        plan_revision=1,
    )
    req = request_digest(
        action="pc.minimize_window",
        params={"hwnd": 1, "title": "synthetic"},
        plan_digest="c" * 64,
    )
    ledger.claim(
        intent_key=key,
        mission_id="mis_crash",
        task_id="task_mutate",
        action="pc.minimize_window",
        plan_revision=1,
        request_digest=req,
        owner_id="dead-worker",
    )
    must_raise(
        "running claim cannot be stolen after crash",
        ConcurrencyConflict,
        lambda: ledger.claim(
            intent_key=key,
            mission_id="mis_crash",
            task_id="task_mutate",
            action="pc.minimize_window",
            plan_revision=1,
            request_digest=req,
            owner_id="restart-worker",
        ),
    )
    add("crash claim remains running until reconciliation", ledger.get(key).state == "running")

    reconciled = ledger.reconcile_recovered(
        intent_key=key,
        request_digest=req,
        recovery_receipt_id="rcp_r9_recovery_example",
    )
    add("R9-style recovery reconciliation terminal", reconciled.state == "recovered")
    add("recovery receipt bound into intent", reconciled.recovery_receipt_id == "rcp_r9_recovery_example")
    must_raise(
        "recovered mutation intent cannot redispatch",
        TerminalIntentError,
        lambda: ledger.claim(
            intent_key=key,
            mission_id="mis_crash",
            task_id="task_mutate",
            action="pc.minimize_window",
            plan_revision=1,
            request_digest=req,
            owner_id="late-worker",
        ),
    )

# ---------------------------------------------------------------------------
# Failed dispatch remains terminal; R10 never invents a retry policy.
with tempfile.TemporaryDirectory(prefix="aura_a200_r10_failed_") as td:
    root = Path(td)
    ledger = A200ExecutionIntentLedger(root / "idempotency.sqlite3")
    guard = A200IdempotentMissionGuard(ledger=ledger)

    def boom():
        raise RuntimeError("synthetic dispatch failure")

    must_raise(
        "failed guarded dispatch propagates error",
        RuntimeError,
        lambda: guard.execute_once(
            mission_id="mis_fail",
            task_id="task_fail",
            action="pc.get_foreground_window",
            params={},
            plan_revision=1,
            plan_digest="d" * 64,
            owner_id="worker-fail",
            dispatch=boom,
        ),
    )
    key = logical_key(
        mission_id="mis_fail",
        task_id="task_fail",
        action="pc.get_foreground_window",
        plan_revision=1,
    )
    add("failed intent persisted terminal failed", ledger.get(key).state == "failed")
    must_raise(
        "failed intent cannot auto-retry through R10",
        TerminalIntentError,
        lambda: ledger.claim(
            intent_key=key,
            mission_id="mis_fail",
            task_id="task_fail",
            action="pc.get_foreground_window",
            plan_revision=1,
            request_digest=request_digest(
                action="pc.get_foreground_window",
                params={},
                plan_digest="d" * 64,
            ),
            owner_id="worker-retry",
        ),
    )

src_path = ROOT / "runtime" / "aura_execution_idempotency_v200.py"
src = src_path.read_text(encoding="utf-8-sig", errors="replace")
add("R10 uses companion SQLite ledger", "a200_execution_intents" in src)
add("R10 uses BEGIN IMMEDIATE locking", 'BEGIN IMMEDIATE' in src)
add("R10 explicitly closes SQLite connections", "conn.close()" in src)
add("R10 contains no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
add("R10 contains no native shell API", all(x not in src for x in ("os.system(", "os.popen(", "ctypes.", "win32", "WindowsPcControlAdapter(")))
add("R10 contains no close capability", "pc.close_window" not in src)
add("R10 contains no terminate capability", "pc.terminate_process" not in src)

failed = [x for x in checks if not x[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
if failed:
    print("failed = " + ", ".join(x[0] for x in failed))
    raise SystemExit(1)
print("[PASS] A200-R10 concurrency/locking + duplicate suppression + idempotency invariant")
