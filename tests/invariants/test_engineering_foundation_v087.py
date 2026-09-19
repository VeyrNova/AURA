from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE_VERSION = ROOT / "core" / "version.py"
CERT68 = ROOT / "AURA_V0_8_6_8_FINAL_CERTIFICATE.json"
SOURCE_BUILDER = ROOT / "tools" / "ui_source_build_v0865.py"
SOURCE_MANIFEST = ROOT / "ci" / "ui_source_manifest_v0865.json"
RUNTIME_PERF = ROOT / "tests" / "invariants" / "test_runtime_performance_v0867.py"
SEC_LEGACY = ROOT / "tests" / "invariants" / "test_security_fail_closed_v0861.py"
SEC_V2 = ROOT / "tests" / "invariants" / "test_security_policy_v2_v0866.py"
MEMORY_INV = ROOT / "tests" / "invariants" / "test_memorykernel_v2_v087.py"
MEMORY_MANIFEST = ROOT / "ci" / "memorykernel_v2_manifest_v087.json"
MANAGER = ROOT / "memory" / "manager.py"
KERNEL = ROOT / "memory" / "kernel_v2.py"
POLICY = ROOT / "security" / "policy_engine.py"
AURA_DB = ROOT / "database" / "aura.db"

EXPECTED_RECORDS = [
    "memory_id", "memory_type", "scope", "scope_id", "content",
    "provenance_json", "version", "created_at", "updated_at",
    "expires_at", "status", "merged_into_id", "is_sensitive",
]
EXPECTED_AUDIT = ["audit_id", "memory_id", "action", "at", "version", "detail_json"]

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

def cols(table):
    conn = sqlite3.connect(str(AURA_DB))
    try:
        return [r[1] for r in conn.execute("PRAGMA table_info(" + json.dumps(table) + ")").fetchall()]
    finally:
        conn.close()

version_src = CORE_VERSION.read_text(encoding="utf-8-sig", errors="replace")
m = re.search(r'(?m)^\s*AURA_VERSION\s*=\s*["\']([^"\']+)["\']', version_src)
add("canonical product version 0.8.7", bool(m) and m.group(1) == "0.8.7", m.group(1) if m else "missing")

cert68 = json.loads(CERT68.read_text(encoding="utf-8-sig"))
add("v0.8.6.8 golden foundation preserved", cert68.get("status") == "CERTIFIED" and cert68.get("foundation_status") == "ENGINEERING_FOUNDATION_CERTIFIED_COMPLETE", cert68.get("foundation_status"))

add("source manifest present", SOURCE_MANIFEST.is_file(), SOURCE_MANIFEST)
builder = run(SOURCE_BUILDER, "--check")
add("source-driven UI builder", builder.returncode == 0, "exit=" + str(builder.returncode))

runtime_perf = run(RUNTIME_PERF)
add("runtime performance invariant", runtime_perf.returncode == 0, "exit=" + str(runtime_perf.returncode))

sec_legacy = run(SEC_LEGACY)
add("legacy security fail-closed", sec_legacy.returncode == 0, "exit=" + str(sec_legacy.returncode))

sec_v2 = run(SEC_V2)
add("SecurityPolicyEngine v2 fail-closed", sec_v2.returncode == 0, "exit=" + str(sec_v2.returncode))

memory = run(MEMORY_INV)
add("MemoryKernel v2 lifecycle", memory.returncode == 0, "exit=" + str(memory.returncode))

add("MemoryKernel v2 manifest present", MEMORY_MANIFEST.is_file(), MEMORY_MANIFEST)

manager_src = MANAGER.read_text(encoding="utf-8-sig", errors="replace")
kernel_src = KERNEL.read_text(encoding="utf-8-sig", errors="replace")
policy_src = POLICY.read_text(encoding="utf-8-sig", errors="replace")

add("MemoryManager v2 facade", "# AURA v0.8.7 - MemoryKernel v2 compatibility facade" in manager_src, "facade")
add("MemoryKernel v2 authority", "# AURA v0.8.7 - MemoryKernel v2 canonical implementation" in kernel_src, "kernel")
add("router user_confirmed compatibility", "# AURA v0.8.7 - router user_confirmed compatibility" in policy_src, "security-compat")
add("MemoryKernel records schema", cols("memory_kernel_v2_records") == EXPECTED_RECORDS, cols("memory_kernel_v2_records"))
add("MemoryKernel audit schema", cols("memory_kernel_v2_audit") == EXPECTED_AUDIT, cols("memory_kernel_v2_audit"))

manifest = json.loads(MEMORY_MANIFEST.read_text(encoding="utf-8-sig"))
add("five memory types frozen", manifest.get("memory_types") == ["working", "episodic", "semantic", "preference", "project"], manifest.get("memory_types"))
add("three memory scopes frozen", manifest.get("scopes") == ["session", "user", "project"], manifest.get("scopes"))
add("legacy rows migration policy preserved", (manifest.get("persistence") or {}).get("legacy_tables_rewritten") is False, manifest.get("persistence"))
add("security fail-closed compatibility frozen", (manifest.get("security") or {}).get("router_user_confirmed_compatibility") is True, manifest.get("security"))

passed = sum(1 for _, ok, _ in checks if ok)
for name, ok, detail in checks:
    print(("[PASS] " if ok else "[FAIL] ") + name + " - " + detail)
print("PASS GLOBAL" if passed == len(checks) else "FAIL GLOBAL")
raise SystemExit(0 if passed == len(checks) else 2)
