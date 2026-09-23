from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from action_receipts import ActionReceiptService, ActionReceiptStore
from runtime.aura_live_reversible_acceptance_v200 import (
    A200ControlledLiveAcceptance,
    A200_R6_MARKER,
    AUTO_RESTORE_REQUIRED,
    AUTONOMOUS_MULTI_MUTATION_ENABLED,
    DESTRUCTIVE_EXECUTION_ENABLED,
    LIVE_ACCEPTED_CAPABILITY,
    LIVE_SELF_WINDOW_ONLY,
    LiveAcceptanceDenied,
    SELF_WINDOW_MARKER,
    assert_scope_is_live_self_window_only,
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


class Security:
    def authorize(self, action, params, *, user_confirmed=False):
        return evaluate_integration_permission_pc_v131(action, params=params).decision


approved = os.environ.get("AURA_A200_R6_USER_APPROVED", "").strip().upper() == "YES"

add("A200-R6 marker", A200_R6_MARKER == "AURA_A200_R6_CONTROLLED_LIVE_REVERSIBLE_ACCEPTANCE_V1")
add("live scope self-window only", LIVE_SELF_WINDOW_ONLY is True)
add("automatic restore mandatory", AUTO_RESTORE_REQUIRED is True)
add("multi-mutation remains disabled", AUTONOMOUS_MULTI_MUTATION_ENABLED is False)
add("destructive execution remains disabled", DESTRUCTIVE_EXECUTION_ENABLED is False)
add("single live capability is minimize", LIVE_ACCEPTED_CAPABILITY == "pc.minimize_window")
add("self marker non-empty", bool(SELF_WINDOW_MARKER))
assert_scope_is_live_self_window_only()
add("live safety scope assertion", True)
add("explicit user approval signal received", approved is True)

if not approved:
    print("[BLOCKED] User did not approve the live reversible mutation.")
    raise SystemExit(2)

with tempfile.TemporaryDirectory(prefix="aura_a200_r6_live_") as td:
    store = ActionReceiptStore(Path(td) / "receipts.sqlite3")
    receipts = ActionReceiptService(store=store)

    harness = A200ControlledLiveAcceptance.create(
        receipt_service=receipts,
        security_engine=Security(),
        backend=None,
        origin="a200-r6-controlled-live",
    )

    # Prove missing explicit approval is denied BEFORE target mutation.
    before = len(receipts.list_receipts())
    must_raise(
        "harness refuses missing human approval",
        LiveAcceptanceDenied,
        lambda: harness.run(human_approved=False),
    )
    add("missing approval created no receipt", len(receipts.list_receipts()) == before)

    # Resolve only the current R6 console before live mutation.
    target, pre_receipt_id = harness.resolve_self_window()
    add("self console resolved uniquely", target.hwnd > 0 and bool(target.title))
    add("resolved title contains R6 marker", SELF_WINDOW_MARKER.casefold() in target.title.casefold())
    add("preflight discovery owns canonical receipt", bool(pre_receipt_id))
    pre_receipt = receipts.get_receipt(pre_receipt_id)
    add("preflight discovery receipt succeeded", pre_receipt.status == "succeeded")

    plan = harness.build_exact_plan(target)
    add("live plan has exactly one step", len(plan.steps) == 1)
    add("live plan target exact HWND", int(plan.steps[0].params_schema["hwnd"]) == target.hwnd)
    add("live plan target exact observed title", str(plan.steps[0].params_schema["title"]) == target.title)
    add("live plan reversible", plan.steps[0].reversible is True)
    add("live plan has recovery hint", bool(plan.steps[0].recovery_hint))

    print("[INFO] Executing one controlled live minimize on the A200-R6 console.")
    print("[INFO] Automatic exact W132 restore will run immediately.")

    result = harness.run(human_approved=True)

    add("live mutation succeeded", result.mutation.status == "succeeded" and result.mutation.ok)
    add("live mutation canonical receipt", bool(result.mutation.receipt_id), result.mutation.receipt_id)
    mutation_receipt = receipts.get_receipt(result.mutation.receipt_id)
    add("live mutation receipt succeeded", mutation_receipt.status == "succeeded")
    add("live mutation receipt lifecycle", store.event_count(result.mutation.receipt_id) >= 3, store.event_count(result.mutation.receipt_id))

    token = result.mutation.recovery_token
    add("live mutation captured W132 recovery token", token is not None)
    add("recovery token binds exact plan digest", token.plan_digest == result.mutation.plan_digest)
    add("recovery token binds mutation receipt", token.mutation_receipt_id == result.mutation.receipt_id)

    add("automatic live restore succeeded", result.restore.status == "succeeded" and result.restore.ok)
    add("restore canonical receipt", bool(result.restore.receipt_id), result.restore.receipt_id)
    restore_receipt = receipts.get_receipt(result.restore.receipt_id)
    add("restore receipt succeeded", restore_receipt.status == "succeeded")
    add("restore receipt lifecycle", store.event_count(result.restore.receipt_id) >= 3, store.event_count(result.restore.receipt_id))

    add("exact console visible after restore", result.post_restore_visible is True)
    add("post-restore verification receipt", bool(result.verification_receipt_id))
    verify_receipt = receipts.get_receipt(result.verification_receipt_id)
    add("post-restore verification receipt succeeded", verify_receipt.status == "succeeded")

    # Do not log other window titles or process names.
    add("live target still self marker only", SELF_WINDOW_MARKER.casefold() in result.target.title.casefold())

src_path = ROOT / "runtime" / "aura_live_reversible_acceptance_v200.py"
src = src_path.read_text(encoding="utf-8-sig", errors="replace")
add("R6 source has no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
add("R6 source has no shell/native API", all(x not in src for x in ("os.system(", "os.popen(", "ctypes.", "win32", "WindowsPcControlAdapter(")))
add("R6 uses R5 mutation binding", "A200ReversibleMutationBinding" in src)
add("R6 uses R4 read-only binding", "A200ReadOnlyPcExecutionBinding" in src)
add("R6 live accepted capability excludes close", "pc.close_window" not in LIVE_ACCEPTED_CAPABILITY)
add("R6 live accepted capability excludes terminate", "pc.terminate_process" not in LIVE_ACCEPTED_CAPABILITY)

failed = [x for x in checks if not x[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
if failed:
    print("failed = " + ", ".join(x[0] for x in failed))
    raise SystemExit(1)
print("[PASS] A200-R6 controlled live reversible mutation + automatic restore invariant")
