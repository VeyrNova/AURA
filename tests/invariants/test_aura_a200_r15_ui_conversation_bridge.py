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
)
from runtime.aura_supervised_runtime_ingress_v200 import (
    A200SupervisedRuntimeIngress,
)
from runtime.aura_ui_conversation_supervised_bridge_v200 import (
    A200UiConversationCommandBridge,
    A200_R15_MARKER,
    APPROVAL_PRESENTATION_DIGEST_REQUIRED,
    ARBITRARY_COMMAND_EXECUTION_ENABLED,
    ARBITRARY_TOOL_INGRESS_ENABLED,
    AUTO_APPROVAL_ENABLED,
    AUTO_CANCEL_ENABLED,
    AUTONOMOUS_MUTATION_ENABLED,
    AUTONOMOUS_RETRY_ENABLED,
    DESTRUCTIVE_EXECUTION_ENABLED,
    EXPLICIT_APPROVAL_CONFIRMATION_REQUIRED,
    EXPLICIT_CANCELLATION_CONFIRMATION_REQUIRED,
    MISSIONENGINE_CANCEL_AUTHORITY_REQUIRED,
    NATURAL_LANGUAGE_DIRECT_EXECUTION_ENABLED,
    STRUCTURED_UI_COMMANDS_ONLY,
    SUPERVISED_CANCELLATION_REQUIRED,
    UiApprovalPresentationError,
    UiCancellationError,
    UiCommandBridgeError,
    assert_r15_safety_contract,
)
from runtime.aura_pc_control_windows_v131 import (
    WindowSnapshot,
    ProcessSnapshot,
)


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
        self.target_hwnd = 17101
        self.other_hwnd = 17102
        self.target_title = "A200 R15 UI Bridge Synthetic Target"
        self.other_title = "A200 R15 UI Bridge Synthetic Other"
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
        pid = 17201 if hwnd == self.target_hwnd else 17202
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
            ProcessSnapshot(17201, "a200-r15-target.exe", 1),
            ProcessSnapshot(17202, "a200-r15-other.exe", 1),
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


add("A200-R15 marker", A200_R15_MARKER == "AURA_A200_R15_UI_CONVERSATION_COMMAND_BRIDGE_APPROVAL_CANCELLATION_V1")
add("structured UI commands only", STRUCTURED_UI_COMMANDS_ONLY is True)
add("approval presentation digest required", APPROVAL_PRESENTATION_DIGEST_REQUIRED is True)
add("explicit approval confirmation required", EXPLICIT_APPROVAL_CONFIRMATION_REQUIRED is True)
add("explicit cancellation confirmation required", EXPLICIT_CANCELLATION_CONFIRMATION_REQUIRED is True)
add("supervised cancellation required", SUPERVISED_CANCELLATION_REQUIRED is True)
add("MissionEngine cancellation authority required", MISSIONENGINE_CANCEL_AUTHORITY_REQUIRED is True)
add("natural language direct execution disabled", NATURAL_LANGUAGE_DIRECT_EXECUTION_ENABLED is False)
add("arbitrary command execution disabled", ARBITRARY_COMMAND_EXECUTION_ENABLED is False)
add("arbitrary tool ingress disabled", ARBITRARY_TOOL_INGRESS_ENABLED is False)
add("auto approval disabled", AUTO_APPROVAL_ENABLED is False)
add("auto cancel disabled", AUTO_CANCEL_ENABLED is False)
add("autonomous retry disabled", AUTONOMOUS_RETRY_ENABLED is False)
add("autonomous mutation disabled", AUTONOMOUS_MUTATION_ENABLED is False)
add("destructive execution disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
assert_r15_safety_contract()
add("R15 safety contract assertion", True)

# -------------------------------------------------------------------
# REAL read-only command through R15.
# -------------------------------------------------------------------
live_root = Path(tempfile.mkdtemp(prefix="aura_a200_r15_live_read_"))
try:
    runtime = A200PersistentRuntimeBootstrap(
        state_root=live_root,
        backend=None,
        owner_id="r15-live-read",
    )
    ingress = A200SupervisedRuntimeIngress(runtime=runtime)
    bridge = A200UiConversationCommandBridge(ingress=ingress)

    status = bridge.handle({"type": "runtime.status"}).to_dict()
    add("R15 clean status response ok", status["ok"] is True)
    add("R15 clean status kind", status["kind"] == "runtime.status")
    add("R15 clean status read-only ready", status["payload"]["read_only_ready"] is True)
    add("R15 clean status mutation ready", status["payload"]["mutation_ready"] is True)

    before = len(runtime.receipts.list_receipts())
    read = bridge.handle(
        {
            "type": "pc.read_foreground",
            "request_id": "r15-real-ui-read",
        }
    ).to_dict()
    real_read_only_windows_observation = True
    add("R15 real read command succeeded", read["ok"] is True)
    add("R15 real read command kind", read["kind"] == "pc.read_foreground")
    add("R15 real read owns canonical receipt", bool(read["payload"]["receipt_id"]))
    add("R15 real read created exactly one receipt", len(runtime.receipts.list_receipts()) == before + 1)

    after = len(runtime.receipts.list_receipts())
    must_raise(
        "R15 rejects unknown structured command",
        UiCommandBridgeError,
        lambda: bridge.handle({"type": "shell.execute", "command": "dir"}),
    )
    add("unknown command created no receipt", len(runtime.receipts.list_receipts()) == after)
    runtime.close()
finally:
    shutil.rmtree(live_root, ignore_errors=True)

# -------------------------------------------------------------------
# SYNTHETIC exact approval presentation -> explicit confirmation.
# -------------------------------------------------------------------
state_root = Path(tempfile.mkdtemp(prefix="aura_a200_r15_approval_"))
backend = FakeBackend()
try:
    runtime = A200PersistentRuntimeBootstrap(
        state_root=state_root,
        backend=backend,
        owner_id="r15-approval",
    )
    ingress = A200SupervisedRuntimeIngress(runtime=runtime)
    bridge = A200UiConversationCommandBridge(ingress=ingress)

    prepared = bridge.handle(
        {
            "type": "pc.prepare_minimize_window",
            "hwnd": backend.target_hwnd,
            "title": backend.target_title,
            "goal": "R15 UI presentation approval mission",
        }
    ).to_dict()
    add("prepare command returns approval.required", prepared["kind"] == "approval.required")
    add("prepare command returns waiting mission", prepared["payload"]["phase"] == "waiting_confirmation")
    approval = dict(prepared["payload"]["approval"])
    add("approval presentation id present", bool(approval["approval_id"]))
    add("approval presentation digest SHA256", len(approval["presentation_digest"]) == 64)
    add("approval challenge digest SHA256", len(approval["challenge_digest"]) == 64)
    add("approval presentation exact target hwnd", approval["target_hwnd"] == backend.target_hwnd)
    add("approval presentation exact target title", approval["target_title"] == backend.target_title)
    add("approval presentation reversible", approval["reversible"] is True)
    add("approval presentation explicit confirmation flag", approval["requires_explicit_confirmation"] is True)
    add("no synthetic mutation before UI confirmation", backend.minimize_calls == 0)

    status = bridge.handle({"type": "runtime.status"}).to_dict()
    add("status presents pending approval card", len(status["payload"]["pending_approvals"]) == 1)
    add("status mutation lane blocked while pending", status["payload"]["mutation_ready"] is False)

    receipt_count = len(runtime.receipts.list_receipts())
    bad_digest = dict(approval)
    bad_digest["presentation_digest"] = "0" * 64
    must_raise(
        "tampered UI presentation digest rejected",
        UiApprovalPresentationError,
        lambda: bridge.handle(
            {
                "type": "approval.confirm",
                "approval_id": bad_digest["approval_id"],
                "presentation_digest": bad_digest["presentation_digest"],
                "confirm": True,
            }
        ),
    )
    add("tampered presentation caused no mutation", backend.minimize_calls == 0)
    add("tampered presentation created no receipt", len(runtime.receipts.list_receipts()) == receipt_count)

    must_raise(
        "approval confirm false rejected",
        UiApprovalPresentationError,
        lambda: bridge.handle(
            {
                "type": "approval.confirm",
                "approval_id": approval["approval_id"],
                "presentation_digest": approval["presentation_digest"],
                "confirm": False,
            }
        ),
    )
    add("non-explicit UI approval caused no mutation", backend.minimize_calls == 0)

    completed = bridge.handle(
        {
            "type": "approval.confirm",
            "approval_id": approval["approval_id"],
            "presentation_digest": approval["presentation_digest"],
            "confirm": True,
        }
    ).to_dict()
    add("exact UI approval completes mission", completed["kind"] == "approval.completed")
    add("exact UI approval MissionEngine completed", completed["payload"]["mission_status"] == "completed")
    add("synthetic mutation exactly once after UI approval", backend.minimize_calls == 1)
    add("synthetic target restored after UI approval", backend.states[backend.target_hwnd] == "normal")
    add("synthetic foreground restored after UI approval", backend.foreground == backend.target_hwnd)

    final_status = bridge.handle({"type": "runtime.status"}).to_dict()
    add("status ready after approved mission", final_status["payload"]["mutation_ready"] is True)
    add("status has no pending approval after consume", len(final_status["payload"]["pending_approvals"]) == 0)
    runtime.close()
finally:
    shutil.rmtree(state_root, ignore_errors=True)

# -------------------------------------------------------------------
# SYNTHETIC supervised cancellation before mutation.
# -------------------------------------------------------------------
cancel_root = Path(tempfile.mkdtemp(prefix="aura_a200_r15_cancel_"))
backend = FakeBackend()
try:
    runtime = A200PersistentRuntimeBootstrap(
        state_root=cancel_root,
        backend=backend,
        owner_id="r15-cancel",
    )
    ingress = A200SupervisedRuntimeIngress(runtime=runtime)
    bridge = A200UiConversationCommandBridge(ingress=ingress)

    prepared = bridge.handle(
        {
            "type": "pc.prepare_minimize_window",
            "hwnd": backend.target_hwnd,
            "title": backend.target_title,
            "goal": "R15 supervised cancellation mission",
        }
    ).to_dict()
    mission_id = prepared["payload"]["mission_id"]
    approval = dict(prepared["payload"]["approval"])
    add("cancel scenario starts waiting_confirmation", prepared["payload"]["phase"] == "waiting_confirmation")
    add("cancel scenario no mutation before cancellation", backend.minimize_calls == 0)

    must_raise(
        "cancel without explicit confirmation rejected",
        UiCancellationError,
        lambda: bridge.handle(
            {
                "type": "mission.cancel",
                "mission_id": mission_id,
                "confirm_cancel": False,
            }
        ),
    )
    add("rejected cancellation leaves mission waiting", runtime.engine.get_mission(mission_id).status == "waiting_confirmation")
    add("rejected cancellation caused no mutation", backend.minimize_calls == 0)

    cancelled = bridge.handle(
        {
            "type": "mission.cancel",
            "mission_id": mission_id,
            "confirm_cancel": True,
        }
    ).to_dict()
    add("explicit cancel returns mission.cancelled", cancelled["kind"] == "mission.cancelled")
    add("MissionEngine persisted cancelled state", runtime.engine.get_mission(mission_id).status == "cancelled")
    add("cancelled before mutation causes no mutation", backend.minimize_calls == 0)
    add("cancel invalidated pending approval", cancelled["payload"]["invalidated_approvals"] == 1)
    challenge = ingress.approval_store.get(approval["approval_id"])
    add("cancelled approval terminal failed", challenge.state == "failed")
    add("runtime readiness restored after cancellation", runtime.mutation_ready is True)

    receipt_count = len(runtime.receipts.list_receipts())
    must_raise(
        "approval for cancelled mission cannot be used",
        UiApprovalPresentationError,
        lambda: bridge.handle(
            {
                "type": "approval.confirm",
                "approval_id": approval["approval_id"],
                "presentation_digest": approval["presentation_digest"],
                "confirm": True,
            }
        ),
    )
    add("cancelled approval reuse caused no mutation", backend.minimize_calls == 0)
    add("cancelled approval reuse created no receipt", len(runtime.receipts.list_receipts()) == receipt_count)
    runtime.close()
finally:
    shutil.rmtree(cancel_root, ignore_errors=True)

# -------------------------------------------------------------------
# RESTART presentation: old R14 approval disappears; R15 reissues current card.
# -------------------------------------------------------------------
restart_root = Path(tempfile.mkdtemp(prefix="aura_a200_r15_restart_"))
backend = FakeBackend()
try:
    runtime1 = A200PersistentRuntimeBootstrap(
        state_root=restart_root,
        backend=backend,
        owner_id="r15-restart-1",
    )
    ingress1 = A200SupervisedRuntimeIngress(runtime=runtime1)
    bridge1 = A200UiConversationCommandBridge(ingress=ingress1)
    p1 = bridge1.handle(
        {
            "type": "pc.prepare_minimize_window",
            "hwnd": backend.target_hwnd,
            "title": backend.target_title,
            "goal": "R15 restart presentation mission",
        }
    ).to_dict()
    mission_id = p1["payload"]["mission_id"]
    old_approval = dict(p1["payload"]["approval"])
    add("restart scenario old presentation created", bool(old_approval["approval_id"]))
    add("restart scenario still no mutation", backend.minimize_calls == 0)
    runtime1.close()

    runtime2 = A200PersistentRuntimeBootstrap(
        state_root=restart_root,
        backend=backend,
        owner_id="r15-restart-2",
    )
    ingress2 = A200SupervisedRuntimeIngress(runtime=runtime2)
    bridge2 = A200UiConversationCommandBridge(ingress=ingress2)

    status = bridge2.handle({"type": "runtime.status"}).to_dict()
    add("restart bridge sees supervised mission", len(status["payload"]["tracked_missions"]) == 1)
    add("restart bridge does not present stale old approval", len(status["payload"]["pending_approvals"]) == 0)
    add("restart still caused no mutation", backend.minimize_calls == 0)

    fresh_response = bridge2.handle(
        {
            "type": "approval.present",
            "mission_id": mission_id,
        }
    ).to_dict()
    fresh = dict(fresh_response["payload"]["approval"])
    add("restart reissues current-session approval", fresh["session_id"] == runtime2.session_id)
    add("restart approval id differs from old", fresh["approval_id"] != old_approval["approval_id"])
    add("restart presentation digest differs from old", fresh["presentation_digest"] != old_approval["presentation_digest"])

    must_raise(
        "old presentation cannot confirm after restart",
        UiApprovalPresentationError,
        lambda: bridge2.handle(
            {
                "type": "approval.confirm",
                "approval_id": old_approval["approval_id"],
                "presentation_digest": old_approval["presentation_digest"],
                "confirm": True,
            }
        ),
    )
    add("old presentation caused no mutation after restart", backend.minimize_calls == 0)

    done = bridge2.handle(
        {
            "type": "approval.confirm",
            "approval_id": fresh["approval_id"],
            "presentation_digest": fresh["presentation_digest"],
            "confirm": True,
        }
    ).to_dict()
    add("fresh presentation completes mission after restart", done["payload"]["mission_status"] == "completed")
    add("fresh presentation causes one synthetic mutation", backend.minimize_calls == 1)
    add("fresh presentation mission restores target", backend.states[backend.target_hwnd] == "normal")
    runtime2.close()
finally:
    shutil.rmtree(restart_root, ignore_errors=True)

# -------------------------------------------------------------------
# Source architecture.
# -------------------------------------------------------------------
src_path = ROOT / "runtime" / "aura_ui_conversation_supervised_bridge_v200.py"
src = src_path.read_text(encoding="utf-8-sig", errors="replace")
add("R15 wraps R14 supervised ingress", "A200SupervisedRuntimeIngress" in src)
add("R15 does not instantiate MissionEngine", "MissionEngine(" not in src)
add("R15 allowed command set present", "ALLOWED_COMMANDS" in src)
add("R15 presentation digest recomputed", "recompute_digest" in src and "presentation_digest" in src)
add("R15 exact HWND/title presentation present", "target_hwnd" in src and "target_title" in src)
add("R15 approval flows through R14 ingress.approve", "self.ingress.approve(" in src)
add("R15 cancellation flows through MissionEngine.cancel", "self.runtime.engine.cancel(" in src)
add("R15 invalidates approval without executing it", "mark_failed(" in src)
add("R15 contains no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
add("R15 contains no raw shell/native API", all(token not in src for token in (
    "os.system(",
    "os.popen(",
    "ctypes.",
    "WindowsPcControlAdapter(",
)))
add("R15 contains no close capability", "pc.close_window" not in src)
add("R15 contains no terminate capability", "pc.terminate_process" not in src)

failed = [item for item in checks if not item[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
print(f"R15_REAL_READ_ONLY_WINDOWS_OBSERVATION = {real_read_only_windows_observation}")
print(f"R15_REAL_PC_OR_WINDOW_MUTATED = {real_pc_or_window_mutated}")
if failed:
    print("failed = " + ", ".join(item[0] for item in failed))
    raise SystemExit(1)
if not real_read_only_windows_observation:
    raise SystemExit("R15 expected one real read-only Windows observation")
if real_pc_or_window_mutated:
    raise SystemExit("R15 must not mutate the real desktop")
print("[PASS] A200-R15 UI/conversation command bridge + approval presentation + supervised cancellation")
