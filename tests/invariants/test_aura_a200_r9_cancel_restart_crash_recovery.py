from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations.registry import IntegrationRegistry
from mission_engine import MissionEngine, MissionStateError, SQLiteMissionStore
from runtime.aura_crash_recovery_v200 import (
    A200CrashRecoveryJournal,
    A200CrashSafeMissionExecutor,
    A200_R9_MARKER,
    A200_R9_R1_MARKER,
    AUTO_RESUME_AFTER_CRASH,
    AUTONOMOUS_MUTATION_ENABLED,
    CRASH_JOURNAL_REQUIRED,
    CRASH_RECOVERY_ONE_USE,
    DESTRUCTIVE_EXECUTION_ENABLED,
    EXPLICIT_SQLITE_CLOSE_REQUIRED,
    CrashRecoveryError,
    assert_r9_safety_contract,
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
    def __init__(self):
        self.target_hwnd = 11101
        self.other_hwnd = 11102
        self.target_title = "A200 R9 Synthetic Crash Target"
        self.other_title = "A200 R9 Synthetic Other"
        self.states = {self.target_hwnd: "normal", self.other_hwnd: "normal"}
        self.foreground = self.target_hwnd

    def _snap(self, hwnd):
        title = self.target_title if hwnd == self.target_hwnd else self.other_title
        pid = 11201 if hwnd == self.target_hwnd else 11202
        return WindowSnapshot(
            hwnd=hwnd, pid=pid, title=title, visible=True,
            foreground=(self.foreground == hwnd),
        )

    def discover_windows(self, limit=256):
        return [self._snap(self.target_hwnd), self._snap(self.other_hwnd)]

    def discover_processes(self, limit=512):
        return [
            ProcessSnapshot(11201, "a200-r9-target.exe", 1),
            ProcessSnapshot(11202, "a200-r9-other.exe", 1),
        ]

    def foreground_window(self):
        return self._snap(self.foreground) if self.foreground else None

    def window_state(self, hwnd):
        hwnd = int(hwnd)
        if hwnd not in self.states:
            return None
        return {"show_state": self.states[hwnd], "foreground": self.foreground == hwnd}

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


def build_process(root, backend, *, crash_wrapper=None):
    receipts = ActionReceiptService(store=ActionReceiptStore(root / "receipts.sqlite3"))
    registry = IntegrationRegistry(
        security_engine=PcSecurity(),
        receipt_service=receipts,
    )
    register_pc_control_provider_v131(registry, backend=backend)

    read_binding = A200ReadOnlyPcExecutionBinding(registry=registry, origin="a200-r9-read")
    mutation_binding = A200ReversibleMutationBinding(registry=registry, origin="a200-r9-mutation")
    mission_store = SQLiteMissionStore(root / "missions.sqlite3")
    journal = A200CrashRecoveryJournal(root / "crash_recovery.sqlite3")

    holder = {}
    def tool_exec(call):
        result = holder["executor"].tool_executor(call)
        if crash_wrapper is not None:
            return crash_wrapper(call, result)
        return result

    engine = MissionEngine(
        security_engine=MissionSecurity(),
        tool_executor=tool_exec,
        store=mission_store,
    )
    executor = A200CrashSafeMissionExecutor(
        mission_engine=engine,
        read_binding=read_binding,
        mutation_binding=mutation_binding,
        crash_journal=journal,
    )
    holder["executor"] = executor
    return receipts, mission_store, journal, engine, executor


def task_by_key(mission, key):
    return next(task for task in mission.tasks.values() if task.key == key)


def plan_and_pause(engine, executor, backend, goal):
    mission = engine.create_mission(goal)
    engine.plan_mission(
        mission.mission_id,
        executor.build_mission_task_specs(
            hwnd=backend.target_hwnd,
            title=backend.target_title,
        ),
    )
    engine.start_mission(mission.mission_id)
    paused = executor.run_until_pause_or_complete(mission.mission_id)
    return mission.mission_id, paused


def windows_handle_release_probe(db_path: Path):
    """Atomic rename fails on Windows while the SQLite file is still open."""
    probe = db_path.with_suffix(".r9r1_probe")
    if probe.exists():
        probe.unlink()
    os.replace(db_path, probe)
    os.replace(probe, db_path)


add("A200-R9 marker", A200_R9_MARKER == "AURA_A200_R9_CANCEL_RESTART_PERSISTENCE_CRASH_RECOVERY_V1")
add("A200-R9-R1 marker", A200_R9_R1_MARKER == "AURA_A200_R9_R1_SQLITE_HANDLE_LIFECYCLE_REPAIR_V1")
add("crash journal mandatory", CRASH_JOURNAL_REQUIRED is True)
add("explicit SQLite close mandatory", EXPLICIT_SQLITE_CLOSE_REQUIRED is True)
add("auto-resume after crash disabled", AUTO_RESUME_AFTER_CRASH is False)
add("autonomous mutation disabled", AUTONOMOUS_MUTATION_ENABLED is False)
add("destructive execution disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
add("crash recovery one-use", CRASH_RECOVERY_ONE_USE is True)
assert_r9_safety_contract()
add("R9 safety contract assertion", True)

# Scenario A: explicit cancellation persists across restart.
with tempfile.TemporaryDirectory(prefix="aura_a200_r9_cancel_") as td:
    root = Path(td)
    backend = FakeBackend()
    receipts1, store1, journal1, engine1, exec1 = build_process(root, backend)
    mission_id, paused = plan_and_pause(engine1, exec1, backend, "A200-R9 explicit cancellation persistence")
    add("cancel scenario reaches confirmation pause", paused.phase == "waiting_confirmation")
    add("cancel scenario has no pending crash journal", journal1.get_pending(mission_id) is None)
    add("cancel scenario window not mutated", backend.states[backend.target_hwnd] == "normal")
    add("journal handle released after read", (windows_handle_release_probe(root / "crash_recovery.sqlite3") is None))

    cancelled = engine1.cancel(mission_id)
    add("MissionEngine explicit cancel succeeds", cancelled.status == "cancelled")

    receipts2, store2, journal2, engine2, exec2 = build_process(root, backend)
    reloaded = engine2.get_mission(mission_id)
    add("cancelled mission reloads as cancelled", reloaded.status == "cancelled")
    add("cancelled mission persistence is durable", store2.load(mission_id).status == "cancelled")
    must_raise("cancelled mission cannot resume after restart", MissionStateError, lambda: engine2.resume(mission_id))
    add("cancel restart produced no mutation", backend.states[backend.target_hwnd] == "normal")
    add("cancel restart has no crash journal", journal2.count() == 0)
    windows_handle_release_probe(root / "crash_recovery.sqlite3")
    add("journal handle released before temp cleanup", True)

# Scenario B: clean restart waiting confirmation -> explicit continuation.
with tempfile.TemporaryDirectory(prefix="aura_a200_r9_resume_") as td:
    root = Path(td)
    backend = FakeBackend()
    receipts1, store1, journal1, engine1, exec1 = build_process(root, backend)
    mission_id, paused = plan_and_pause(engine1, exec1, backend, "A200-R9 restart from waiting confirmation")
    add("resume scenario persisted waiting_confirmation", paused.phase == "waiting_confirmation")
    add("resume scenario no side effect before restart", backend.states[backend.target_hwnd] == "normal")
    receipt_count_before_restart = len(receipts1.list_receipts())

    receipts2, store2, journal2, engine2, exec2 = build_process(root, backend)
    reloaded = engine2.get_mission(mission_id)
    add("waiting mission rehydrates after restart", reloaded.status == "waiting_confirmation")
    add("waiting task rehydrates after restart", task_by_key(reloaded, "minimize_once").status == "waiting_confirmation")
    add("clean restart does not auto-confirm", backend.states[backend.target_hwnd] == "normal")
    add("clean restart creates no new receipt by itself", len(receipts2.list_receipts()) == receipt_count_before_restart)

    confirmed = exec2.confirm_waiting_task(mission_id)
    add("explicit confirmation after restart succeeds", confirmed.status == "succeeded")
    add("mutation occurs only after post-restart confirmation", backend.states[backend.target_hwnd] == "minimized")
    add("durable crash journal armed after mutation", journal2.get_pending(mission_id) is not None)
    completed = exec2.run_until_pause_or_complete(mission_id)
    add("rehydrated mission completes", completed.phase == "completed", completed)
    final = engine2.get_mission(mission_id)
    add("rehydrated MissionEngine final status completed", final.status == "completed")
    add("planned restore clears pending crash journal", journal2.get_pending(mission_id) is None)
    add("journal records restored state", journal2.count(state="restored") == 1)
    add("clean restart final window state restored", backend.states[backend.target_hwnd] == "normal")
    add("clean restart original foreground restored", backend.foreground == backend.target_hwnd)
    windows_handle_release_probe(root / "crash_recovery.sqlite3")
    add("journal handle released after planned restore", True)

# Scenario C: abrupt crash after mutation+journal arm, before MissionEngine commit.
class SimulatedProcessCrash(BaseException):
    pass

with tempfile.TemporaryDirectory(prefix="aura_a200_r9_crash_") as td:
    root = Path(td)
    backend = FakeBackend()
    crash_once = {"armed": True}

    def crash_wrapper(call, result):
        if crash_once["armed"] and str(call.action) == "pc.minimize_window":
            crash_once["armed"] = False
            raise SimulatedProcessCrash("synthetic abrupt process termination after external mutation")
        return result

    receipts1, store1, journal1, engine1, exec1 = build_process(root, backend, crash_wrapper=crash_wrapper)
    mission_id, paused = plan_and_pause(engine1, exec1, backend, "A200-R9 crash after mutation before MissionEngine commit")
    add("crash scenario reaches confirmation pause", paused.phase == "waiting_confirmation")

    crashed = False
    try:
        exec1.confirm_waiting_task(mission_id)
    except SimulatedProcessCrash:
        crashed = True
    add("simulated abrupt crash escaped MissionEngine", crashed is True)
    add("crash occurred after real synthetic mutation", backend.states[backend.target_hwnd] == "minimized")
    pending1 = journal1.get_pending(mission_id)
    add("durable recovery record exists at crash point", pending1 is not None)
    add("crash journal record state armed", pending1 is not None and pending1.state == "armed")
    add("crash journal binds mutation receipt", pending1 is not None and bool(pending1.mutation_receipt_id))
    add("crash journal has exact recovery digest", pending1 is not None and len(pending1.recovery_digest) == 64)
    windows_handle_release_probe(root / "crash_recovery.sqlite3")
    add("journal handle released at crash point", True)

    persisted_mid_crash = store1.load(mission_id)
    mutate_task_mid_crash = task_by_key(persisted_mid_crash, "minimize_once")
    add("MissionEngine persisted task as running at crash", mutate_task_mid_crash.status == "running")
    add("MissionEngine did not falsely commit mutation success", mutate_task_mid_crash.result is None)

    receipts2, store2, journal2, engine2, exec2 = build_process(root, backend)
    reloaded = engine2.get_mission(mission_id)
    add("crashed mission rehydrates from SQLite", reloaded.status == "running")
    add("new process has no R5 in-memory recovery token", exec2.recovery_pending is False)
    add("new process sees durable pending recovery", journal2.get_pending(mission_id) is not None)

    recovery = exec2.recover_after_restart(mission_id)
    add("restart crash recovery succeeded", recovery.restored is True)
    add("crash recovery owns canonical receipt", bool(recovery.restore_receipt_id))
    add("crash recovery canonical receipt succeeded", receipts2.get_receipt(recovery.restore_receipt_id).status == "succeeded")
    add("crash recovery restored target show-state", backend.states[backend.target_hwnd] == "normal")
    add("crash recovery restored original foreground", backend.foreground == backend.target_hwnd)
    add("interrupted mission cancelled after recovery", engine2.get_mission(mission_id).status == "cancelled")
    add("crash journal consumed after restore", journal2.get_pending(mission_id) is None)
    add("crash journal restored count one", journal2.count(state="restored") == 1)

    recovered_mission = engine2.get_mission(mission_id)
    recovered_task = task_by_key(recovered_mission, "minimize_once")
    evidence_kinds = [
        recovered_mission.evidence[eid].kind
        for eid in recovered_task.evidence_ids
        if eid in recovered_mission.evidence
    ]
    add("MissionEngine records crash_recovery evidence", "crash_recovery" in evidence_kinds, evidence_kinds)
    receipt_count_after_recovery = len(receipts2.list_receipts())
    must_raise("one-use crash recovery rejects second recovery", CrashRecoveryError, lambda: exec2.recover_after_restart(mission_id))
    add("second recovery attempt creates no receipt", len(receipts2.list_receipts()) == receipt_count_after_recovery)
    must_raise("crash-recovered cancelled mission cannot resume", MissionStateError, lambda: engine2.resume(mission_id))
    windows_handle_release_probe(root / "crash_recovery.sqlite3")
    add("journal handle released after crash recovery", True)

src_path = ROOT / "runtime" / "aura_crash_recovery_v200.py"
src = src_path.read_text(encoding="utf-8-sig", errors="replace")
add("R9 uses canonical MissionEngine", "from mission_engine import MissionEngine" in src)
add("R9 extends R7 executor", "A200SupervisedMissionExecutor" in src)
add("R9 recovery uses IntegrationRequest", "IntegrationRequest.create(" in src)
add("R9 recovery uses canonical registry dispatch", ".execute_integration(" in src)
add("R9 stores companion SQLite journal", "a200_crash_recovery_journal" in src)
add("R9-R1 explicitly closes SQLite connection", "conn.close()" in src)
add("R9 source has no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
add("R9 source has no raw shell/native API", all(x not in src for x in ("os.system(", "os.popen(", "ctypes.", "win32", "WindowsPcControlAdapter(")))
add("R9 source contains no close capability", "pc.close_window" not in src)
add("R9 source contains no terminate capability", "pc.terminate_process" not in src)

failed = [x for x in checks if not x[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
if failed:
    print("failed = " + ", ".join(x[0] for x in failed))
    raise SystemExit(1)
print("[PASS] A200-R9-R1 cancellation + restart persistence + crash recovery + SQLite lifecycle invariant")
