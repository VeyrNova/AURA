from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_ARCH = ROOT / "ci" / "architecture_gate_v0865.py"
LEGACY_SECURITY = ROOT / "tests" / "invariants" / "test_security_fail_closed_v0861.py"
V2_SECURITY = ROOT / "tests" / "invariants" / "test_security_policy_v2_v0866.py"
POLICY = ROOT / "security" / "policy_engine.py"
POLICY_V2 = ROOT / "security" / "policy_engine_v2.py"
COMMON = ROOT / "ci" / "common.py"

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
add("v0.8.6.5 architecture foundation", legacy.returncode == 0, "exit=" + str(legacy.returncode))

add("policy_engine.py present", POLICY.is_file(), POLICY)
add("policy_engine_v2.py present", POLICY_V2.is_file(), POLICY_V2)

if POLICY.is_file():
    src = POLICY.read_text(encoding="utf-8-sig", errors="replace")
    add("v2 compatibility facade marker", "AURA v0.8.6.6 SecurityPolicyEngine v2 compatibility facade" in src, "marker")
    add("legacy engine alias retained", "_SecurityPolicyEngineV1 = SecurityPolicyEngine" in src, "alias")

if POLICY_V2.is_file():
    src2 = POLICY_V2.read_text(encoding="utf-8-sig", errors="replace")
    add("normalized decision vocabulary", all(x in src2 for x in ("ALLOW", "DENY", "REQUIRE_CONFIRMATION")), "enum")
    add("unknown action fail closed", "unknown_action_denied" in src2, "unknown")
    add("exception fail closed", "evaluator_exception_denied" in src2, "exception")

common_src = COMMON.read_text(encoding="utf-8-sig", errors="replace")
add("legacy security invariant routed", "test_security_fail_closed_v0861.py" in common_src, "legacy")
add("v2 security invariant routed", "test_security_policy_v2_v0866.py" in common_src, "v2")

for name, path in (("legacy security invariant", LEGACY_SECURITY), ("v2 security invariant", V2_SECURITY)):
    cp = subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    add(name, cp.returncode == 0, "exit=" + str(cp.returncode))

probe = subprocess.run(
    [
        sys.executable,
        "-c",
        (
            "from security.policy_engine import SecurityPolicyEngine;"
            "assert getattr(SecurityPolicyEngine,'SECURITY_POLICY_VERSION',None)=='2';"
            "print('OK')"
        ),
    ],
    cwd=ROOT,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
add("public SecurityPolicyEngine authority v2", probe.returncode == 0, probe.stdout.strip())

passed = sum(1 for _, ok, _ in checks if ok)
for name, ok, detail in checks:
    print(("[PASS] " if ok else "[FAIL] ") + name + " - " + detail)
print("PASS GLOBAL" if passed == len(checks) else "FAIL GLOBAL")
raise SystemExit(0 if passed == len(checks) else 2)
