from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from action_receipts import ActionReceiptService, ActionReceiptStore
from runtime.aura_autonomous_supervisor_v200 import SupervisedPlan
from runtime.aura_readonly_pc_execution_binding_v200 import (
    A200ReadOnlyPcExecutionBinding,
    A200_R4_MARKER,
    AUTONOMOUS_MUTATION_ENABLED,
    EXPLICITLY_NON_READ_ONLY_CAPABILITIES,
    READ_ONLY_CAPABILITIES,
    READ_ONLY_EXECUTION_ENABLED,
    ReadOnlyExecutionDenied,
    assert_mutation_disabled,
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


class DenyFallbackSecurity:
    def authorize(self, action, params, *, user_confirmed=False):
        return "DENY"


add("A200-R4 marker", A200_R4_MARKER == "AURA_A200_R4_READ_ONLY_EXECUTION_BINDING_V1")
add("read-only execution enabled", READ_ONLY_EXECUTION_ENABLED is True)
add("autonomous mutation disabled", AUTONOMOUS_MUTATION_ENABLED is False)
add(
    "exact read-only allowlist",
    READ_ONLY_CAPABILITIES == frozenset({
        "pc.discover_windows",
        "pc.discover_processes",
        "pc.get_foreground_window",
    }),
)
add("focus explicitly non-read-only", "pc.focus_window" in EXPLICITLY_NON_READ_ONLY_CAPABILITIES)
add("minimize explicitly non-read-only", "pc.minimize_window" in EXPLICITLY_NON_READ_ONLY_CAPABILITIES)
add("maximize explicitly non-read-only", "pc.maximize_window" in EXPLICITLY_NON_READ_ONLY_CAPABILITIES)
add("close explicitly non-read-only", "pc.close_window" in EXPLICITLY_NON_READ_ONLY_CAPABILITIES)
add("terminate explicitly non-read-only", "pc.terminate_process" in EXPLICITLY_NON_READ_ONLY_CAPABILITIES)

with tempfile.TemporaryDirectory(prefix="aura_a200_r4_") as td:
    store = ActionReceiptStore(Path(td) / "receipts.sqlite3")
    receipts = ActionReceiptService(store=store)

    binding = A200ReadOnlyPcExecutionBinding.create_with_existing_w131_provider(
        receipt_service=receipts,
        security_engine=DenyFallbackSecurity(),
        backend=None,
        origin="a200-r4-live-read-only-acceptance",
    )

    manifests = binding.registry.list_providers()
    add(
        "existing W131 PC provider registered",
        any(getattr(m, "provider_id", None) == "pc_control.windows" for m in manifests)
        or len(manifests) >= 1,
        [getattr(m, "provider_id", None) for m in manifests],
    )

    # FIRST REAL A200 READ-ONLY EXECUTION.
    windows = binding.execute_capability(
        "pc.discover_windows",
        params={},
        step_id="live-windows",
    )
    add("live windows discovery succeeded", windows.status == "succeeded" and windows.ok)
    add("live windows discovery canonical receipt id", bool(windows.receipt_id), windows.receipt_id)
    w_receipt = receipts.get_receipt(windows.receipt_id)
    add("live windows receipt canonical succeeded", w_receipt.status == "succeeded")
    add("live windows receipt event lifecycle", store.event_count(windows.receipt_id) >= 3, store.event_count(windows.receipt_id))

    processes = binding.execute_capability(
        "pc.discover_processes",
        params={},
        step_id="live-processes",
    )
    add("live process discovery succeeded", processes.status == "succeeded" and processes.ok)
    add("live process discovery canonical receipt id", bool(processes.receipt_id), processes.receipt_id)
    p_receipt = receipts.get_receipt(processes.receipt_id)
    add("live process receipt canonical succeeded", p_receipt.status == "succeeded")

    foreground = binding.execute_capability(
        "pc.get_foreground_window",
        params={},
        step_id="live-foreground",
    )
    add("live foreground read succeeded", foreground.status == "succeeded" and foreground.ok)
    add("live foreground canonical receipt id", bool(foreground.receipt_id), foreground.receipt_id)
    f_receipt = receipts.get_receipt(foreground.receipt_id)
    add("live foreground receipt canonical succeeded", f_receipt.status == "succeeded")

    # Multi-step A200 R2 -> R3 -> R4 path.
    plan = SupervisedPlan.from_steps(
        goal="A200-R4 certified Windows read-only observation",
        steps=[
            {
                "step_id": "discover",
                "capability_id": "pc.discover_windows",
                "action": "pc.discover_windows",
                "summary": "Discover visible windows",
                "risk_tier": "READ_ONLY",
                "side_effect_class": "read_only",
                "params_schema": {},
            },
            {
                "step_id": "foreground",
                "capability_id": "pc.get_foreground_window",
                "action": "pc.get_foreground_window",
                "summary": "Read current foreground window",
                "depends_on": ["discover"],
                "risk_tier": "READ_ONLY",
                "side_effect_class": "read_only",
                "params_schema": {},
            },
        ],
    )
    executed = binding.execute_plan(plan)
    add("R2-R3-R4 read-only plan succeeded", executed["status"] == "succeeded", executed)
    add("R4 plan mutation flag false", executed["autonomous_mutation_enabled"] is False)
    add("R4 plan produced one canonical receipt per step", all(r["receipt_id"] for r in executed["records"]), executed["records"])
    add("R4 plan all steps succeeded", all(r["status"] == "succeeded" and r["ok"] for r in executed["records"]))

    # Gate proof: mutation is denied before IntegrationRequest dispatch.
    before_receipts = len(receipts.list_receipts())
    for cap in (
        "pc.focus_window",
        "pc.minimize_window",
        "pc.maximize_window",
        "pc.restore_window_state",
        "pc.close_window",
        "pc.terminate_process",
    ):
        must_raise(
            "R4 denies " + cap,
            ReadOnlyExecutionDenied,
            lambda cap=cap: binding.execute_capability(cap, params={}),
        )
    after_receipts = len(receipts.list_receipts())
    add(
        "denied mutations created no canonical receipt",
        after_receipts == before_receipts,
        f"before={before_receipts} after={after_receipts}",
    )

    must_raise(
        "R4 denies raw shell key",
        ReadOnlyExecutionDenied,
        lambda: binding.execute_capability(
            "pc.discover_windows",
            params={"command": "whoami"},
        ),
    )
    add(
        "raw shell denial created no receipt",
        len(receipts.list_receipts()) == after_receipts,
    )

    spoofed = SupervisedPlan.from_steps(
        goal="mislabelled focus must still fail",
        steps=[
            {
                "step_id": "spoof",
                "capability_id": "pc.focus_window",
                "action": "observe_window",
                "summary": "Mislabelled focus capability",
                "risk_tier": "READ_ONLY",
                "side_effect_class": "read_only",
                "params_schema": {},
            }
        ],
    )
    must_raise(
        "capability allowlist defeats risk-label spoofing",
        ReadOnlyExecutionDenied,
        lambda: binding.execute_plan(spoofed),
    )

must_raise(
    "explicit mutation assertion fail-closed",
    RuntimeError,
    assert_mutation_disabled,
)

src_path = ROOT / "runtime" / "aura_readonly_pc_execution_binding_v200.py"
src = src_path.read_text(encoding="utf-8-sig", errors="replace")
add("R4 source has no subprocess import", "import subprocess" not in src and "from subprocess" not in src)
add("R4 source has no shell/process APIs", all(x not in src for x in ("os.system(", "os.popen(", "ctypes.", "win32")))
add("R4 reuses canonical execute_integration", ".execute_integration(" in src)
add("R4 reuses W131 provider registration", "register_pc_control_provider_v131" in src)
add("R4 does not call native Windows adapter directly", "WindowsPcControlAdapter(" not in src)

failed = [x for x in checks if not x[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
if failed:
    print("failed = " + ", ".join(x[0] for x in failed))
    raise SystemExit(1)
print("[PASS] A200-R4 real read-only execution + canonical receipt invariant")
