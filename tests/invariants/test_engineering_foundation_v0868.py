from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE_VERSION = ROOT / "core" / "version.py"
SOURCE_MANIFEST = ROOT / "ci" / "ui_source_manifest_v0865.json"
SOURCE_BUILDER = ROOT / "tools" / "ui_source_build_v0865.py"
RUNTIME_PERF = ROOT / "tests" / "invariants" / "test_runtime_performance_v0867.py"
SEC_LEGACY = ROOT / "tests" / "invariants" / "test_security_fail_closed_v0861.py"
SEC_V2 = ROOT / "tests" / "invariants" / "test_security_policy_v2_v0866.py"
POLICY = ROOT / "security" / "policy_engine.py"
POLICY_V2 = ROOT / "security" / "policy_engine_v2.py"
PERF_MANIFEST = ROOT / "ci" / "runtime_performance_manifest_v0867.json"

CERTS = [
    ROOT / "AURA_V0_8_6_3_FINAL_CERTIFICATE.json",
    ROOT / "AURA_V0_8_6_4_FINAL_CERTIFICATE.json",
    ROOT / "AURA_V0_8_6_5_FINAL_CERTIFICATE.json",
    ROOT / "AURA_V0_8_6_6_FINAL_CERTIFICATE.json",
    ROOT / "AURA_V0_8_6_7_FINAL_CERTIFICATE.json",
]

checks = []

def add(name, ok, detail=""):
    checks.append((name, bool(ok), str(detail)))

def run(path, *args):
    return subprocess.run(
        [sys.executable, str(path), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

version_src = CORE_VERSION.read_text(encoding="utf-8-sig", errors="replace")
m = re.search(r'(?m)^\s*AURA_VERSION\s*=\s*["\']([^"\']+)["\']', version_src)
add("canonical product version 0.8.6.8", bool(m) and m.group(1) == "0.8.6.8", m.group(1) if m else "missing")

for cert in CERTS:
    ok = False
    detail = "missing"
    if cert.is_file():
        try:
            obj = json.loads(cert.read_text(encoding="utf-8-sig"))
            ok = obj.get("status") == "CERTIFIED" and obj.get("completion_percent") == 100
            detail = str(obj.get("version")) + " " + str(obj.get("status"))
        except Exception as exc:
            detail = repr(exc)
    add("historical certificate " + cert.name, ok, detail)

add("source manifest present", SOURCE_MANIFEST.is_file(), SOURCE_MANIFEST)
builder = run(SOURCE_BUILDER, "--check")
add("source-driven UI builder --check", builder.returncode == 0, "exit=" + str(builder.returncode))

runtime_perf = run(RUNTIME_PERF)
add("runtime performance invariant", runtime_perf.returncode == 0, "exit=" + str(runtime_perf.returncode))

sec_legacy = run(SEC_LEGACY)
add("legacy security fail-closed", sec_legacy.returncode == 0, "exit=" + str(sec_legacy.returncode))

sec_v2 = run(SEC_V2)
add("SecurityPolicyEngine v2 fail-closed", sec_v2.returncode == 0, "exit=" + str(sec_v2.returncode))

policy_src = POLICY.read_text(encoding="utf-8-sig", errors="replace")
policy_v2_src = POLICY_V2.read_text(encoding="utf-8-sig", errors="replace")
add("SecurityPolicyEngine v2 facade", "AURA v0.8.6.6 SecurityPolicyEngine v2 compatibility facade" in policy_src, "facade")
add("legacy policy alias", "_SecurityPolicyEngineV1 = SecurityPolicyEngine" in policy_src, "alias")
add("security decision vocabulary", all(x in policy_v2_src for x in ("ALLOW", "DENY", "REQUIRE_CONFIRMATION")), "vocabulary")
add("unknown action fail closed", "unknown_action_denied" in policy_v2_src, "unknown_action_denied")
add("evaluator exception fail closed", "evaluator_exception_denied" in policy_v2_src, "evaluator_exception_denied")

perf_manifest = json.loads(PERF_MANIFEST.read_text(encoding="utf-8-sig"))
mic = perf_manifest.get("microphone") or {}
xtts = perf_manifest.get("xtts") or {}
add("microphone live fallback preserved", mic.get("existing_live_index_validation_preserved") is True and mic.get("existing_default_fallback_preserved") is True, mic)
add("XTTS first warmup preserved", xtts.get("first_warmup_preserves_original") is True, xtts)
add("XTTS repeat warmup reuse", xtts.get("repeat_warmup_reuses_resident_model") is True, xtts)
add("Resource Guardian limits unchanged", xtts.get("resource_guardian_limits_changed") is False, xtts)
add("voice provider policy unchanged", xtts.get("provider_policy_changed") is False, xtts)

passed = sum(1 for _, ok, _ in checks if ok)
for name, ok, detail in checks:
    print(("[PASS] " if ok else "[FAIL] ") + name + " - " + detail)

print("PASS GLOBAL" if passed == len(checks) else "FAIL GLOBAL")
raise SystemExit(0 if passed == len(checks) else 2)
