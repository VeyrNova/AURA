from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "tests" / "invariants" / "test_engineering_foundation_v0871.py"
SURFACE = ROOT / "tests" / "invariants" / "test_product_version_surfaces_v0871.py"

checks = []
for name, path in [
    ("engineering foundation v0871", FOUNDATION),
    ("version surfaces v0871", SURFACE),
]:
    cp = subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    checks.append((name, cp.returncode == 0))

passed = sum(1 for _, ok in checks if ok)
for name, ok in checks:
    print(("[PASS] " if ok else "[FAIL] ") + name)
print("PASS GLOBAL" if passed == len(checks) else "FAIL GLOBAL")
raise SystemExit(0 if passed == len(checks) else 2)
