from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)

CHECKS = [
    (
        "Critical Baseline v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_critical_baseline_v095.py")],
        1200,
    ),
    (
        "Architecture Gate v095",
        [str(PYTHON), str(ROOT / "ci" / "architecture_gate_v095.py")],
        1500,
    ),
    (
        "Metadata Contract v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_metadata_contract_v095.py")],
        600,
    ),
    (
        "Engineering Foundation v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_engineering_foundation_v095.py")],
        1800,
    ),
    (
        "Color Charter Lock v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_color_charter_lock_v095.py")],
        600,
    ),
    (
        "Notifications Provider v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_notifications_provider_v095.py")],
        600,
    ),
    (
        "Notifications Runtime Bridge v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_notifications_runtime_bridge_v095.py")],
        600,
    ),
    (
        "Notifications Modules UI v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_notifications_module_ui_v095.py")],
        600,
    ),
    (
        "Activity Center Structural Color v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_activity_center_structural_color_fix_v095.py")],
        600,
    ),
    (
        "Files Provider preserved_v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_files_provider_preserved_v095.py")],
        900,
    ),
    (
        "Documents Files UI preserved_v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_documents_files_module_ui_preserved_v095.py")],
        900,
    ),
    (
        "Contacts Provider preserved_v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_contacts_provider_preserved_v095.py")],
        600,
    ),
    (
        "Contacts UI preserved_v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_contacts_module_ui_preserved_v095.py")],
        600,
    ),
    (
        "Agenda UI preserved_v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_modules_agenda_ui_preserved_v095.py")],
        600,
    ),
    (
        "Workspace Color Harmonization preserved_v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_workspace_color_harmonization_preserved_v095.py")],
        600,
    ),
    (
        "SYSTEM LIVE de-dup preserved_v095",
        [str(PYTHON), str(ROOT / "tests" / "invariants" / "test_modules_system_live_dedup_preserved_v095.py")],
        600,
    ),
    (
        "Source-driven UI",
        [str(PYTHON), str(ROOT / "tools" / "ui_source_build_v0865.py"), "--check"],
        600,
    ),
]

results = []
failed = False

for label, command, timeout in CHECKS:
    try:
        cp = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        ok = cp.returncode == 0
        output = cp.stdout or ""
    except Exception as exc:
        ok = False
        output = repr(exc)
        cp = None

    results.append(
        {
            "name": label,
            "pass": ok,
            "exit": cp.returncode if cp is not None else None,
            "tail": "\n".join(output.splitlines()[-80:]),
        }
    )

    print(("[PASS] " if ok else "[FAIL] ") + label)

    if not ok:
        failed = True
        if output:
            print("\n".join(output.splitlines()[-80:]))

if failed:
    print(json.dumps({"checks": results}, indent=2, ensure_ascii=False))
    print("FAIL GLOBAL")
    raise SystemExit(2)

print(json.dumps(
    {
        "schema": "aura.fast-lane.v095-preservation.v2",
        "version": "0.9.5",
        "milestone": "Notifications",
        "checks_total": len(results),
        "checks_passed": len(results),
        "color_charter": "LOCKED",
    },
    indent=2,
    ensure_ascii=False,
))
print("PASS GLOBAL")
raise SystemExit(0)
