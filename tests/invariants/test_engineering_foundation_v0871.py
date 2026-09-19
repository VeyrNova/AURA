from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SURFACE = ROOT / "tests" / "invariants" / "test_product_version_surfaces_v0871.py"
MEMORY = ROOT / "tests" / "invariants" / "test_memorykernel_v2_v087.py"
SECURITY = ROOT / "tests" / "invariants" / "test_security_policy_v2_v0866.py"
RUNTIME_PERF = ROOT / "tests" / "invariants" / "test_runtime_performance_v0867.py"
SOURCE_BUILDER = ROOT / "tools" / "ui_source_build_v0865.py"
CERT87 = ROOT / "AURA_V0_8_7_FINAL_CERTIFICATE.json"

checks = []

def run(path, *args):
    return subprocess.run(
        [sys.executable, str(path), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

cert = json.loads(CERT87.read_text(encoding="utf-8-sig"))
checks.append(("v0.8.7 certified parent", cert.get("status") == "CERTIFIED"))

for name, path, args in [
    ("version surfaces", SURFACE, ()),
    ("MemoryKernel v2", MEMORY, ()),
    ("SecurityPolicyEngine v2", SECURITY, ()),
    ("runtime performance", RUNTIME_PERF, ()),
    ("source-driven UI", SOURCE_BUILDER, ("--check",)),
]:
    cp = run(path, *args)
    checks.append((name, cp.returncode == 0))

passed = sum(1 for _, ok in checks if ok)
for name, ok in checks:
    print(("[PASS] " if ok else "[FAIL] ") + name)
print("PASS GLOBAL" if passed == len(checks) else "FAIL GLOBAL")
raise SystemExit(0 if passed == len(checks) else 2)
