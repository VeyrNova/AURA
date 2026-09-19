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
from runtime.aura_pc_control_registry_binding_v131 import register_pc_control_provider_v131
from runtime.aura_pc_control_windows_v131 import WindowSnapshot, ProcessSnapshot
from runtime.aura_readonly_pc_execution_binding_v200 import A200ReadOnlyPcExecutionBinding
from runtime.aura_reversible_mutation_binding_v200 import A200ReversibleMutationBinding
from runtime.aura_supervised_mission_executor_v200 import A200SupervisedMissionExecutor
from runtime.aura_supervised_recovery_retry_v200 import (
    A200BoundedSupervisedRecovery,
    A200_R8_MARKER,
    AUTONOMOUS_RETRY_ENABLED,
    DESTRUCTIVE_EXECUTION_ENABLED,
    MAX_SUPERVISED_RETRIES_PER_TASK,
    MUTATION_RETRY_ENABLED,
    RECOVERY_PRECEDES_RETRY,
    RETRYABLE_ACTIONS,
    RetryApprovalError,
    RetryApprovalGrant,
    RetryCandidateError,
    assert_r8_safety_contract,
)
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
        return evaluate_integration_permission_pc_v131(
            action,
            params=params,
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
    def __init__(
        self,
        *,
        fail_first_foreground=False,
        fail_all_foreground=False,
        fail_post_mutation_foreground=False,
    ):
        self.target_hwnd = 10101
        self.other_hwnd = 10102
        self.target_title = "A200 R8 Synthetic Retry Target"
        self.other_title = "A200 R8 Synthetic Other"
        self.states = {
            self.target_hwnd: "normal",
            self.other_hwnd: "normal",
        }
        self.foreground = self.target_hwnd
        self.foreground_calls = 0
        self.fail_first_foreground = bool(fail_first_foreground)
        self.fail_all_foreground = bool(fail_all_foreground)
        self.fail_post_mutation_foreground = bool(fail_post_mutation_foreground)
        self.post_mutation_failed = False

    def _snap(self, hwnd):
        title = self.target_title if hwnd == self.target_hwnd else self.other_title
        pid = 10201 if hwnd == self.target_hwnd else 10202
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
            ProcessSnapshot(10201, "a200-r8-target.exe", 1),
            ProcessSnapshot(10202, "a200-r8-other.exe", 1),
        ]

    def foreground_window(self):
        self.foreground_calls += 1
        if self.fail_all_foreground:
            raise RuntimeError("synthetic persistent foreground read failure")
        if self.fail_first_foreground and self.foreground_calls == 1:
            raise RuntimeError("synthetic first-attempt foreground read failure")
        if (
            self.fail_post_mutation_foreground
            and self.states[self.target_hwnd] == "minimized"
            and not self.post_mutation_failed
        ):
            self.post_mutation_failed = True
            raise RuntimeError("synthetic post-mutation foreground read failure")
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
        return True

    def focus_window(self, hwnd):
        hwnd = int(hwnd)
        if hwnd not in self.states:
            return False
        if self.states[hwnd] == "minimized":
            self.states[hwnd] = "normal"
        self.foreground = hwnd
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


def build_runtime(td, backend):
    receipt_store = ActionReceiptStore(Path(td) / "receipts.sqlite3")
    receipts = ActionReceiptService(store=receipt_store)

    registry = IntegrationRegistry(
        security_engine=PcSecurity(),
        receipt_service=receipts,
    )
    register_pc_control_provider_v131(registry, backend=backend)

    read_binding = A200ReadOnlyPcExecutionBinding(
        registry=registry,
        origin="a200-r8-read",
    )
    mutation_binding = A200ReversibleMutationBinding(
        registry=registry,
        origin="a200-r8-mutation",
    )

    mission_store = SQLiteMissionStore(Path(td) / "missions.sqlite3")
    holder = {}
    engine = MissionEngine(
        security_engine=MissionSecurity(),
        tool_executor=lambda call: holder["r7"].tool_executor(call),
        store=mission_store,
    )
    r7 = A200SupervisedMissionExecutor(
        mission_engine=engine,
        read_binding=read_binding,
        mutation_binding=mutation_binding,
    )
    holder["r7"] = r7

    r8 = A200BoundedSupervisedRecovery(
        mission_engine=engine,
        mission_executor=r7,
    )
    return receipt_store, receipts, mission_store, engine, r7, r8


def task_by_key(mission, key):
    return next(task for task in mission.tasks.values() if task.key == key)


add("A200-R8 marker", A200_R8_MARKER == "AURA_A200_R8_BOUNDED_SUPERVISED_RECOVERY_RETRY_RESUME_V1")
add("supervised retry bound exactly one", MAX_SUPERVISED_RETRIES_PER_TASK == 1)
add("mutation retry disabled", MUTATION_RETRY_ENABLED is False)
add("autonomous retry disabled", AUTONOMOUS_RETRY_ENABLED is False)
add("destructive execution disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
add("recovery precedes retry", RECOVERY_PRECEDES_RETRY is True)
add("foreground read is retryable", "pc.get_foreground_window" in RETRYABLE_ACTIONS)
add("minimize is not retryable", "pc.minimize_window" not in RETRYABLE_ACTIONS)
add("restore is not retryable", "pc.restore_window_state" not in RETRYABLE_ACTIONS)
assert_r8_safety_contract()
add("R8 safety contract assertion", True)

# ---------------------------------------------------------------------------
# Recoverable pre-mutation failure -> explicit retry -> resume -> completion.
with tempfile.TemporaryDirectory(prefix="aura_a200_r8_retry_") as td:
    backend = FakeBackend(fail_first_foreground=True)
    receipt_store, receipts, mission_store, engine, r7, r8 = build_runtime(td, backend)

    mission = engine.create_mission(
        "A200-R8 supervised retry then complete reversible mission",
        success_criteria=(
            "pause after recoverable read failure",
            "require exact retry approval",
            "resume canonical mission",
            "complete reversible workflow",
        ),
    )
    specs = r8.build_retryable_task_specs(
        hwnd=backend.target_hwnd,
        title=backend.target_title,
    )
    engine.plan_mission(mission.mission_id, specs)
    engine.start_mission(mission.mission_id)

    first = r8.run_until_pause_or_complete(mission.mission_id)
    add("first recoverable failure pauses for retry approval", first.phase == "waiting_retry_approval", first)
    failed_mission = engine.get_mission(mission.mission_id)
    failed_task = task_by_key(failed_mission, "observe_before")
    add("failed read attempt recorded once", failed_task.status == "failed" and failed_task.attempts == 1)
    add("MissionEngine entered recovering", failed_mission.status == "recovering")
    add("no mutation occurred before retry", backend.states[backend.target_hwnd] == "normal")
    add("failed R4 read owns canonical failed receipt", len(receipts.list_receipts()) == 1 and receipts.list_receipts()[0].status == "failed")

    candidate = r8.inspect_retry_candidate(mission.mission_id)
    add("retry candidate action is read-only", candidate.action == "pc.get_foreground_window")
    add("candidate binds failed attempt one", candidate.failed_attempt == 1)
    add("candidate has exact failure digest", len(candidate.failure_digest) == 64)

    # Approval alone must not execute anything.
    grant = RetryApprovalGrant.explicit_for(candidate)
    receipt_count = len(receipts.list_receipts())
    add("creating retry approval creates no receipt", len(receipts.list_receipts()) == receipt_count)

    # Make the previous grant stale by adding evidence to the failure snapshot.
    engine.record_evidence(
        mission.mission_id,
        failed_task.task_id,
        "retry_diagnostic",
        {"reviewed": True},
    )
    must_raise(
        "stale retry approval rejected",
        RetryApprovalError,
        lambda: r8.approve_retry(candidate, approval=grant),
    )
    add("stale retry approval created no receipt", len(receipts.list_receipts()) == receipt_count)
    add("stale retry approval caused no mutation", backend.states[backend.target_hwnd] == "normal")

    fresh = r8.inspect_retry_candidate(mission.mission_id)
    fresh_grant = RetryApprovalGrant.explicit_for(fresh)
    retried = r8.approve_retry(fresh, approval=fresh_grant)
    add("MissionEngine retry_task scheduled", retried.status == "ready")
    resumed = engine.get_mission(mission.mission_id)
    add("MissionEngine resumed after explicit retry", resumed.status == "running")

    second = r8.run_until_pause_or_complete(mission.mission_id)
    add("retry succeeds then mission reaches mutation confirmation", second.phase == "waiting_confirmation", second)
    after_retry = engine.get_mission(mission.mission_id)
    observe = task_by_key(after_retry, "observe_before")
    add("retryable read succeeded on second attempt", observe.status == "succeeded" and observe.attempts == 2)
    add("read retry still caused no mutation", backend.states[backend.target_hwnd] == "normal")
    add("retry created one additional successful canonical receipt", len(receipts.list_receipts()) == 2)
    add("first receipt failed second receipt succeeded", [r.status for r in receipts.list_receipts()] == ["failed", "succeeded"])

    confirmed = r7.confirm_waiting_task(mission.mission_id)
    add("explicit mutation confirmation still required", confirmed.status == "succeeded")
    add("mutation occurred only after separate confirmation", backend.states[backend.target_hwnd] == "minimized")

    final = r8.run_until_pause_or_complete(mission.mission_id)
    add("mission completes after supervised retry", final.phase == "completed", final)
    finished = engine.get_mission(mission.mission_id)
    add("MissionEngine final status completed", finished.status == "completed")
    add("exact window state restored after mission", backend.states[backend.target_hwnd] == "normal")
    add("original foreground restored after mission", backend.foreground == backend.target_hwnd)
    add("no recovery token pending at completion", r7.recovery_pending is False)

    evidence_kinds = [
        finished.evidence[eid].kind
        for eid in task_by_key(finished, "observe_before").evidence_ids
    ]
    add("retry task preserves first failure evidence", "execution_error" in evidence_kinds, evidence_kinds)
    add("retry task records final execution result", "execution_result" in evidence_kinds, evidence_kinds)
    add("retry diagnostic evidence preserved", "retry_diagnostic" in evidence_kinds, evidence_kinds)
    add("retry task has two authorization evidences", evidence_kinds.count("authorization") == 2, evidence_kinds)

    add("MissionEngine persistence survives retry lifecycle", mission_store.load(mission.mission_id).status == "completed")

# ---------------------------------------------------------------------------
# Retry bound: second failed attempt cannot be retried again.
with tempfile.TemporaryDirectory(prefix="aura_a200_r8_bound_") as td:
    backend = FakeBackend(fail_all_foreground=True)
    receipt_store, receipts, mission_store, engine, r7, r8 = build_runtime(td, backend)

    mission = engine.create_mission("A200-R8 retry bound enforcement")
    engine.plan_mission(
        mission.mission_id,
        r8.build_retryable_task_specs(
            hwnd=backend.target_hwnd,
            title=backend.target_title,
        ),
    )
    engine.start_mission(mission.mission_id)

    paused = r8.run_until_pause_or_complete(mission.mission_id)
    add("persistent failure first pauses for retry approval", paused.phase == "waiting_retry_approval")
    candidate = r8.inspect_retry_candidate(mission.mission_id)
    r8.approve_retry(candidate, approval=RetryApprovalGrant.explicit_for(candidate))

    bounded = r8.run_until_pause_or_complete(mission.mission_id)
    add("second failed attempt becomes nonretryable", bounded.phase == "failed_nonretryable", bounded)
    bounded_mission = engine.get_mission(mission.mission_id)
    bounded_task = task_by_key(bounded_mission, "observe_before")
    add("retry bound consumed exactly two attempts", bounded_task.attempts == 2)
    add("mission cancelled after retry bound", bounded_mission.status == "cancelled")
    add("retry-bound scenario never mutated window", backend.states[backend.target_hwnd] == "normal")
    add("retry-bound scenario has two failed receipts", [r.status for r in receipts.list_receipts()] == ["failed", "failed"])
    must_raise(
        "no retry candidate after bound reached",
        RetryCandidateError,
        lambda: r8.inspect_retry_candidate(mission.mission_id),
    )

# ---------------------------------------------------------------------------
# Failure after mutation: recovery MUST win over retry.
with tempfile.TemporaryDirectory(prefix="aura_a200_r8_postmut_") as td:
    backend = FakeBackend(fail_post_mutation_foreground=True)
    receipt_store, receipts, mission_store, engine, r7, r8 = build_runtime(td, backend)

    mission = engine.create_mission("A200-R8 recovery precedence after mutation")
    engine.plan_mission(
        mission.mission_id,
        r8.build_retryable_task_specs(
            hwnd=backend.target_hwnd,
            title=backend.target_title,
        ),
    )
    engine.start_mission(mission.mission_id)

    pre = r8.run_until_pause_or_complete(mission.mission_id)
    add("post-mutation scenario pauses for mutation confirmation", pre.phase == "waiting_confirmation")
    r7.confirm_waiting_task(mission.mission_id)
    add("post-mutation scenario window mutated", backend.states[backend.target_hwnd] == "minimized")
    add("post-mutation scenario recovery pending", r7.recovery_pending is True)

    post = r8.run_until_pause_or_complete(mission.mission_id)
    add("post-mutation failure recovered instead of retried", post.phase == "failed_recovered", post)
    recovered = engine.get_mission(mission.mission_id)
    add("post-mutation mission cancelled after recovery", recovered.status == "cancelled")
    add("post-mutation window restored", backend.states[backend.target_hwnd] == "normal")
    add("post-mutation foreground restored", backend.foreground == backend.target_hwnd)
    add("post-mutation recovery token consumed", r7.recovery_pending is False)
    add("emergency recovery canonical receipt exists", bool(post.emergency_restore_receipt_id))
    add("emergency recovery receipt succeeded", receipts.get_receipt(post.emergency_restore_receipt_id).status == "succeeded")
    must_raise(
        "post-mutation failed task cannot become retry candidate",
        RetryCandidateError,
        lambda: r8.inspect_retry_candidate(mission.mission_id),
    )

src_path = ROOT / "runtime" / "aura_supervised_recovery_retry_v200.py"
src = src_path.read_text(encoding="utf-8-sig", errors="replace")
add("R8 uses canonical MissionEngine", "from mission_engine import MissionEngine" in src)
add("R8 wraps R7 executor", "A200SupervisedMissionExecutor" in src)
add("R8 uses canonical retry_task", ".retry_task(" in src)
add("R8 uses canonical resume", ".resume(" in src)
add("R8 source has no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
add("R8 source has no shell/native APIs", all(x not in src for x in ("os.system(", "os.popen(", "ctypes.", "win32", "WindowsPcControlAdapter(")))
add("R8 contains no close capability", "pc.close_window" not in src)
add("R8 contains no terminate capability", "pc.terminate_process" not in src)

failed = [x for x in checks if not x[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
if failed:
    print("failed = " + ", ".join(x[0] for x in failed))
    raise SystemExit(1)
print("[PASS] A200-R8 bounded supervised recovery/retry/resume invariant")
