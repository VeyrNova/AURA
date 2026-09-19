from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_ARCH = ROOT / "ci" / "architecture_gate_v0867.py"
FINAL_INVARIANT = ROOT / "tests" / "invariants" / "test_engineering_foundation_v0868.py"

checks = []

def add(name, ok, detail=""):
    checks.append((name, bool(ok), str(detail)))

legacy = subprocess.run(
    [sys.executable, str(LEGACY_ARCH)],
    cwd=ROOT,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
add("v0.8.6.7 architecture foundation", legacy.returncode == 0, "exit=" + str(legacy.returncode))

final = subprocess.run(
    [sys.executable, str(FINAL_INVARIANT)],
    cwd=ROOT,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
add("v0.8.6.8 engineering foundation invariant", final.returncode == 0, "exit=" + str(final.returncode))

passed = sum(1 for _, ok, _ in checks if ok)
for name, ok, detail in checks:
    print(("[PASS] " if ok else "[FAIL] ") + name + " - " + detail)
print("PASS GLOBAL" if passed == len(checks) else "FAIL GLOBAL")
raise SystemExit(0 if passed == len(checks) else 2)
