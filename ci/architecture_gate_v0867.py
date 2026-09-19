from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_ARCH = ROOT / "ci" / "architecture_gate_v0866.py"
RUNTIME_PERF = ROOT / "tests" / "invariants" / "test_runtime_performance_v0867.py"
MANIFEST = ROOT / "ci" / "runtime_performance_manifest_v0867.json"
MIC = ROOT / "voice" / "microphone.py"
XTTS = ROOT / "voice" / "xtts_tts.py"
GUARDIAN = ROOT / "runtime" / "resource_guardian.py"

EXPECTED_GUARDIAN_HASH = "f8f3ee6a70e196423fed44545436407139bb9518efb1138f3f868a841c0b3df2"
MIC_MARKER = "# AURA v0.8.6.7 - stale microphone warning dedup"
XTTS_MARKER = "# AURA v0.8.6.7 - repeat XTTS warmup reuse"

checks = []

def add(name, ok, detail=""):
    checks.append((name, bool(ok), str(detail)))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

legacy = subprocess.run(
    [sys.executable, str(LEGACY_ARCH)],
    cwd=ROOT,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
add("v0.8.6.6 architecture foundation", legacy.returncode == 0, "exit=" + str(legacy.returncode))

perf = subprocess.run(
    [sys.executable, str(RUNTIME_PERF)],
    cwd=ROOT,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
add("runtime performance invariant", perf.returncode == 0, "exit=" + str(perf.returncode))

add("runtime performance manifest present", MANIFEST.is_file(), MANIFEST)
add("microphone marker active", MIC_MARKER in MIC.read_text(encoding="utf-8-sig", errors="replace"), MIC_MARKER)
add("XTTS repeat warmup marker active", XTTS_MARKER in XTTS.read_text(encoding="utf-8-sig", errors="replace"), XTTS_MARKER)
add("Resource Guardian unchanged", GUARDIAN.is_file() and sha(GUARDIAN) == EXPECTED_GUARDIAN_HASH, sha(GUARDIAN) if GUARDIAN.is_file() else "missing")

if MANIFEST.is_file():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    mic = manifest.get("microphone") or {}
    xtts = manifest.get("xtts") or {}
    add("manifest microphone fallback preserved", mic.get("existing_live_index_validation_preserved") is True and mic.get("existing_default_fallback_preserved") is True, mic)
    add("manifest XTTS first warmup preserved", xtts.get("first_warmup_preserves_original") is True, xtts)
    add("manifest XTTS repeat warmup reuse", xtts.get("repeat_warmup_reuses_resident_model") is True, xtts)
    add("manifest resource limits unchanged", xtts.get("resource_guardian_limits_changed") is False, xtts)
    add("manifest provider policy unchanged", xtts.get("provider_policy_changed") is False, xtts)

passed = sum(1 for _, ok, _ in checks if ok)
for name, ok, detail in checks:
    print(("[PASS] " if ok else "[FAIL] ") + name + " - " + detail)
print("PASS GLOBAL" if passed == len(checks) else "FAIL GLOBAL")
raise SystemExit(0 if passed == len(checks) else 2)
