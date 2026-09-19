from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "tests" / "invariants" / "test_engineering_foundation_v087.py"
MEMORY = ROOT / "tests" / "invariants" / "test_memorykernel_v2_v087.py"
SEC_V2 = ROOT / "tests" / "invariants" / "test_security_policy_v2_v0866.py"

checks = []

def run(path):
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

for name, path in [
    ("engineering foundation v087", FOUNDATION),
    ("MemoryKernel v2 lifecycle", MEMORY),
    ("SecurityPolicyEngine v2", SEC_V2),
]:
    cp = run(path)
    checks.append((name, cp.returncode == 0, "exit=" + str(cp.returncode)))

passed = sum(1 for _, ok, _ in checks if ok)
for name, ok, detail in checks:
    print(("[PASS] " if ok else "[FAIL] ") + name + " - " + detail)
print("PASS GLOBAL" if passed == len(checks) else "FAIL GLOBAL")
raise SystemExit(0 if passed == len(checks) else 2)
