from __future__ import annotations

import ctypes
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_restart_recovery_safety_acceptance_v200 import (
    A200_R23_MARKER,
    APPROVAL_REPLAY_AFTER_CRASH_DISABLED,
    AUTO_APPROVAL_ENABLED,
    AUTO_CANCEL_ENABLED,
    AUTONOMOUS_MULTI_MUTATION_ENABLED,
    AUTONOMOUS_RETRY_ENABLED,
    CANCELLATION_BEFORE_MUTATION_REQUIRED,
    CLOSE_WINDOW_ENABLED,
    CRASH_AFTER_DISPATCH_RECOVERY_REQUIRED,
    DESTRUCTIVE_EXECUTION_ENABLED,
    EXACT_RESTORE_REQUIRED,
    EXPLICIT_HUMAN_APPROVAL_REQUIRED,
    LIVE_CAPABILITY,
    SELF_WINDOW_ONLY,
    SHELL_EXECUTION_ENABLED,
    SINGLE_LIVE_MUTATION_MAX,
    STALE_APPROVAL_MUST_FAIL_CLOSED,
    STARTUP_RECOVERY_PRECEDENCE_REQUIRED,
    TERMINATE_PROCESS_ENABLED,
    assert_r23_safety_contract,
    task_by_key,
)
from runtime.aura_persistent_runtime_bootstrap_v200 import (
    A200PersistentRuntimeBootstrap,
)
from runtime.aura_supervised_runtime_ingress_v200 import (
    A200SupervisedRuntimeIngress,
)
from runtime.aura_ui_conversation_supervised_bridge_v200 import (
    A200UiConversationCommandBridge,
    UiApprovalPresentationError,
    UiCancellationError,
)

checks = []
real_mutation_count = 0
final_state_restored = False
emergency_recovery_attempted = False


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


user32 = ctypes.windll.user32


def title_of(hwnd: int) -> str:
    length = int(user32.GetWindowTextLengthW(int(hwnd)))
    buf = ctypes.create_unicode_buffer(max(length + 2, 2))
    user32.GetWindowTextW(int(hwnd), buf, len(buf))
    return buf.value


def snap(hwnd: int) -> dict:
    return {
        "exists": bool(user32.IsWindow(int(hwnd))),
        "title": title_of(int(hwnd)),
        "iconic": bool(user32.IsIconic(int(hwnd))),
        "zoomed": bool(user32.IsZoomed(int(hwnd))),
        "foreground": int(user32.GetForegroundWindow()) == int(hwnd),
    }


def assert_exact_console(marker: str) -> tuple[int, dict]:
    hwnd = int(user32.GetForegroundWindow())
    current = snap(hwnd)
    if hwnd <= 0 or current["title"] != marker:
        raise RuntimeError(
            "R23 exact foreground console requirement failed: "
            + repr(current)
        )
    if current["iconic"]:
        raise RuntimeError("R23 console unexpectedly minimized before scenario")
    return hwnd, current


marker = str(os.environ.get("AURA_A200_R23_CONSOLE_MARKER") or "").strip()
run_token = str(os.environ.get("AURA_A200_R23_RUN_TOKEN") or "").strip()
human_approved = os.environ.get("AURA_A200_R23_USER_APPROVED") == "YES"

add(
    "R23 marker",
    A200_R23_MARKER
    == "AURA_A200_R23_RESTART_STALE_CANCEL_CRASH_RECOVERY_SAFETY_V1",
)
add("R23 self-window only", SELF_WINDOW_ONLY is True)
add("R23 explicit human approval required", EXPLICIT_HUMAN_APPROVAL_REQUIRED is True)
add("R23 stale approvals fail closed", STALE_APPROVAL_MUST_FAIL_CLOSED is True)
add("R23 cancellation before mutation required", CANCELLATION_BEFORE_MUTATION_REQUIRED is True)
add("R23 crash recovery required", CRASH_AFTER_DISPATCH_RECOVERY_REQUIRED is True)
add("R23 startup recovery precedence", STARTUP_RECOVERY_PRECEDENCE_REQUIRED is True)
add("R23 post-crash replay disabled", APPROVAL_REPLAY_AFTER_CRASH_DISABLED is True)
add("R23 single live mutation max one", SINGLE_LIVE_MUTATION_MAX == 1)
add("R23 live capability exact", LIVE_CAPABILITY == "pc.minimize_window")
add("R23 exact restore required", EXACT_RESTORE_REQUIRED is True)
add("R23 auto approval disabled", AUTO_APPROVAL_ENABLED is False)
add("R23 auto cancel disabled", AUTO_CANCEL_ENABLED is False)
add("R23 autonomous retry disabled", AUTONOMOUS_RETRY_ENABLED is False)
add("R23 autonomous multi-mutation disabled", AUTONOMOUS_MULTI_MUTATION_ENABLED is False)
add("R23 destructive disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
add("R23 close disabled", CLOSE_WINDOW_ENABLED is False)
add("R23 terminate disabled", TERMINATE_PROCESS_ENABLED is False)
add("R23 runtime shell disabled", SHELL_EXECUTION_ENABLED is False)
add("R23 marker env present", bool(marker), marker)
add("R23 run token env present", bool(run_token), run_token)
add("R23 explicit human approval received", human_approved is True)
assert_r23_safety_contract()
add("R23 safety contract assertion", True)

if not human_approved:
    raise RuntimeError("R23 human approval missing")

initial_hwnd, initial_snapshot = assert_exact_console(marker)
add("R23 exact initial target exists", initial_snapshot["exists"] is True)
add("R23 exact initial title", initial_snapshot["title"] == marker, initial_snapshot["title"])
add("R23 exact initial foreground", initial_snapshot["foreground"] is True)
add("R23 exact initial not minimized", initial_snapshot["iconic"] is False)

# -------------------------------------------------------------------
# SCENARIO A: waiting approval -> restart -> old card becomes stale.
# Then current-session approval is reissued and mission is cancelled
# before any mutation.
# -------------------------------------------------------------------
restart_root = Path(tempfile.mkdtemp(prefix="aura_a200_r23_restart_"))
runtime1 = runtime2 = None
try:
    hwnd_a, snap_a = assert_exact_console(marker)

    runtime1 = A200PersistentRuntimeBootstrap(
        state_root=restart_root,
        backend=None,
        owner_id="r23-stale-session-1-" + run_token,
    )
    ingress1 = A200SupervisedRuntimeIngress(runtime=runtime1)
    bridge1 = A200UiConversationCommandBridge(ingress=ingress1)

    receipts_a0 = len(runtime1.receipts.list_receipts())
    prepared = bridge1.handle(
        {
            "type": "pc.prepare_minimize_window",
            "hwnd": hwnd_a,
            "title": marker,
            "goal": "R23 real-window stale approval restart scenario",
        }
    ).to_dict()

    add("R23 stale scenario reaches approval.required", prepared["kind"] == "approval.required")
    add("R23 stale scenario waits confirmation", prepared["payload"]["phase"] == "waiting_confirmation")
    mission_a = prepared["payload"]["mission_id"]
    old = dict(prepared["payload"]["approval"])
    add("R23 old approval id present", bool(old["approval_id"]))
    add("R23 old presentation digest SHA256", len(old["presentation_digest"]) == 64)
    add(
        "R23 stale scenario creates only observe-before receipt",
        len(runtime1.receipts.list_receipts()) == receipts_a0 + 1,
    )
    add("R23 stale scenario caused no mutation", snap(hwnd_a)["iconic"] is False)
    runtime1.close()

    runtime2 = A200PersistentRuntimeBootstrap(
        state_root=restart_root,
        backend=None,
        owner_id="r23-stale-session-2-" + run_token,
    )
    ingress2 = A200SupervisedRuntimeIngress(runtime=runtime2)
    bridge2 = A200UiConversationCommandBridge(ingress=ingress2)

    add(
        "R23 restart exposes supervision-required mission",
        mission_a in runtime2.startup_snapshot.supervision_required,
    )
    add("R23 restart does not auto-confirm", snap(hwnd_a)["iconic"] is False)
    add("R23 restart mutation lane blocked", runtime2.mutation_ready is False)
    add("R23 restart read-only lane remains ready", runtime2.read_only_ready is True)

    old_challenge = ingress2.approval_store.get(old["approval_id"])
    add("R23 old challenge still durable", old_challenge is not None)
    add(
        "R23 old challenge marked stale_session",
        old_challenge is not None and old_challenge.state == "stale_session",
        None if old_challenge is None else old_challenge.state,
    )

    receipts_before_old_replay = len(runtime2.receipts.list_receipts())
    must_raise(
        "R23 stale approval cannot confirm after restart",
        UiApprovalPresentationError,
        lambda: bridge2.handle(
            {
                "type": "approval.confirm",
                "approval_id": old["approval_id"],
                "presentation_digest": old["presentation_digest"],
                "confirm": True,
            }
        ),
    )
    add(
        "R23 stale approval replay creates no receipt",
        len(runtime2.receipts.list_receipts()) == receipts_before_old_replay,
    )
    add("R23 stale replay caused no mutation", snap(hwnd_a)["iconic"] is False)

    status2 = bridge2.handle({"type": "runtime.status"}).to_dict()
    add(
        "R23 restart status has no actionable stale approval",
        len(status2["payload"]["pending_approvals"]) == 0,
    )

    fresh_resp = bridge2.handle(
        {
            "type": "approval.present",
            "mission_id": mission_a,
        }
    ).to_dict()
    fresh = dict(fresh_resp["payload"]["approval"])
    add("R23 fresh approval belongs current session", fresh["session_id"] == runtime2.session_id)
    add("R23 fresh approval id differs", fresh["approval_id"] != old["approval_id"])
    add(
        "R23 fresh presentation digest differs",
        fresh["presentation_digest"] != old["presentation_digest"],
    )

    must_raise(
        "R23 cancellation without explicit flag rejected",
        UiCancellationError,
        lambda: bridge2.handle(
            {
                "type": "mission.cancel",
                "mission_id": mission_a,
                "confirm_cancel": False,
            }
        ),
    )
    add(
        "R23 rejected cancellation leaves mission waiting",
        runtime2.engine.get_mission(mission_a).status == "waiting_confirmation",
    )
    add("R23 rejected cancellation caused no mutation", snap(hwnd_a)["iconic"] is False)

    cancelled = bridge2.handle(
        {
            "type": "mission.cancel",
            "mission_id": mission_a,
            "confirm_cancel": True,
        }
    ).to_dict()
    add("R23 explicit cancel returns mission.cancelled", cancelled["kind"] == "mission.cancelled")
    add(
        "R23 MissionEngine persisted cancelled restart mission",
        runtime2.engine.get_mission(mission_a).status == "cancelled",
    )
    fresh_state = ingress2.approval_store.get(fresh["approval_id"])
    add(
        "R23 fresh approval invalidated by cancellation",
        fresh_state is not None and fresh_state.state == "failed",
        None if fresh_state is None else fresh_state.state,
    )
    add("R23 cancellation caused no mutation", snap(hwnd_a)["iconic"] is False)
    add("R23 mutation lane restored after cancellation", runtime2.mutation_ready is True)
    add("R23 no recovery journal after pre-mutation cancel", runtime2.crash_journal.get_pending(mission_a) is None)

    replay_count = len(runtime2.receipts.list_receipts())
    must_raise(
        "R23 cancelled fresh approval cannot be reused",
        UiApprovalPresentationError,
        lambda: bridge2.handle(
            {
                "type": "approval.confirm",
                "approval_id": fresh["approval_id"],
                "presentation_digest": fresh["presentation_digest"],
                "confirm": True,
            }
        ),
    )
    add(
        "R23 cancelled approval reuse creates no receipt",
        len(runtime2.receipts.list_receipts()) == replay_count,
    )

finally:
    if runtime2 is not None:
        try:
            runtime2.close()
        except Exception:
            pass
    if runtime1 is not None:
        try:
            runtime1.close()
        except Exception:
            pass
    shutil.rmtree(restart_root, ignore_errors=True)

# -------------------------------------------------------------------
# SCENARIO B: real self-window mutation dispatch succeeds, then an
# injected BaseException simulates abrupt process death BEFORE mission
# commit. A new R13 bootstrap MUST restore automatically on startup.
# -------------------------------------------------------------------
class SimulatedProcessCrash(BaseException):
    pass

crash_root = Path(tempfile.mkdtemp(prefix="aura_a200_r23_crash_"))
crash_runtime = recovery_runtime = None
crash_mission = ""
crash_approval = {}
crash_hwnd = 0
crash_snapshot_before = None
crash_once = {"armed": True}

def crash_hook(call, result):
    global real_mutation_count
    if crash_once["armed"] and str(call.action) == "pc.minimize_window":
        crash_once["armed"] = False
        real_mutation_count += 1
        raise SimulatedProcessCrash(
            "R23 injected abrupt crash after real provider mutation"
        )

try:
    crash_hwnd, crash_snapshot_before = assert_exact_console(marker)

    crash_runtime = A200PersistentRuntimeBootstrap(
        state_root=crash_root,
        backend=None,
        owner_id="r23-crash-session-1-" + run_token,
        after_dispatch_hook=crash_hook,
    )
    crash_ingress = A200SupervisedRuntimeIngress(runtime=crash_runtime)
    crash_bridge = A200UiConversationCommandBridge(ingress=crash_ingress)

    receipts_c0 = len(crash_runtime.receipts.list_receipts())
    prepared_c = crash_bridge.handle(
        {
            "type": "pc.prepare_minimize_window",
            "hwnd": crash_hwnd,
            "title": marker,
            "goal": "R23 live crash-after-dispatch recovery mission",
        }
    ).to_dict()
    crash_mission = prepared_c["payload"]["mission_id"]
    crash_approval = dict(prepared_c["payload"]["approval"])

    add("R23 crash scenario reaches waiting confirmation", prepared_c["payload"]["phase"] == "waiting_confirmation")
    add(
        "R23 crash scenario pre-approval receipt exactly one",
        len(crash_runtime.receipts.list_receipts()) == receipts_c0 + 1,
    )
    add("R23 no mutation before crash approval", snap(crash_hwnd)["iconic"] is False)

    crashed = False
    try:
        crash_bridge.handle(
            {
                "type": "approval.confirm",
                "approval_id": crash_approval["approval_id"],
                "presentation_digest": crash_approval["presentation_digest"],
                "confirm": True,
            }
        )
    except SimulatedProcessCrash:
        crashed = True

    add("R23 injected process crash escaped normal approval flow", crashed is True)
    add("R23 exactly one live mutation dispatched", real_mutation_count == 1, real_mutation_count)

    crash_boundary = snap(crash_hwnd)
    add("R23 target minimized at crash boundary", crash_boundary["iconic"] is True)
    add("R23 target left foreground at crash boundary", crash_boundary["foreground"] is False)

    pending = crash_runtime.crash_journal.get_pending(crash_mission)
    add("R23 durable crash journal armed", pending is not None)
    add(
        "R23 crash journal owns mutation receipt",
        pending is not None and bool(pending.mutation_receipt_id),
    )
    add(
        "R23 crash journal recovery digest SHA256",
        pending is not None and len(pending.recovery_digest) == 64,
    )
    add(
        "R23 durable idempotency intent running at crash",
        crash_runtime.intent_ledger.count(state="running") == 1,
    )

    persisted = crash_runtime.engine.get_mission(crash_mission)
    mutate_task = task_by_key(persisted, "minimize_once")
    add("R23 MissionEngine mission running at crash", persisted.status == "running")
    add("R23 mutation task running at crash", mutate_task.status == "running")
    add("R23 mutation not falsely committed to task result", mutate_task.result is None)

    consuming = crash_ingress.approval_store.get(crash_approval["approval_id"])
    add("R23 crash approval remains durable", consuming is not None)
    add(
        "R23 crash approval is non-pending consuming",
        consuming is not None and consuming.state == "consuming",
        None if consuming is None else consuming.state,
    )

    # No crash_runtime.close(): emulate the old process vanishing.
    recovery_runtime = A200PersistentRuntimeBootstrap(
        state_root=crash_root,
        backend=None,
        owner_id="r23-crash-session-2-" + run_token,
    )
    recovery_ingress = A200SupervisedRuntimeIngress(runtime=recovery_runtime)
    recovery_bridge = A200UiConversationCommandBridge(ingress=recovery_ingress)

    startup = recovery_runtime.startup_snapshot
    add(
        "R23 startup automatically recovered crashed mission",
        crash_mission in startup.recovered_missions,
        startup.recovered_missions,
    )
    add("R23 startup recovery has no failures", len(startup.startup_failures) == 0)
    add("R23 startup recovery leaves no supervision blocker", len(startup.supervision_required) == 0)
    add("R23 startup recovery re-enables mutation lane", recovery_runtime.mutation_ready is True)
    add("R23 startup recovery keeps read-only lane ready", recovery_runtime.read_only_ready is True)

    recovered_mission = recovery_runtime.engine.get_mission(crash_mission)
    add("R23 recovered MissionEngine mission cancelled", recovered_mission.status == "cancelled")
    add("R23 crash journal consumed after startup restore", recovery_runtime.crash_journal.get_pending(crash_mission) is None)
    add("R23 exactly one restored crash journal", recovery_runtime.crash_journal.count(state="restored") == 1)
    add("R23 running intent reconciled to recovered", recovery_runtime.intent_ledger.count(state="recovered") == 1)

    row = recovery_runtime.session_store.get_mission_row(crash_mission)
    recovery_receipt_id = str(row["recovery_receipt_id"] or "")
    add("R23 session registry marks recovered mission terminal", bool(row["terminal"]))
    add("R23 session registry stores recovery receipt", bool(recovery_receipt_id), recovery_receipt_id)
    if recovery_receipt_id:
        add(
            "R23 recovery receipt succeeded",
            recovery_runtime.receipts.get_receipt(recovery_receipt_id).status == "succeeded",
        )

    receipts_after_recovery = len(recovery_runtime.receipts.list_receipts())
    add(
        "R23 crash journey owns exactly three canonical receipts",
        receipts_after_recovery == receipts_c0 + 3,
        f"{receipts_c0}->{receipts_after_recovery}",
    )

    post_recovery_approval = recovery_ingress.approval_store.get(
        crash_approval["approval_id"]
    )
    add("R23 post-crash approval still durable", post_recovery_approval is not None)
    add(
        "R23 post-crash approval remains non-pending",
        post_recovery_approval is not None
        and post_recovery_approval.state != "pending",
        None if post_recovery_approval is None else post_recovery_approval.state,
    )

    before_replay = len(recovery_runtime.receipts.list_receipts())
    must_raise(
        "R23 post-crash approval replay rejected",
        UiApprovalPresentationError,
        lambda: recovery_bridge.handle(
            {
                "type": "approval.confirm",
                "approval_id": crash_approval["approval_id"],
                "presentation_digest": crash_approval["presentation_digest"],
                "confirm": True,
            }
        ),
    )
    add(
        "R23 post-crash replay creates no receipt",
        len(recovery_runtime.receipts.list_receipts()) == before_replay,
    )
    add("R23 post-crash replay causes no second mutation", real_mutation_count == 1)

    # Exact W132 restoration proof.
    final = None
    for _ in range(30):
        final = snap(crash_hwnd)
        if (
            final["exists"]
            and final["title"] == marker
            and final["iconic"] == crash_snapshot_before["iconic"]
            and final["zoomed"] == crash_snapshot_before["zoomed"]
            and final["foreground"]
        ):
            break
        time.sleep(0.1)

    add("R23 recovered target still exists", final["exists"] is True)
    add("R23 recovered title exact", final["title"] == marker, final["title"])
    add(
        "R23 recovered minimized state exact",
        final["iconic"] == crash_snapshot_before["iconic"],
        f"{crash_snapshot_before['iconic']}->{final['iconic']}",
    )
    add(
        "R23 recovered maximized state exact",
        final["zoomed"] == crash_snapshot_before["zoomed"],
        f"{crash_snapshot_before['zoomed']}->{final['zoomed']}",
    )
    add("R23 recovered foreground exact", final["foreground"] is True)

    final_state_restored = all(
        [
            final["exists"],
            final["title"] == marker,
            final["iconic"] == crash_snapshot_before["iconic"],
            final["zoomed"] == crash_snapshot_before["zoomed"],
            final["foreground"],
        ]
    )
    print(f"R23_REAL_MUTATION_COUNT = {real_mutation_count}", flush=True)
    print(f"R23_FINAL_STATE_RESTORED = {final_state_restored}", flush=True)

finally:
    # Emergency safety net: if the invariant itself faults after the live
    # mutation, instantiate the certified R13 startup recovery again.
    try:
        if crash_mission and crash_root.exists():
            current = snap(crash_hwnd) if crash_hwnd else {}
            needs_recovery = bool(
                current
                and (
                    current.get("iconic")
                    or not current.get("foreground")
                )
            )
            pending_exists = False
            if recovery_runtime is not None:
                try:
                    pending_exists = (
                        recovery_runtime.crash_journal.get_pending(crash_mission)
                        is not None
                    )
                except Exception:
                    pending_exists = False
            elif crash_runtime is not None:
                try:
                    pending_exists = (
                        crash_runtime.crash_journal.get_pending(crash_mission)
                        is not None
                    )
                except Exception:
                    pending_exists = False

            if needs_recovery or pending_exists:
                emergency_recovery_attempted = True
                emergency = A200PersistentRuntimeBootstrap(
                    state_root=crash_root,
                    backend=None,
                    owner_id="r23-emergency-recovery-" + run_token,
                )
                emergency.close()
    except Exception as emergency_exc:
        print(
            "[EMERGENCY-RECOVERY-ERROR] "
            + f"{type(emergency_exc).__name__}: {emergency_exc}",
            flush=True,
        )

    if recovery_runtime is not None:
        try:
            recovery_runtime.close()
        except Exception:
            pass

    # After emergency handling, record the actual final desktop state.
    if crash_hwnd:
        try:
            settled = snap(crash_hwnd)
            if crash_snapshot_before is not None:
                final_state_restored = all(
                    [
                        settled["exists"],
                        settled["title"] == marker,
                        settled["iconic"] == crash_snapshot_before["iconic"],
                        settled["zoomed"] == crash_snapshot_before["zoomed"],
                        settled["foreground"],
                    ]
                )
        except Exception:
            pass

    shutil.rmtree(crash_root, ignore_errors=True)

add("R23 live mutation count exact one", real_mutation_count == 1, real_mutation_count)
add("R23 final state restored after all recovery handling", final_state_restored is True)
add("R23 emergency recovery not needed on normal PASS path", emergency_recovery_attempted is False)

src = (
    ROOT / "runtime" / "aura_restart_recovery_safety_acceptance_v200.py"
).read_text(encoding="utf-8-sig", errors="replace")
add("R23 guard source contains no subprocess", "import subprocess" not in src and "from subprocess" not in src)
add("R23 guard source contains no shell API", all(token not in src for token in ("os.system(", "os.popen(", "ctypes.", "child_process")))
add("R23 guard source contains no close capability", "pc.close_window" not in src)
add("R23 guard source contains no terminate capability", "pc.terminate_process" not in src)

failed = [item for item in checks if not item[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
print(f"R23_REAL_MUTATION_COUNT = {real_mutation_count}")
print(f"R23_FINAL_STATE_RESTORED = {final_state_restored}")
print(f"R23_EMERGENCY_RECOVERY_ATTEMPTED = {emergency_recovery_attempted}")
if failed:
    print("failed = " + ", ".join(item[0] for item in failed))
    raise SystemExit(1)
if real_mutation_count != 1:
    raise SystemExit("R23 expected exactly one live reversible mutation")
if not final_state_restored:
    raise SystemExit("R23 exact final desktop state was not restored")
print("[PASS] A200-R23 restart stale-approval cancellation + live crash startup-recovery safety acceptance")
