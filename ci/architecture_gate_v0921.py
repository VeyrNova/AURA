from __future__ import annotations
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
routes = [
    ("engineering foundation v0921", ROOT / "tests" / "invariants" / "test_engineering_foundation_v0921.py"),
    ("runtime wiring v0.9.2.1", ROOT / "tests" / "invariants" / "test_runtime_wiring_v0921.py"),
    ("visible Mail/Calendar modules", ROOT / "tests" / "invariants" / "test_runtime_wiring_ui_v0921.py"),
    ("Calendar Provider reverified", ROOT / "tests" / "invariants" / "test_calendar_provider_v092.py"),
    ("Email Provider reverified", ROOT / "tests" / "invariants" / "test_email_provider_v091.py"),
    ("Integration Architecture reverified", ROOT / "tests" / "invariants" / "test_integration_architecture_v090.py"),
    ("Action Receipts reverified", ROOT / "tests" / "invariants" / "test_action_receipts_v089.py"),
    ("MissionEngine reverified", ROOT / "tests" / "invariants" / "test_mission_engine_v088.py"),
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
    checks.append((name, cp.returncode == 0))

passed = sum(1 for _, ok in checks if ok)
for name, ok in checks:
    print(("[PASS] " if ok else "[FAIL] ") + name)
print("PASS GLOBAL" if passed == len(checks) else "FAIL GLOBAL")
raise SystemExit(0 if passed == len(checks) else 2)
