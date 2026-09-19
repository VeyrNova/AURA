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
from runtime.aura_supervised_mission_executor_v200 import (
    A200SupervisedMissionExecutor,
    A200_R7_MARKER,
    AUTONOMOUS_MULTI_MUTATION_ENABLED,
    AUTONOMOUS_RETRY_ENABLED,
    DESTRUCTIVE_EXECUTION_ENABLED,
    FAIL_SAFE_RECOVERY_REQUIRED,
    R7MissionBindingError,
    assert_r7_safety_contract,
)
from runtime.integration_permissions_pc_v131 import evaluate_integration_permission_pc_v131


checks = []

def add(name, ok, detail=""):
    ok = bool(ok)
    checks.append((name, ok, str(detail)))
    print(("[PASS] " if ok else "[FAIL] ") + name + (f" :: {detail}" if detail else ""))


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
    def __init__(self, *, fail_read_after_minimize=False):
        self.target_hwnd = 9101
        self.other_hwnd = 9102
        self.target_title = "A200 R7 Synthetic Mission Target"
        self.other_title = "A200 R7 Synthetic Other Window"
        self.states = {
            self.target_hwnd: "normal",
            self.other_hwnd: "normal",
        }
        self.foreground = self.target_hwnd
        self.restore_calls = []
        self.focus_calls = []
        self.fail_read_after_minimize = bool(fail_read_after_minimize)
        self.failed_post_mutation_read = False

    def _snap(self, hwnd):
        title = self.target_title if hwnd == self.target_hwnd else self.other_title
        pid = 9201 if hwnd == self.target_hwnd else 9202
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
            ProcessSnapshot(9201, "a200-r7-target.exe", 1),
            ProcessSnapshot(9202, "a200-r7-other.exe", 1),
        ]

    def foreground_window(self):
        if (
            self.fail_read_after_minimize
            and self.states[self.target_hwnd] == "minimized"
            and not self.failed_post_mutation_read
        ):
            self.failed_post_mutation_read = True
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


def foreground_hwnd(task_result):
    if not isinstance(task_result, dict):
        return 0
    output = task_result.get("output")
    if not isinstance(output, dict):
        return 0
    pc_result = output.get("pc_result")
    if not isinstance(pc_result, dict):
        return 0
    data = pc_result.get("data")
    if not isinstance(data, dict):
        return 0
    try:
        return int(data.get("hwnd") or 0)
    except Exception:
        return 0


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
        origin="a200-r7-read",
    )
    mutation_binding = A200ReversibleMutationBinding(
        registry=registry,
        origin="a200-r7-mutation",
    )

    mission_store = SQLiteMissionStore(Path(td) / "missions.sqlite3")
    holder = {}
    engine = MissionEngine(
        security_engine=MissionSecurity(),
        tool_executor=lambda call: holder["bridge"].tool_executor(call),
        store=mission_store,
    )
    bridge = A200SupervisedMissionExecutor(
        mission_engine=engine,
        read_binding=read_binding,
        mutation_binding=mutation_binding,
    )
    holder["bridge"] = bridge
    return receipt_store, receipts, mission_store, engine, bridge


def task_by_key(mission, key):
    return next(task for task in mission.tasks.values() if task.key == key)


add("A200-R7 marker", A200_R7_MARKER == "AURA_A200_R7_SUPERVISED_MULTI_STEP_E2E_MISSION_V1")
add("multi-mutation remains disabled", AUTONOMOUS_MULTI_MUTATION_ENABLED is False)
add("autonomous retry remains disabled", AUTONOMOUS_RETRY_ENABLED is False)
add("destructive execution remains disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
add("fail-safe recovery mandatory", FAIL_SAFE_RECOVERY_REQUIRED is True)
assert_r7_safety_contract()
add("R7 safety contract assertion", True)

# ---------------------------------------------------------------------------
# Happy-path canonical MissionEngine lifecycle.
with tempfile.TemporaryDirectory(prefix="aura_a200_r7_happy_") as td:
    backend = FakeBackend()
    receipt_store, receipts, mission_store, engine, bridge = build_runtime(td, backend)

    mission = engine.create_mission(
        "A200-R7 supervised five-step reversible Windows mission",
        success_criteria=(
            "read foreground before mutation",
            "pause for explicit mutation confirmation",
            "mutate exactly one window",
            "restore exact W132 preimage",
            "complete with all required tasks evidenced",
        ),
    )
    specs = bridge.build_mission_task_specs(
        hwnd=backend.target_hwnd,
        title=backend.target_title,
    )
    planned = engine.plan_mission(mission.mission_id, specs)
    add("MissionEngine plan has five tasks", len(planned.tasks) == 5)
    add("MissionEngine plan revision 1", planned.plan is not None and planned.plan.revision == 1)

    started = engine.start_mission(mission.mission_id)
    add("MissionEngine mission started", started.status == "running")

    first = bridge.run_until_pause_or_complete(mission.mission_id)
    add("mission pauses for explicit confirmation", first.phase == "waiting_confirmation", first)
    paused = engine.get_mission(mission.mission_id)
    add("MissionEngine status waiting_confirmation", paused.status == "waiting_confirmation")
    add("observe_before succeeded", task_by_key(paused, "observe_before").status == "succeeded")
    add("minimize task waiting_confirmation", task_by_key(paused, "minimize_once").status == "waiting_confirmation")
    add("no mutation before confirmation", backend.states[backend.target_hwnd] == "normal")
    add("only pre-mutation read receipt exists", len(receipts.list_receipts()) == 1, len(receipts.list_receipts()))

    confirmed_task = bridge.confirm_waiting_task(mission.mission_id)
    add("explicitly confirmed mutation succeeded", confirmed_task.status == "succeeded")
    add("synthetic target minimized after confirmation", backend.states[backend.target_hwnd] == "minimized")
    add("foreground moved after minimize", backend.foreground == backend.other_hwnd)
    add("R5 recovery pending after mutation", bridge.recovery_pending is True)

    final_run = bridge.run_until_pause_or_complete(mission.mission_id)
    add("five-step mission completed", final_run.phase == "completed", final_run)
    finished = engine.get_mission(mission.mission_id)
    add("MissionEngine final status completed", finished.status == "completed")
    add("all five MissionEngine tasks succeeded", all(t.status == "succeeded" for t in finished.tasks.values()))
    add("exact target show-state restored", backend.states[backend.target_hwnd] == "normal", backend.states)
    add("original foreground restored", backend.foreground == backend.target_hwnd, backend.foreground)
    add("no recovery remains pending", bridge.recovery_pending is False)

    before_task = task_by_key(finished, "observe_before")
    during_task = task_by_key(finished, "observe_mutated")
    final_task = task_by_key(finished, "observe_final")
    add("pre-mutation read saw target foreground", foreground_hwnd(before_task.result) == backend.target_hwnd)
    add("post-mutation read saw other foreground", foreground_hwnd(during_task.result) == backend.other_hwnd)
    add("post-restore read saw target foreground", foreground_hwnd(final_task.result) == backend.target_hwnd)

    minimize_task = task_by_key(finished, "minimize_once")
    restore_task = task_by_key(finished, "restore_exact")
    add("mutation result carries canonical receipt", bool(minimize_task.result.get("receipt_id")))
    add("mutation result carries R2 plan digest", bool(minimize_task.result.get("r2_plan_digest")))
    add("restore result carries canonical receipt", bool(restore_task.result.get("receipt_id")))

    add(
        "every MissionEngine task has authorization + execution evidence",
        all(len(t.evidence_ids) >= 2 for t in finished.tasks.values()),
        {t.key: len(t.evidence_ids) for t in finished.tasks.values()},
    )
    add("MissionEngine persisted one mission", mission_store.count() == 1)
    persisted = mission_store.load(mission.mission_id)
    add("persisted MissionEngine mission completed", persisted is not None and persisted.status == "completed")

    receipt_ids = []
    for task in finished.tasks.values():
        result = task.result if isinstance(task.result, dict) else {}
        rid = result.get("receipt_id")
        if rid:
            receipt_ids.append(rid)
    add("five task actions produced five canonical receipts", len(receipt_ids) == 5, receipt_ids)
    add("canonical receipt ids unique", len(set(receipt_ids)) == 5)
    add(
        "all happy-path canonical receipts succeeded",
        all(receipts.get_receipt(rid).status == "succeeded" for rid in receipt_ids),
    )

# ---------------------------------------------------------------------------
# Failure after mutation: blocked DAG must not strand the window.
with tempfile.TemporaryDirectory(prefix="aura_a200_r7_failure_") as td:
    backend = FakeBackend(fail_read_after_minimize=True)
    receipt_store, receipts, mission_store, engine, bridge = build_runtime(td, backend)

    mission = engine.create_mission(
        "A200-R7 fail-safe recovery after a post-mutation task failure",
        success_criteria=("never strand a reversible mutation",),
    )
    engine.plan_mission(
        mission.mission_id,
        bridge.build_mission_task_specs(
            hwnd=backend.target_hwnd,
            title=backend.target_title,
        ),
    )
    engine.start_mission(mission.mission_id)

    paused = bridge.run_until_pause_or_complete(mission.mission_id)
    add("failure scenario first pauses for confirmation", paused.phase == "waiting_confirmation")
    bridge.confirm_waiting_task(mission.mission_id)
    add("failure scenario mutation occurred", backend.states[backend.target_hwnd] == "minimized")
    add("failure scenario recovery token pending", bridge.recovery_pending is True)

    failed_run = bridge.run_until_pause_or_complete(mission.mission_id)
    add("post-mutation failure triggers fail-safe recovery", failed_run.phase == "failed_recovered", failed_run)
    recovered = engine.get_mission(mission.mission_id)
    add("failed mission cancelled after recovery", recovered.status == "cancelled")
    add("failure path restored target show-state", backend.states[backend.target_hwnd] == "normal", backend.states)
    add("failure path restored original foreground", backend.foreground == backend.target_hwnd)
    add("failure path consumed recovery token", bridge.recovery_pending is False)
    add("emergency restore canonical receipt exists", bool(bridge.last_emergency_restore_receipt_id))
    emergency_receipt = receipts.get_receipt(bridge.last_emergency_restore_receipt_id)
    add("emergency restore receipt succeeded", emergency_receipt.status == "succeeded")

    mutation_task = task_by_key(recovered, "minimize_once")
    evidence_kinds = [
        recovered.evidence[eid].kind
        for eid in mutation_task.evidence_ids
        if eid in recovered.evidence
    ]
    add("MissionEngine records emergency_recovery evidence", "emergency_recovery" in evidence_kinds, evidence_kinds)

    failed_task = task_by_key(recovered, "observe_mutated")
    failed_evidence_kinds = [
        recovered.evidence[eid].kind
        for eid in failed_task.evidence_ids
        if eid in recovered.evidence
    ]
    add("failed task records execution_error evidence", "execution_error" in failed_evidence_kinds, failed_evidence_kinds)
    add("planned restore task cancelled after emergency recovery", task_by_key(recovered, "restore_exact").status == "cancelled")
    add("final verification task cancelled after failure", task_by_key(recovered, "observe_final").status == "cancelled")

    statuses = [r.status for r in receipts.list_receipts()]
    add("failure scenario contains canonical failed receipt", "failed" in statuses, statuses)
    add("failure scenario contains successful recovery receipt", statuses.count("succeeded") >= 3, statuses)

src_path = ROOT / "runtime" / "aura_supervised_mission_executor_v200.py"
src = src_path.read_text(encoding="utf-8-sig", errors="replace")
add("R7 uses canonical MissionEngine", "from mission_engine import MissionEngine" in src)
add("R7 uses R4 read binding", "A200ReadOnlyPcExecutionBinding" in src)
add("R7 uses R5 reversible binding", "A200ReversibleMutationBinding" in src)
add("R7 source has no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
add("R7 source has no shell/native APIs", all(x not in src for x in ("os.system(", "os.popen(", "ctypes.", "win32", "WindowsPcControlAdapter(")))
add("R7 source contains no close capability", "pc.close_window" not in src)
add("R7 source contains no terminate capability", "pc.terminate_process" not in src)

failed = [x for x in checks if not x[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
if failed:
    print("failed = " + ", ".join(x[0] for x in failed))
    raise SystemExit(1)
print("[PASS] A200-R7 supervised multi-step MissionEngine E2E + fail-safe recovery invariant")
