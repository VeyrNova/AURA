from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_final_global_audit_v200 import (
    A200_R25_MARKER,
    AUDIT_ONLY,
    CERTIFICATE_CREATION_ALLOWED,
    DEPLOYED_UI_MUTATION_ALLOWED,
    REAL_PC_MUTATION_ALLOWED,
    ROADMAP_SCHEDULE_MUTATION_ALLOWED,
    RUNTIME_AUTHORITY_MUTATION_ALLOWED,
    assert_r25_contract,
)
from runtime.aura_persistent_runtime_bootstrap_v200 import (
    A200PersistentRuntimeBootstrap,
)
from runtime.aura_supervised_runtime_ingress_v200 import (
    A200SupervisedRuntimeIngress,
)
from runtime.aura_ui_conversation_supervised_bridge_v200 import (
    A200UiConversationCommandBridge,
)

checks = []


def add(name, ok, detail=""):
    ok = bool(ok)
    checks.append((name, ok, str(detail)))
    print(
        ("[PASS] " if ok else "[FAIL] ")
        + name
        + (f" :: {detail}" if detail else ""),
        flush=True,
    )


add(
    "R25 marker",
    A200_R25_MARKER
    == "AURA_A200_R25_FINAL_GLOBAL_AUDIT_AURA_V2_CERTIFICATION_V1",
)
add("R25 audit-only", AUDIT_ONLY is True)
add("R25 real PC mutation disabled", REAL_PC_MUTATION_ALLOWED is False)
add("R25 runtime authority mutation disabled", RUNTIME_AUTHORITY_MUTATION_ALLOWED is False)
add("R25 deployed UI mutation disabled", DEPLOYED_UI_MUTATION_ALLOWED is False)
add("R25 roadmap schedule mutation disabled", ROADMAP_SCHEDULE_MUTATION_ALLOWED is False)
add("R25 certificate creation allowed", CERTIFICATE_CREATION_ALLOWED is True)
assert_r25_contract()
add("R25 contract assertion", True)

state_root = Path(tempfile.mkdtemp(prefix="aura_a200_r25_audit_"))
runtime = None

try:
    runtime = A200PersistentRuntimeBootstrap(
        state_root=state_root,
        backend=None,
        owner_id="r25-final-audit",
    )
    ingress = A200SupervisedRuntimeIngress(runtime=runtime)
    bridge = A200UiConversationCommandBridge(ingress=ingress)

    status = bridge.handle({"type": "runtime.status"}).to_dict()
    add("R25 runtime.status ok", status["ok"] is True)
    payload = status["payload"]
    add("R25 read-only lane ready", payload["read_only_ready"] is True)
    add("R25 mutation lane ready", payload["mutation_ready"] is True)
    add(
        "R25 pending approvals zero",
        len(payload["pending_approvals"]) == 0,
        len(payload["pending_approvals"]),
    )
    add(
        "R25 startup failures zero",
        len(payload["startup_failures"]) == 0,
        len(payload["startup_failures"]),
    )
    add(
        "R25 startup supervision-required zero",
        len(payload["startup_supervision_required"]) == 0,
        len(payload["startup_supervision_required"]),
    )

    before = len(runtime.receipts.list_receipts())
    read = bridge.handle(
        {"type": "pc.read_foreground"}
    ).to_dict()
    after = len(runtime.receipts.list_receipts())

    add("R25 real read-only foreground probe ok", read["ok"] is True)
    add("R25 foreground probe kind exact", read["kind"] == "pc.read_foreground")
    add(
        "R25 foreground probe creates exactly one receipt",
        after == before + 1,
        f"{before}->{after}",
    )
    receipt_id = str((read.get("payload") or {}).get("receipt_id") or "")
    add("R25 foreground receipt id present", bool(receipt_id), receipt_id)
    if receipt_id:
        add(
            "R25 foreground receipt succeeded",
            runtime.receipts.get_receipt(receipt_id).status == "succeeded",
        )

    add(
        "R25 no pending crash recovery",
        runtime.crash_journal.count(state="armed") == 0,
    )
    add(
        "R25 no running idempotency intents",
        runtime.intent_ledger.count(state="running") == 0,
    )

finally:
    if runtime is not None:
        runtime.close()
    shutil.rmtree(state_root, ignore_errors=True)

src = (
    ROOT / "runtime" / "aura_final_global_audit_v200.py"
).read_text(encoding="utf-8-sig", errors="replace")
add("R25 audit source contains no subprocess", "import subprocess" not in src and "from subprocess" not in src)
add(
    "R25 audit source contains no PC mutation capability",
    all(
        token not in src
        for token in (
            "pc.minimize_window",
            "pc.maximize_window",
            "pc.focus_window",
            "pc.close_window",
            "pc.terminate_process",
        )
    ),
)

failed = [item for item in checks if not item[1]]
print()
print(f"checks_passed = {len(checks)-len(failed)}/{len(checks)}")
print("R25_REAL_PC_OR_WINDOW_MUTATED = False")
if failed:
    print("failed = " + ", ".join(item[0] for item in failed))
    raise SystemExit(1)
print("[PASS] A200-R25 read-only runtime final audit probe")
