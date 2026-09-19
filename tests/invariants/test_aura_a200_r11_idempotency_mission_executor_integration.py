from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations.registry import IntegrationRegistry
from mission_engine import MissionEngine, SQLiteMissionStore
from runtime.aura_crash_recovery_v200 import A200CrashRecoveryJournal
from runtime.aura_execution_idempotency_v200 import (
    A200ExecutionIntentLedger,
    TerminalIntentError,
)
from runtime.aura_idempotent_mission_executor_v200 import (
    A200IdempotentCrashSafeMissionExecutor,
    A200_R11_MARKER,
    A200_R11_R1_MARKER,
    A200_R11_R2_MARKER,
    ATTEMPT_SCOPED_INTENT_KEYS,
    AUTONOMOUS_MUTATION_ENABLED,
    AUTONOMOUS_RETRY_ENABLED,
    CANONICAL_TASK_DEPENDENCIES_FIELD,
    DESTRUCTIVE_EXECUTION_ENABLED,
    DUPLICATE_DISPATCH_ENABLED,
    LEASE_STEAL_ENABLED,
    MISSION_EXECUTOR_IDEMPOTENCY_REQUIRED,
    PRE_EXECUTION_ATTEMPT_ARMING_REQUIRED,
    assert_r11_safety_contract,
    attempt_scoped_intent_key,
    mission_task_contract_digest,
)
from runtime.aura_pc_control_registry_binding_v131 import (
    register_pc_control_provider_v131,
)
from runtime.aura_pc_control_windows_v131 import WindowSnapshot, ProcessSnapshot
from runtime.aura_readonly_pc_execution_binding_v200 import (
    A200ReadOnlyPcExecutionBinding,
)
from runtime.aura_reversible_mutation_binding_v200 import (
    A200ReversibleMutationBinding,
)
from runtime.aura_supervised_recovery_retry_v200 import (
    A200BoundedSupervisedRecovery,
    RetryApprovalGrant,
)
from runtime.integration_permissions_pc_v131 import (
    evaluate_integration_permission_pc_v131,
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


class PcSecurity:
    def authorize(self, action, params, *, user_confirmed=False):
        return evaluate_integration_permission_pc_v131(
            action, params=params
        ).decision


class MissionSecurity:
    def authorize(self, action, params, user_confirmed=False):
        action = str(action or "")
        if action in {
            "pc.discover_windows",
            "pc.discover_processes",
            "pc.get_foreground_window",
            "pc.restore_window_state",
        }:
            return "ALLOW"
        if action == "pc.minimize_window":
            return "ALLOW" if user_confirmed else "REQUIRE_CONFIRMATION"
        return "DENY"


class FakeBackend:
    def __init__(self, *, fail_first_foreground=False):
        self.target_hwnd = 14101
        self.other_hwnd = 14102
        self.target_title = "A200 R11 R2 Synthetic Integrated Target"
        self.other_title = "A200 R11 R2 Synthetic Other"
        self.states = {self.target_hwnd: "normal", self.other_hwnd: "normal"}
        self.foreground = self.target_hwnd
        self.foreground_calls = 0
        self.minimize_calls = 0
        self.fail_first_foreground = bool(fail_first_foreground)

    def _snap(self, hwnd):
        title = self.target_title if hwnd == self.target_hwnd else self.other_title
        pid = 14201 if hwnd == self.target_hwnd else 14202
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
            ProcessSnapshot(14201, "a200-r11-r2-target.exe", 1),
            ProcessSnapshot(14202, "a200-r11-r2-other.exe", 1),
        ]

    def foreground_window(self):
        self.foreground_calls += 1
        if self.fail_first_foreground and self.foreground_calls == 1:
            raise RuntimeError("synthetic first foreground failure")
        return self._snap(self.foreground)

    def window_state(self, hwnd):
        hwnd = int(hwnd)
        return {
            "show_state": self.states[hwnd],
            "foreground": self.foreground == hwnd,
        }

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


def build_runtime(root, *, backend=None, owner_id="worker-r11-r2", crash_hook=None):
    receipts = ActionReceiptService(
        store=ActionReceiptStore(root / "receipts.sqlite3")
    )
    registry = IntegrationRegistry(
        security_engine=PcSecurity(),
        receipt_service=receipts,
    )
    register_pc_control_provider_v131(registry, backend=backend)

    read_binding = A200ReadOnlyPcExecutionBinding(
        registry=registry,
        origin="a200-r11-r2-read",
    )
    mutation_binding = A200ReversibleMutationBinding(
        registry=registry,
        origin="a200-r11-r2-mutation",
    )
    mission_store = SQLiteMissionStore(root / "missions.sqlite3")
    crash_journal = A200CrashRecoveryJournal(root / "crash_recovery.sqlite3")
    ledger = A200ExecutionIntentLedger(root / "idempotency.sqlite3")

    holder = {}
    engine = MissionEngine(
        security_engine=MissionSecurity(),
        tool_executor=lambda call: holder["executor"].tool_executor(call),
        store=mission_store,
    )
    executor = A200IdempotentCrashSafeMissionExecutor(
        mission_engine=engine,
        read_binding=read_binding,
        mutation_binding=mutation_binding,
        crash_journal=crash_journal,
        intent_ledger=ledger,
        owner_id=owner_id,
        after_dispatch_hook=crash_hook,
    )
    holder["executor"] = executor
    return (
        receipts,
        registry,
        mission_store,
        crash_journal,
        ledger,
        engine,
        executor,
    )


def task_by_key(mission, key):
    return next(task for task in mission.tasks.values() if task.key == key)


def arm_private_replay(executor, mission_id, task):
    executor._active_mission_id = mission_id
    executor._active_task_id = task.task_id
    executor._confirmed_for_active_call = True
    try:
        return executor.tool_executor(task.tool_call)
    finally:
        executor._confirmed_for_active_call = False
        executor._active_task_id = None
        executor._active_mission_id = None


add("A200-R11 marker", A200_R11_MARKER == "AURA_A200_R11_IDEMPOTENCY_GUARD_MISSION_EXECUTOR_INTEGRATION_V1")
add("A200-R11-R1 marker retained", A200_R11_R1_MARKER == "AURA_A200_R11_R1_ATTEMPT_CONTEXT_BINDING_REPAIR_V1")
add("A200-R11-R2 marker", A200_R11_R2_MARKER == "AURA_A200_R11_R2_CANONICAL_TASK_SCHEMA_REPAIR_V1")
add("Mission executor idempotency mandatory", MISSION_EXECUTOR_IDEMPOTENCY_REQUIRED is True)
add("attempt-scoped intent keys enabled", ATTEMPT_SCOPED_INTENT_KEYS is True)
add("pre-execution attempt arming required", PRE_EXECUTION_ATTEMPT_ARMING_REQUIRED is True)
add("canonical dependency field is dependencies", CANONICAL_TASK_DEPENDENCIES_FIELD == "dependencies")
add("duplicate dispatch disabled", DUPLICATE_DISPATCH_ENABLED is False)
add("lease stealing disabled", LEASE_STEAL_ENABLED is False)
add("autonomous retry disabled", AUTONOMOUS_RETRY_ENABLED is False)
add("autonomous mutation disabled", AUTONOMOUS_MUTATION_ENABLED is False)
add("destructive execution disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
assert_r11_safety_contract()
add("R11-R2 safety contract assertion", True)

# Canonical Task schema / dependency digest test.
with tempfile.TemporaryDirectory(prefix="aura_a200_r11_r2_schema_") as td:
    root = Path(td)
    backend = FakeBackend()
    receipts, registry, store, journal, ledger, engine, executor = build_runtime(
        root, backend=backend, owner_id="schema-worker"
    )
    mission = engine.create_mission("A200-R11-R2 canonical Task schema binding")
    planned = engine.plan_mission(
        mission.mission_id,
        [
            {
                "key": "first",
                "title": "first read",
                "tool_name": "a200-r11-r2",
                "action": "pc.get_foreground_window",
                "params": {},
                "max_attempts": 1,
            },
            {
                "key": "second",
                "title": "dependent read",
                "tool_name": "a200-r11-r2",
                "action": "pc.get_foreground_window",
                "params": {},
                "depends_on": ["first"],
                "max_attempts": 1,
            },
        ],
    )
    first = task_by_key(planned, "first")
    second = task_by_key(planned, "second")
    add("canonical Task exposes dependencies", hasattr(second, "dependencies"))
    add("canonical Task does not require depends_on attribute", not hasattr(second, "depends_on"))
    add("dependent task stores upstream task id", second.dependencies == [first.task_id], second.dependencies)
    digest = mission_task_contract_digest(planned, second)
    add("canonical dependency-bound contract digest is SHA256", len(digest) == 64)

# LIVE read-only MissionEngine execution + restart replay suppression.
with tempfile.TemporaryDirectory(prefix="aura_a200_r11_r2_live_") as td:
    root = Path(td)
    receipts1, registry1, store1, journal1, ledger1, engine1, exec1 = build_runtime(
        root, backend=None, owner_id="live-worker-1"
    )

    mission = engine1.create_mission("A200-R11-R2 live persistent read-only mission")
    engine1.plan_mission(
        mission.mission_id,
        [
            {
                "key": "live_read",
                "title": "Read real Windows foreground through integrated executor",
                "tool_name": "a200-r11-r2-integrated",
                "action": "pc.get_foreground_window",
                "params": {},
                "max_attempts": 1,
            }
        ],
    )
    engine1.start_mission(mission.mission_id)
    task = task_by_key(engine1.get_mission(mission.mission_id), "live_read")
    add("live task attempts zero before canonical execute", task.attempts == 0)

    executed = exec1._execute_task(
        mission.mission_id,
        task.task_id,
        user_confirmed=False,
    )
    add(
        "live read-only MissionEngine task succeeded",
        executed.status == "succeeded",
        f"status={executed.status} error={executed.error}",
    )
    add("live execution used armed attempt one", exec1.last_attempt == 1, exec1.last_attempt)

    completed = engine1.complete(mission.mission_id)
    add("live read-only MissionEngine mission completed", completed.status == "completed")

    live_task = task_by_key(completed, "live_read")
    live_result = live_task.result
    live_receipt = live_result.get("receipt_id")
    add("live task persisted attempts one", live_task.attempts == 1)
    add("live integrated read owns canonical receipt", bool(live_receipt))
    add("live result idempotency attempt one", live_result.get("idempotency_attempt") == 1)
    add("live integrated read ledger succeeded", ledger1.count(state="succeeded") == 1)
    add("live integrated read produced one receipt", len(receipts1.list_receipts()) == 1)
    add("live integrated result tagged executed", live_result.get("idempotency_disposition") == "executed")

    receipts2, registry2, store2, journal2, ledger2, engine2, exec2 = build_runtime(
        root, backend=None, owner_id="live-worker-2"
    )
    reloaded = engine2.get_mission(mission.mission_id)
    add("completed live mission rehydrates after restart", reloaded.status == "completed")
    add("idempotency ledger survives restart", ledger2.count(state="succeeded") == 1)
    receipt_count = len(receipts2.list_receipts())
    replay_task = task_by_key(reloaded, "live_read")
    replay = arm_private_replay(exec2, mission.mission_id, replay_task)
    add("post-restart stale replay suppressed", replay.get("idempotency_disposition") == "duplicate_suppressed")
    add("post-restart stale replay uses persisted attempt one", replay.get("idempotency_attempt") == 1)
    add("post-restart replay reuses original receipt", replay.get("receipt_id") == live_receipt)
    add("post-restart replay creates no receipt", len(receipts2.list_receipts()) == receipt_count)

# Full synthetic reversible mission.
with tempfile.TemporaryDirectory(prefix="aura_a200_r11_r2_full_") as td:
    root = Path(td)
    backend = FakeBackend()
    receipts, registry, store, journal, ledger, engine, executor = build_runtime(
        root, backend=backend, owner_id="integrated-worker"
    )
    mission = engine.create_mission("A200-R11-R2 full integrated reversible mission")
    engine.plan_mission(
        mission.mission_id,
        executor.build_mission_task_specs(
            hwnd=backend.target_hwnd,
            title=backend.target_title,
        ),
    )
    engine.start_mission(mission.mission_id)
    paused = executor.run_until_pause_or_complete(mission.mission_id)
    add("integrated mission pauses for mutation confirmation", paused.phase == "waiting_confirmation")
    executor.confirm_waiting_task(mission.mission_id)
    add("integrated mutation occurred once", backend.minimize_calls == 1)
    finished_run = executor.run_until_pause_or_complete(mission.mission_id)
    add("integrated five-step mission completed", finished_run.phase == "completed")
    finished = engine.get_mission(mission.mission_id)
    add("integrated MissionEngine final completed", finished.status == "completed")
    add("integrated window restored", backend.states[backend.target_hwnd] == "normal")
    add("integrated original foreground restored", backend.foreground == backend.target_hwnd)
    add("R9 journal terminal restored", journal.count(state="restored") == 1)
    add("five execution intents succeeded", ledger.count(state="succeeded") == 5)
    add("five canonical receipts produced", len(receipts.list_receipts()) == 5)
    add(
        "all first-attempt task results tagged attempt one",
        all(
            isinstance(t.result, dict)
            and t.result.get("idempotency_attempt") == 1
            for t in finished.tasks.values()
        ),
    )
    add(
        "MissionEngine DAG dependencies preserved",
        all(
            isinstance(t.dependencies, list)
            for t in finished.tasks.values()
        ),
    )

    mutation_task = task_by_key(finished, "minimize_once")
    receipt_count = len(receipts.list_receipts())
    replay = arm_private_replay(executor, mission.mission_id, mutation_task)
    add("stale duplicate mutation suppressed inside integrated executor", replay.get("idempotency_disposition") == "duplicate_suppressed")
    add("duplicate mutation did not repeat side effect", backend.minimize_calls == 1)
    add("duplicate mutation created no canonical receipt", len(receipts.list_receipts()) == receipt_count)

# R8 compatibility: explicit retry becomes attempt 2.
with tempfile.TemporaryDirectory(prefix="aura_a200_r11_r2_retry_") as td:
    root = Path(td)
    backend = FakeBackend(fail_first_foreground=True)
    receipts, registry, store, journal, ledger, engine, executor = build_runtime(
        root, backend=backend, owner_id="retry-worker"
    )
    r8 = A200BoundedSupervisedRecovery(
        mission_engine=engine,
        mission_executor=executor,
    )
    mission = engine.create_mission("A200-R11-R2 integrated R8 retry compatibility")
    engine.plan_mission(
        mission.mission_id,
        r8.build_retryable_task_specs(
            hwnd=backend.target_hwnd,
            title=backend.target_title,
        ),
    )
    engine.start_mission(mission.mission_id)

    first_run = r8.run_until_pause_or_complete(mission.mission_id)
    add("integrated first read failure waits retry approval", first_run.phase == "waiting_retry_approval")
    failed_task = task_by_key(engine.get_mission(mission.mission_id), "observe_before")
    add("first failed attempt persisted as attempt one", failed_task.attempts == 1)
    add("first failed attempt ledger terminal failed", ledger.count(state="failed") == 1)

    candidate = r8.inspect_retry_candidate(mission.mission_id)
    r8.approve_retry(candidate, approval=RetryApprovalGrant.explicit_for(candidate))
    second_run = r8.run_until_pause_or_complete(mission.mission_id)
    add("explicit retry reaches mutation confirmation", second_run.phase == "waiting_confirmation")
    retried_task = task_by_key(engine.get_mission(mission.mission_id), "observe_before")
    add("MissionEngine retry advanced to attempt two", retried_task.attempts == 2)
    add("attempt one and attempt two have separate intent rows", ledger.count() == 2)
    add("attempt two ledger succeeded", ledger.count(state="succeeded") == 1)
    add("integrated executor reports attempt two", executor.last_attempt == 2, executor.last_attempt)

    key1 = attempt_scoped_intent_key(
        mission_id=mission.mission_id,
        task_id=retried_task.task_id,
        action="pc.get_foreground_window",
        plan_revision=engine.get_mission(mission.mission_id).plan.revision,
        attempt=1,
    )
    key2 = attempt_scoped_intent_key(
        mission_id=mission.mission_id,
        task_id=retried_task.task_id,
        action="pc.get_foreground_window",
        plan_revision=engine.get_mission(mission.mission_id).plan.revision,
        attempt=2,
    )
    add("attempt-scoped intent keys differ", key1 != key2)
    add("attempt one remains failed", ledger.get(key1).state == "failed")
    add("attempt two is succeeded", ledger.get(key2).state == "succeeded")

# Crash after R9 journal arm but before idempotency success commit.
class SimulatedProcessCrash(BaseException):
    pass

with tempfile.TemporaryDirectory(prefix="aura_a200_r11_r2_crash_") as td:
    root = Path(td)
    backend = FakeBackend()
    crash_once = {"armed": True}

    def crash_hook(call, result):
        if crash_once["armed"] and str(call.action) == "pc.minimize_window":
            crash_once["armed"] = False
            raise SimulatedProcessCrash(
                "R11-R2 crash between canonical mutation and idempotency commit"
            )

    receipts1, registry1, store1, journal1, ledger1, engine1, exec1 = build_runtime(
        root,
        backend=backend,
        owner_id="crashing-worker",
        crash_hook=crash_hook,
    )
    mission = engine1.create_mission("A200-R11-R2 crash-safe integrated idempotency")
    engine1.plan_mission(
        mission.mission_id,
        exec1.build_mission_task_specs(
            hwnd=backend.target_hwnd,
            title=backend.target_title,
        ),
    )
    engine1.start_mission(mission.mission_id)
    paused = exec1.run_until_pause_or_complete(mission.mission_id)
    add("crash scenario reaches mutation confirmation", paused.phase == "waiting_confirmation")

    crashed = False
    try:
        exec1.confirm_waiting_task(mission.mission_id)
    except SimulatedProcessCrash:
        crashed = True
    add("simulated process crash escapes MissionEngine", crashed is True)
    add("crash happened after one mutation", backend.minimize_calls == 1 and backend.states[backend.target_hwnd] == "minimized")
    add("R9 crash journal armed before crash", journal1.get_pending(mission.mission_id) is not None)
    add("R10/R11 intent left running before success commit", ledger1.count(state="running") == 1)

    receipts2, registry2, store2, journal2, ledger2, engine2, exec2 = build_runtime(
        root,
        backend=backend,
        owner_id="restart-worker",
    )
    add("restart sees running idempotency claim", ledger2.count(state="running") == 1)
    recovery = exec2.recover_after_restart(mission.mission_id)
    add("integrated restart recovery succeeds", recovery.restored is True)
    add("restart recovery restores window", backend.states[backend.target_hwnd] == "normal")
    add("restart recovery restores original foreground", backend.foreground == backend.target_hwnd)
    add("recovered MissionEngine mission cancelled", engine2.get_mission(mission.mission_id).status == "cancelled")
    add("running intent reconciled to recovered", ledger2.count(state="recovered") == 1)

    recovered_record = ledger2.get(exec1.last_intent_key)
    add("recovered intent binds crash recovery receipt", recovered_record.recovery_receipt_id == recovery.restore_receipt_id)
    must_raise(
        "recovered integrated mutation cannot redispatch",
        TerminalIntentError,
        lambda: ledger2.claim(
            intent_key=recovered_record.intent_key,
            mission_id=recovered_record.mission_id,
            task_id=recovered_record.task_id,
            action=recovered_record.action,
            plan_revision=recovered_record.plan_revision,
            request_digest=recovered_record.request_digest,
            owner_id="late-worker",
        ),
    )
    add("crash recovery did not repeat mutation", backend.minimize_calls == 1)

src_path = ROOT / "runtime" / "aura_idempotent_mission_executor_v200.py"
src = src_path.read_text(encoding="utf-8-sig", errors="replace")
add("R11-R2 source uses canonical task.dependencies", "list(task.dependencies)" in src)
add("R11-R2 source contains no task.depends_on", "task.depends_on" not in src)
add("R11-R2 pre-execution arming retained", "_arm_attempt_context" in src)
add("R11-R2 uses next attempt before execute", "int(task.attempts) + 1" in src)
add("R11 extends R9 crash-safe executor", "A200CrashSafeMissionExecutor" in src)
add("R11 uses R10 execution ledger", "A200ExecutionIntentLedger" in src)
add("R11 keeps crash recovery reconciliation", ".reconcile_recovered(" in src)
add("R11 contains no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
add("R11 contains no native shell API", all(x not in src for x in ("os.system(", "os.popen(", "ctypes.", "win32", "WindowsPcControlAdapter(")))
add("R11 contains no close capability", "pc.close_window" not in src)
add("R11 contains no terminate capability", "pc.terminate_process" not in src)

failed = [x for x in checks if not x[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
if failed:
    print("failed = " + ", ".join(x[0] for x in failed))
    raise SystemExit(1)
print("[PASS] A200-R11-R2 canonical Task schema + integrated idempotency invariant")
