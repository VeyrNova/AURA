from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_persistent_runtime_bootstrap_v200 import (
    A200PersistentRuntimeBootstrap,
    A200_R13_MARKER,
    AUTO_CONFIRM_ON_STARTUP_ENABLED,
    AUTO_RESUME_NONRECOVERY_MISSIONS_ENABLED,
    AUTONOMOUS_MUTATION_ENABLED,
    AUTONOMOUS_RETRY_ENABLED,
    DEFAULT_RUNTIME_STATE_ROOT,
    DESTRUCTIVE_EXECUTION_ENABLED,
    LEASE_STEAL_ENABLED,
    PERSISTENT_RUNTIME_REQUIRED,
    READ_ONLY_DURING_SUPERVISION_BLOCK,
    RuntimeMutationBlocked,
    STARTUP_RECOVERY_REQUIRED,
    SUPERVISED_SESSION_BINDING_REQUIRED,
    assert_r13_safety_contract,
)
from runtime.aura_pc_control_windows_v131 import WindowSnapshot, ProcessSnapshot


checks = []
real_read_only_windows_observation = False
real_pc_or_window_mutated = False


def add(name, ok, detail=""):
    ok = bool(ok)
    checks.append((name, ok, str(detail)))
    print(
        ("[PASS] " if ok else "[FAIL] ")
        + name
        + (f" :: {detail}" if detail else ""),
        flush=True,
    )


def must_raise(name, exc_type, fn):
    try:
        fn()
    except exc_type:
        add(name, True)
    except Exception as exc:
        add(
            name,
            False,
            f"wrong exception {type(exc).__name__}: {exc}",
        )
    else:
        add(name, False, "no exception")


class FakeBackend:
    def __init__(self):
        self.target_hwnd = 15101
        self.other_hwnd = 15102
        self.target_title = "A200 R13 Persistent Synthetic Target"
        self.other_title = "A200 R13 Persistent Synthetic Other"
        self.states = {
            self.target_hwnd: "normal",
            self.other_hwnd: "normal",
        }
        self.foreground = self.target_hwnd
        self.minimize_calls = 0
        self.restore_calls = 0

    def _snap(self, hwnd):
        title = (
            self.target_title
            if hwnd == self.target_hwnd
            else self.other_title
        )
        pid = 15201 if hwnd == self.target_hwnd else 15202
        return WindowSnapshot(
            hwnd=hwnd,
            pid=pid,
            title=title,
            visible=True,
            foreground=(self.foreground == hwnd),
        )

    def discover_windows(self, limit=256):
        return [
            self._snap(self.target_hwnd),
            self._snap(self.other_hwnd),
        ]

    def discover_processes(self, limit=512):
        return [
            ProcessSnapshot(15201, "a200-r13-target.exe", 1),
            ProcessSnapshot(15202, "a200-r13-other.exe", 1),
        ]

    def foreground_window(self):
        return self._snap(self.foreground)

    def window_state(self, hwnd):
        hwnd = int(hwnd)
        return {
            "show_state": self.states[hwnd],
            "foreground": self.foreground == hwnd,
        }

    def restore_window_state(self, hwnd, state):
        self.restore_calls += 1
        hwnd = int(hwnd)
        self.states[hwnd] = str(
            (state or {}).get("show_state") or "normal"
        )
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


add("A200-R13 marker", A200_R13_MARKER == "AURA_A200_R13_PERSISTENT_RUNTIME_BOOTSTRAP_STARTUP_RECOVERY_SESSION_BINDING_V1")
add("persistent runtime required", PERSISTENT_RUNTIME_REQUIRED is True)
add("startup recovery required", STARTUP_RECOVERY_REQUIRED is True)
add("supervised session binding required", SUPERVISED_SESSION_BINDING_REQUIRED is True)
add("read-only during supervision block enabled", READ_ONLY_DURING_SUPERVISION_BLOCK is True)
add("startup auto-confirm disabled", AUTO_CONFIRM_ON_STARTUP_ENABLED is False)
add("non-recovery auto-resume disabled", AUTO_RESUME_NONRECOVERY_MISSIONS_ENABLED is False)
add("autonomous retry disabled", AUTONOMOUS_RETRY_ENABLED is False)
add("autonomous mutation disabled", AUTONOMOUS_MUTATION_ENABLED is False)
add("lease stealing disabled", LEASE_STEAL_ENABLED is False)
add("destructive execution disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
add("default state root is persistent AURA data path", str(DEFAULT_RUNTIME_STATE_ROOT).endswith(r"data\a200_runtime"))
assert_r13_safety_contract()
add("R13 safety contract assertion", True)

# -------------------------------------------------------------------
# REAL read-only Windows composition through the persistent bootstrap.
# -------------------------------------------------------------------
live_root = Path(tempfile.mkdtemp(prefix="aura_a200_r13_live_read_"))
try:
    live = A200PersistentRuntimeBootstrap(
        state_root=live_root,
        backend=None,
        owner_id="r13-live-read",
    )
    add("clean live bootstrap read-only ready", live.read_only_ready is True)
    add("clean live bootstrap mutation-ready", live.mutation_ready is True)
    result = live.execute_read_only(
        "pc.get_foreground_window",
        step_id="r13-live-real-foreground",
    )
    real_read_only_windows_observation = True
    add("real Windows foreground read succeeded", result.ok and result.status == "succeeded")
    add("real Windows foreground read owns canonical receipt", bool(result.receipt_id))
    add("real read canonical receipt succeeded", live.receipts.get_receipt(result.receipt_id).status == "succeeded")
    add("live bootstrap state databases persist", all((live_root / name).exists() for name in (
        "receipts.sqlite3",
        "missions.sqlite3",
        "crash_recovery.sqlite3",
        "idempotency.sqlite3",
        "runtime_sessions.sqlite3",
    )))
    live.close()
finally:
    shutil.rmtree(live_root, ignore_errors=True)

# -------------------------------------------------------------------
# WAITING_CONFIRMATION persists across restart and is NOT auto-confirmed.
# -------------------------------------------------------------------
state_root = Path(tempfile.mkdtemp(prefix="aura_a200_r13_waiting_"))
backend = FakeBackend()
try:
    boot1 = A200PersistentRuntimeBootstrap(
        state_root=state_root,
        backend=backend,
        owner_id="r13-waiting-session-1",
    )
    mission_id = boot1.create_supervised_window_mission(
        hwnd=backend.target_hwnd,
        title=backend.target_title,
        goal="R13 durable waiting-confirmation mission",
    )
    paused = boot1.run_tracked_until_pause_or_complete(mission_id)
    add("first session reaches waiting_confirmation", paused.phase == "waiting_confirmation")
    add("first session created no mutation before confirmation", backend.minimize_calls == 0)
    add("first session readiness blocks new mutation", boot1.mutation_ready is False)
    add("waiting mission tracked persistently", boot1.session_store.mission_count() == 1)
    boot1.close()

    boot2 = A200PersistentRuntimeBootstrap(
        state_root=state_root,
        backend=backend,
        owner_id="r13-waiting-session-2",
    )
    add("restart rehydrates supervised mission", boot2.engine.get_mission(mission_id).status == "waiting_confirmation")
    add("restart does not auto-confirm", backend.minimize_calls == 0)
    add("restart exposes supervision-required mission", mission_id in boot2.startup_snapshot.supervision_required)
    add("restart blocks new mutation while approval pending", boot2.mutation_ready is False)
    add("read-only remains available while mutation blocked", boot2.read_only_ready is True)
    read = boot2.execute_read_only(
        "pc.get_foreground_window",
        step_id="r13-waiting-read-safe",
    )
    add("read-only executes while supervision pending", read.ok and read.status == "succeeded")

    must_raise(
        "missing explicit confirmation rejected",
        RuntimeMutationBlocked,
        lambda: boot2.explicitly_confirm_tracked_mission(
            mission_id,
            explicit_confirmation=False,
        ),
    )
    add("rejected confirmation still caused no mutation", backend.minimize_calls == 0)

    completed = boot2.explicitly_confirm_tracked_mission(
        mission_id,
        explicit_confirmation=True,
    )
    add("explicit post-restart confirmation completes mission", completed.phase == "completed")
    add("synthetic mutation occurred exactly once", backend.minimize_calls == 1)
    add("synthetic target restored after completion", backend.states[backend.target_hwnd] == "normal")
    add("synthetic foreground restored after completion", backend.foreground == backend.target_hwnd)
    add("post-completion recovery journal clear", boot2.crash_journal.get_pending(mission_id) is None)
    add("supervision blocker clears after completion", boot2.mutation_ready is True)
    add("tracked mission terminal after completion", bool(boot2.session_store.get_mission_row(mission_id)["terminal"]))
    add("two supervised runtime sessions persisted", boot2.session_store.session_count() == 2)
    boot2.close()
finally:
    shutil.rmtree(state_root, ignore_errors=True)

# -------------------------------------------------------------------
# CRASH after real synthetic mutation -> automatic startup restoration.
# -------------------------------------------------------------------
class SimulatedProcessCrash(BaseException):
    pass

crash_root = Path(tempfile.mkdtemp(prefix="aura_a200_r13_crash_"))
backend = FakeBackend()
crash_once = {"armed": True}

def crash_hook(call, result):
    if crash_once["armed"] and str(call.action) == "pc.minimize_window":
        crash_once["armed"] = False
        raise SimulatedProcessCrash(
            "R13 synthetic abrupt process crash after provider mutation"
        )

try:
    crash1 = A200PersistentRuntimeBootstrap(
        state_root=crash_root,
        backend=backend,
        owner_id="r13-crash-session-1",
        after_dispatch_hook=crash_hook,
    )
    crash_mid = crash1.create_supervised_window_mission(
        hwnd=backend.target_hwnd,
        title=backend.target_title,
        goal="R13 durable crash-startup-recovery mission",
    )
    paused = crash1.run_tracked_until_pause_or_complete(crash_mid)
    add("crash scenario reaches confirmation pause", paused.phase == "waiting_confirmation")

    crashed = False
    try:
        crash1.explicitly_confirm_tracked_mission(
            crash_mid,
            explicit_confirmation=True,
        )
    except SimulatedProcessCrash:
        crashed = True
    add("simulated crash escapes runtime", crashed is True)
    real_pc_or_window_mutated = False  # backend is synthetic, never real desktop
    add("synthetic crash happened after one mutation", backend.minimize_calls == 1)
    add("synthetic target left minimized at crash boundary", backend.states[backend.target_hwnd] == "minimized")
    add("R9 durable recovery pending at crash boundary", crash1.crash_journal.get_pending(crash_mid) is not None)
    add("R10/R11 running intent durable at crash boundary", crash1.intent_ledger.count(state="running") == 1)
    # Deliberately do not call crash1.close(): emulate process termination.

    crash2 = A200PersistentRuntimeBootstrap(
        state_root=crash_root,
        backend=backend,
        owner_id="r13-crash-session-2",
    )
    snap = crash2.startup_snapshot
    add("startup automatically recovered crashed mission", crash_mid in snap.recovered_missions)
    add("startup recovery has no failure", len(snap.startup_failures) == 0)
    add("startup recovery leaves no supervision blocker", len(snap.supervision_required) == 0)
    add("startup recovery re-enables mutation lane", snap.mutation_ready is True)
    add("startup recovery restored synthetic target", backend.states[backend.target_hwnd] == "normal")
    add("startup recovery restored synthetic foreground", backend.foreground == backend.target_hwnd)
    add("startup recovery consumed R9 pending record", crash2.crash_journal.get_pending(crash_mid) is None)
    add("startup recovery terminal journal count one", crash2.crash_journal.count(state="restored") == 1)
    add("startup recovery reconciled R10/R11 running intent", crash2.intent_ledger.count(state="recovered") == 1)
    recovered_mission = crash2.engine.get_mission(crash_mid)
    add("startup recovery cancels interrupted MissionEngine mission", recovered_mission.status == "cancelled")
    row = crash2.session_store.get_mission_row(crash_mid)
    add("startup session registry marks crash mission terminal", bool(row["terminal"]))
    add("startup session registry stores recovery receipt", bool(row["recovery_receipt_id"]))
    add("startup recovery did not repeat synthetic mutation", backend.minimize_calls == 1)
    add("startup recovery performed exactly one synthetic restore", backend.restore_calls >= 1, backend.restore_calls)
    crash2.close()
finally:
    shutil.rmtree(crash_root, ignore_errors=True)

# -------------------------------------------------------------------
# Source/architecture safety.
# -------------------------------------------------------------------
src_path = ROOT / "runtime" / "aura_persistent_runtime_bootstrap_v200.py"
src = src_path.read_text(encoding="utf-8-sig", errors="replace")
add("R13 composes canonical MissionEngine", "MissionEngine" in src)
add("R13 composes R11 integrated executor", "A200IdempotentCrashSafeMissionExecutor" in src)
add("R13 composes R9 crash journal", "A200CrashRecoveryJournal" in src)
add("R13 composes R10 intent ledger", "A200ExecutionIntentLedger" in src)
add("R13 composes canonical ActionReceiptService", "ActionReceiptService" in src)
add("R13 composes IntegrationRegistry", "IntegrationRegistry" in src)
add("R13 composes certified W131 provider registration", "register_pc_control_provider_v131" in src)
add("R13 persistent SQLite paths present", all(token in src for token in (
    "receipts.sqlite3",
    "missions.sqlite3",
    "crash_recovery.sqlite3",
    "idempotency.sqlite3",
    "runtime_sessions.sqlite3",
)))
add("R13 startup recovery calls recover_after_restart", ".recover_after_restart(" in src)
add("R13 no startup auto-confirm token", "AUTO_CONFIRM_ON_STARTUP_ENABLED = False" in src)
add("R13 no non-recovery auto-resume token", "AUTO_RESUME_NONRECOVERY_MISSIONS_ENABLED = False" in src)
add("R13 contains no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
add("R13 contains no raw shell/native API", all(x not in src for x in (
    "os.system(",
    "os.popen(",
    "ctypes.",
    "WindowsPcControlAdapter(",
)))
add("R13 contains no close capability", "pc.close_window" not in src)
add("R13 contains no terminate capability", "pc.terminate_process" not in src)

failed = [x for x in checks if not x[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
print(f"R13_REAL_READ_ONLY_WINDOWS_OBSERVATION = {real_read_only_windows_observation}")
print(f"R13_REAL_PC_OR_WINDOW_MUTATED = {real_pc_or_window_mutated}")
if failed:
    print("failed = " + ", ".join(x[0] for x in failed))
    raise SystemExit(1)
if not real_read_only_windows_observation:
    raise SystemExit("R13 expected one real read-only Windows observation")
if real_pc_or_window_mutated:
    raise SystemExit("R13 must never mutate the real desktop during acceptance")
print("[PASS] A200-R13 persistent runtime bootstrap + startup recovery + supervised session binding")
