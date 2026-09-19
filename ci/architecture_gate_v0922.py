from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

routes = [
    (
        "engineering foundation v0922",
        ROOT / "tests" / "invariants" / "test_engineering_foundation_v0922.py",
    ),
    (
        "runtime wiring",
        ROOT / "tests" / "invariants" / "test_runtime_wiring_v0921.py",
    ),
    (
        "Mail Calendar controller wiring",
        ROOT / "tests" / "invariants" / "test_runtime_wiring_ui_v0921.py",
    ),
    (
        "Modules Agenda UI",
        ROOT / "tests" / "invariants" / "test_modules_agenda_ui_v0922.py",
    ),
    (
        "Calendar Provider",
        ROOT / "tests" / "invariants" / "test_calendar_provider_v092.py",
    ),
    (
        "Email Provider",
        ROOT / "tests" / "invariants" / "test_email_provider_v091.py",
    ),
    (
        "Integration Architecture",
        ROOT / "tests" / "invariants" / "test_integration_architecture_v090.py",
    ),
    (
        "Action Receipts",
        ROOT / "tests" / "invariants" / "test_action_receipts_v089.py",
    ),
    (
        "MissionEngine",
        ROOT / "tests" / "invariants" / "test_mission_engine_v088.py",
    ),
]

checks = []

for name, path in routes:
    cp = subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    checks.append(
        (name, cp.returncode == 0)
    )

passed = sum(
    1 for _, ok in checks
    if ok
)

for name, ok in checks:
    print(
        ("[PASS] " if ok else "[FAIL] ")
        + name
    )

print(
    "PASS GLOBAL"
    if passed == len(checks)
    else "FAIL GLOBAL"
)

raise SystemExit(
    0 if passed == len(checks)
    else 2
)
