from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

routes = [
    ("engineering foundation v088", ROOT / "tests" / "invariants" / "test_engineering_foundation_v088.py"),
    ("visual version surfaces", ROOT / "tests" / "invariants" / "test_product_version_surfaces_v0871.py"),
    ("spoken version surfaces", ROOT / "tests" / "invariants" / "test_spoken_product_version_v0872.py"),
    ("MissionEngine v0.8.8", ROOT / "tests" / "invariants" / "test_mission_engine_v088.py"),
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
