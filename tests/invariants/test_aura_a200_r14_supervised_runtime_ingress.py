from __future__ import annotations

from dataclasses import replace
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_persistent_runtime_bootstrap_v200 import (
    A200PersistentRuntimeBootstrap,
)
from runtime.aura_supervised_runtime_ingress_v200 import (
    A200SupervisedRuntimeIngress,
    A200_R14_MARKER,
    APPROVAL_DURABILITY_REQUIRED,
    APPROVAL_EXACT_BINDING_REQUIRED,
    APPROVAL_ONE_USE,
    APPROVAL_REUSE_AFTER_RESTART_ENABLED,
    APPROVAL_SESSION_BOUND,
    ARBITRARY_TOOL_INGRESS_ENABLED,
    AUTO_APPROVAL_ENABLED,
    AUTONOMOUS_MUTATION_ENABLED,
    AUTONOMOUS_RETRY_ENABLED,
    ApprovalBridgeError,
    ApprovalGrant,
    DESTRUCTIVE_EXECUTION_ENABLED,
    EXPLICIT_APPROVAL_BRIDGE_REQUIRED,
    LEASE_STEAL_ENABLED,
    READ_ONLY_STATUS_SURFACE_REQUIRED,
    RuntimeIngressError,
    STRUCTURED_INGRESS_ONLY,
    assert_r14_safety_contract,
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
        self.target_hwnd = 16101
        self.other_hwnd = 16102
        self.target_title = "A200 R14 Structured Ingress Synthetic Target"
        self.other_title = "A200 R14 Structured Ingress Synthetic Other"
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
        pid = 16201 if hwnd == self.target_hwnd else 16202
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
            ProcessSnapshot(16201, "a200-r14-target.exe", 1),
            ProcessSnapshot(16202, "a200-r14-other.exe", 1),
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


add("A200-R14 marker", A200_R14_MARKER == "AURA_A200_R14_SUPERVISED_RUNTIME_INGRESS_EXPLICIT_APPROVAL_STATUS_V1")
add("structured ingress only", STRUCTURED_INGRESS_ONLY is True)
add("explicit approval bridge required", EXPLICIT_APPROVAL_BRIDGE_REQUIRED is True)
add("approval durability required", APPROVAL_DURABILITY_REQUIRED is True)
add("approval exact binding required", APPROVAL_EXACT_BINDING_REQUIRED is True)
add("approval one-use", APPROVAL_ONE_USE is True)
add("approval session-bound", APPROVAL_SESSION_BOUND is True)
add("read-only status surface required", READ_ONLY_STATUS_SURFACE_REQUIRED is True)
add("arbitrary tool ingress disabled", ARBITRARY_TOOL_INGRESS_ENABLED is False)
add("automatic approval disabled", AUTO_APPROVAL_ENABLED is False)
add("approval reuse after restart disabled", APPROVAL_REUSE_AFTER_RESTART_ENABLED is False)
add("autonomous retry disabled", AUTONOMOUS_RETRY_ENABLED is False)
add("autonomous mutation disabled", AUTONOMOUS_MUTATION_ENABLED is False)
add("lease stealing disabled", LEASE_STEAL_ENABLED is False)
add("destructive execution disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
assert_r14_safety_contract()
add("R14 safety contract assertion", True)

# -------------------------------------------------------------------
# REAL READ-ONLY ingress and safe status surface.
# -------------------------------------------------------------------
live_root = Path(tempfile.mkdtemp(prefix="aura_a200_r14_live_read_"))
try:
    runtime = A200PersistentRuntimeBootstrap(
        state_root=live_root,
        backend=None,
        owner_id="r14-live-read",
    )
    ingress = A200SupervisedRuntimeIngress(runtime=runtime)
    status = ingress.status_surface()
    add("clean status surface read-only ready", status.read_only_ready is True)
    add("clean status surface mutation ready", status.mutation_ready is True)
    add("clean status has no pending approval", len(status.pending_approval_ids) == 0)

    before_receipts = len(runtime.receipts.list_receipts())
    result = ingress.submit_read(
        "pc.get_foreground_window",
        request_id="r14-live-real-read",
    )
    real_read_only_windows_observation = True
    add("real read-only ingress succeeded", result.ok and result.status == "succeeded")
    add("real read-only ingress owns canonical receipt", bool(result.receipt_id))
    add("real read receipt succeeded", runtime.receipts.get_receipt(result.receipt_id).status == "succeeded")
    add("real read created exactly one receipt", len(runtime.receipts.list_receipts()) == before_receipts + 1)

    after_read_receipts = len(runtime.receipts.list_receipts())
    must_raise(
        "read ingress rejects reversible mutation capability",
        RuntimeIngressError,
        lambda: ingress.submit_read(
            "pc.minimize_window",
            params={"hwnd": 1},
        ),
    )
    add("rejected arbitrary ingress created no receipt", len(runtime.receipts.list_receipts()) == after_read_receipts)
    runtime.close()
finally:
    shutil.rmtree(live_root, ignore_errors=True)

# -------------------------------------------------------------------
# SYNTHETIC mission approval: exact, one-use, no stale/tampered grant.
# -------------------------------------------------------------------
state_root = Path(tempfile.mkdtemp(prefix="aura_a200_r14_approval_"))
backend = FakeBackend()
try:
    runtime = A200PersistentRuntimeBootstrap(
        state_root=state_root,
        backend=backend,
        owner_id="r14-approval-session",
    )
    ingress = A200SupervisedRuntimeIngress(runtime=runtime)
    progress = ingress.submit_reversible_window_mission(
        hwnd=backend.target_hwnd,
        title=backend.target_title,
        goal="R14 exact approval bridge mission",
    )
    add("structured mission reaches waiting confirmation", progress.phase == "waiting_confirmation")
    challenge = progress.approval_challenge
    add("waiting mission returns approval challenge", challenge is not None)
    add("challenge state pending", challenge is not None and challenge.state == "pending")
    add("challenge digest is SHA256", challenge is not None and len(challenge.challenge_digest) == 64)
    add("challenge params digest is SHA256", challenge is not None and len(challenge.params_digest) == 64)
    add("runtime mutation blocked while confirmation pending", runtime.mutation_ready is False)
    add("no synthetic mutation before approval", backend.minimize_calls == 0)
    add("durable approval row pending", ingress.approval_store.count("pending") == 1)

    status = ingress.status_surface()
    add("status exposes pending mission", len(status.tracked_missions) == 1)
    add("status exposes one pending approval", challenge.approval_id in status.pending_approval_ids)
    add("status reports mutation blocked", status.mutation_ready is False)

    grant = ApprovalGrant.explicit_for(challenge)
    tampered = replace(grant, challenge_digest="0" * 64)
    receipt_count = len(runtime.receipts.list_receipts())
    must_raise(
        "tampered approval digest rejected",
        ApprovalBridgeError,
        lambda: ingress.approve(tampered),
    )
    add("tampered approval caused no mutation", backend.minimize_calls == 0)
    add("tampered approval created no receipt", len(runtime.receipts.list_receipts()) == receipt_count)
    add("challenge remains pending after tamper", ingress.approval_store.get(challenge.approval_id).state == "pending")

    denied = replace(grant, explicit_confirmation=False)
    must_raise(
        "non-explicit approval rejected",
        ApprovalBridgeError,
        lambda: ingress.approve(denied),
    )
    add("non-explicit approval caused no mutation", backend.minimize_calls == 0)

    completed = ingress.approve(grant)
    add("exact approval completes mission", completed.phase == "completed")
    add("MissionEngine mission completed after approval", completed.mission_status == "completed")
    add("synthetic mutation happened exactly once", backend.minimize_calls == 1)
    add("synthetic restore happened", backend.restore_calls >= 1, backend.restore_calls)
    add("synthetic target restored", backend.states[backend.target_hwnd] == "normal")
    add("synthetic foreground restored", backend.foreground == backend.target_hwnd)
    add("approval row consumed", ingress.approval_store.get(challenge.approval_id).state == "consumed")
    add("pending approval count zero after completion", ingress.approval_store.count("pending") == 0)

    receipt_count = len(runtime.receipts.list_receipts())
    must_raise(
        "consumed approval cannot be reused",
        ApprovalBridgeError,
        lambda: ingress.approve(grant),
    )
    add("approval reuse caused no second mutation", backend.minimize_calls == 1)
    add("approval reuse created no receipt", len(runtime.receipts.list_receipts()) == receipt_count)

    status2 = ingress.status_surface()
    add("status surface ready after completion", status2.mutation_ready is True)
    add("status surface consumed count one", status2.approval_counts["consumed"] == 1)
    runtime.close()
finally:
    shutil.rmtree(state_root, ignore_errors=True)

# -------------------------------------------------------------------
# RESTART: old pending approval is invalidated; fresh session challenge required.
# -------------------------------------------------------------------
restart_root = Path(tempfile.mkdtemp(prefix="aura_a200_r14_restart_"))
backend = FakeBackend()
try:
    runtime1 = A200PersistentRuntimeBootstrap(
        state_root=restart_root,
        backend=backend,
        owner_id="r14-restart-session-1",
    )
    ingress1 = A200SupervisedRuntimeIngress(runtime=runtime1)
    p1 = ingress1.submit_reversible_window_mission(
        hwnd=backend.target_hwnd,
        title=backend.target_title,
        goal="R14 restart stale-approval mission",
    )
    old_challenge = p1.approval_challenge
    old_grant = ApprovalGrant.explicit_for(old_challenge)
    add("restart scenario challenge created", old_challenge is not None)
    add("restart scenario no mutation before restart", backend.minimize_calls == 0)
    runtime1.close()

    runtime2 = A200PersistentRuntimeBootstrap(
        state_root=restart_root,
        backend=backend,
        owner_id="r14-restart-session-2",
    )
    ingress2 = A200SupervisedRuntimeIngress(runtime=runtime2)
    old_row = ingress2.approval_store.get(old_challenge.approval_id)
    add("foreign-session pending challenge marked stale", old_row.state == "stale_session")
    add("restart still rehydrates waiting mission", runtime2.engine.get_mission(p1.mission_id).status == "waiting_confirmation")
    add("restart still caused no mutation", backend.minimize_calls == 0)

    receipt_count = len(runtime2.receipts.list_receipts())
    must_raise(
        "old-session approval grant rejected after restart",
        ApprovalBridgeError,
        lambda: ingress2.approve(old_grant),
    )
    add("old-session approval caused no mutation", backend.minimize_calls == 0)
    add("old-session approval created no receipt", len(runtime2.receipts.list_receipts()) == receipt_count)

    fresh = ingress2.issue_approval_challenge(p1.mission_id)
    add("fresh restart challenge bound to new session", fresh.session_id == runtime2.session_id)
    add("fresh restart challenge differs from old", fresh.approval_id != old_challenge.approval_id)
    done = ingress2.approve(ApprovalGrant.explicit_for(fresh))
    add("fresh post-restart approval completes mission", done.phase == "completed")
    add("post-restart synthetic mutation exactly once", backend.minimize_calls == 1)
    add("post-restart synthetic window restored", backend.states[backend.target_hwnd] == "normal")
    add("old challenge remains stale", ingress2.approval_store.get(old_challenge.approval_id).state == "stale_session")
    add("fresh challenge consumed", ingress2.approval_store.get(fresh.approval_id).state == "consumed")

    status = ingress2.status_surface()
    add("status reports stale session approval count", status.approval_counts["stale_session"] == 1)
    add("status reports consumed approval count", status.approval_counts["consumed"] == 1)
    add("status has no pending approvals after restart completion", len(status.pending_approval_ids) == 0)
    runtime2.close()
finally:
    shutil.rmtree(restart_root, ignore_errors=True)

# -------------------------------------------------------------------
# Source/architecture invariants.
# -------------------------------------------------------------------
src_path = ROOT / "runtime" / "aura_supervised_runtime_ingress_v200.py"
src = src_path.read_text(encoding="utf-8-sig", errors="replace")
add("R14 wraps R13 persistent runtime", "A200PersistentRuntimeBootstrap" in src)
add("R14 uses companion SQLite approval store", "r14_approval_challenges" in src)
add("R14 approval store uses BEGIN IMMEDIATE", "BEGIN IMMEDIATE" in src)
add("R14 approval store explicitly closes connections", "with closing(self._connect())" in src)
add("R14 exact params digest binding present", "_params_digest(task.tool_call.params)" in src)
add("R14 exact plan revision binding present", "mission.plan.revision" in src)
add("R14 exact task id binding present", "task.task_id" in src)
add("R14 session binding present", "self.runtime.session_id" in src)
add("R14 one-use consume transition present", "state='consuming'" in src and "state='consumed'" in src)
add("R14 stale-session invalidation present", "stale_session" in src)
add("R14 status surface is read-only data projection", "RuntimeStatusSurface" in src)
add("R14 contains no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
add("R14 contains no raw shell/native API", all(x not in src for x in (
    "os.system(",
    "os.popen(",
    "ctypes.",
    "WindowsPcControlAdapter(",
)))
add("R14 contains no close capability", "pc.close_window" not in src)
add("R14 contains no terminate capability", "pc.terminate_process" not in src)

failed = [item for item in checks if not item[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
print(f"R14_REAL_READ_ONLY_WINDOWS_OBSERVATION = {real_read_only_windows_observation}")
print(f"R14_REAL_PC_OR_WINDOW_MUTATED = {real_pc_or_window_mutated}")
if failed:
    print("failed = " + ", ".join(item[0] for item in failed))
    raise SystemExit(1)
if not real_read_only_windows_observation:
    raise SystemExit("R14 expected one real read-only Windows observation")
if real_pc_or_window_mutated:
    raise SystemExit("R14 must not mutate the real desktop")
print("[PASS] A200-R14 supervised runtime ingress + explicit approval bridge + status surface")
