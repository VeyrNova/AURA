from __future__ import annotations
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "ci" / "architecture_gate_v0864.py"
MANIFEST = ROOT / "ci" / "ui_source_manifest_v0865.json"
BUILDER = ROOT / "tools" / "ui_source_build_v0865.py"
REPORT = ROOT / "ci" / "reports" / "architecture_gate_v0865.json"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

checks = []
def add(name, ok, detail=""):
    checks.append({"name": name, "pass": bool(ok), "detail": str(detail)})

legacy = subprocess.run(
    [sys.executable, str(LEGACY)],
    cwd=ROOT,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
add("v0.8.6.4 architecture foundation", legacy.returncode == 0, "exit=" + str(legacy.returncode))

add("source manifest present", MANIFEST.is_file(), MANIFEST)
add("source builder present", BUILDER.is_file(), BUILDER)

if MANIFEST.is_file() and BUILDER.is_file():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    assets = manifest.get("assets") or []
    add("source manifest schema", manifest.get("schema") == "aura.ui-source-manifest.v0865.v1", manifest.get("schema"))
    add("source manifest exactly 8 assets", len(assets) == 8, len(assets))
    policy = manifest.get("policy") or {}
    add("dist declared generated output", policy.get("dist_is_generated_runtime_output") is True, policy.get("dist_is_generated_runtime_output"))
    add("manual dist patch forbidden", policy.get("manual_dist_patch_after_v0865_forbidden") is True, policy.get("manual_dist_patch_after_v0865_forbidden"))

    for item in assets:
        expected = str(item["sha256"]).lower()
        canonical = Path(item["canonical_source"])
        runtime = Path(item["runtime_dist"])
        add("canonical " + item["name"], canonical.is_file() and sha(canonical) == expected, sha(canonical) if canonical.is_file() else "missing")
        add("runtime " + item["name"], runtime.is_file() and sha(runtime) == expected, sha(runtime) if runtime.is_file() else "missing")
        for raw in item.get("source_mirrors", []):
            mirror = Path(raw)
            add("mirror " + item["name"] + " " + mirror.parent.name, mirror.is_file() and sha(mirror) == expected, sha(mirror) if mirror.is_file() else "missing")

    check = subprocess.run(
        [sys.executable, str(BUILDER), "--check"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    add("source builder check", check.returncode == 0, check.stdout.strip())

    stage_root = Path(tempfile.mkdtemp(prefix="aura_v0865_stage_", dir=str(ROOT / "ci" / "reports")))
    try:
        stage = subprocess.run(
            [sys.executable, str(BUILDER), "--stage", str(stage_root)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        add("source builder stage", stage.returncode == 0, stage.stdout.strip())
        if stage.returncode == 0:
            for item in assets:
                built = stage_root / "assets" / item["name"]
                add("staged " + item["name"], built.is_file() and sha(built) == str(item["sha256"]).lower(), sha(built) if built.is_file() else "missing")
    finally:
        shutil.rmtree(stage_root, ignore_errors=True)

passed = sum(1 for x in checks if x["pass"])
result = {
    "schema": "aura.ci.architecture-gate.v0865.v1",
    "pass": passed == len(checks),
    "checks_total": len(checks),
    "checks_passed": passed,
    "checks_failed": len(checks) - passed,
    "checks": checks,
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
for c in checks:
    print(("[PASS] " if c["pass"] else "[FAIL] ") + c["name"] + " - " + c["detail"])
print("PASS GLOBAL" if result["pass"] else "FAIL GLOBAL")
raise SystemExit(0 if result["pass"] else 2)
