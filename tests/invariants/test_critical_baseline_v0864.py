from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "ci" / "baseline_v0864.json"
REPORT = ROOT / "ci" / "reports" / "critical_baseline_v0864.json"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def resolve(raw):
    p = Path(raw)
    return p if p.is_absolute() else ROOT / p

baseline = json.loads(BASELINE.read_text(encoding="utf-8-sig"))
checks = []
for record in baseline.get("files", []):
    path = resolve(record["path"])
    expected = str(record["sha256"]).lower()
    exists = path.is_file()
    actual = sha(path) if exists else None
    checks.append({
        "path": str(path),
        "pass": exists and actual == expected,
        "expected": expected,
        "actual": actual,
    })

passed = sum(1 for c in checks if c["pass"])
failed = len(checks) - passed
result = {
    "schema": "aura.ci.critical-baseline.v0864.v1",
    "pass": failed == 0,
    "checks_total": len(checks),
    "checks_passed": passed,
    "checks_failed": failed,
    "checks": checks,
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
print("PASS GLOBAL" if result["pass"] else "FAIL GLOBAL")
raise SystemExit(0 if result["pass"] else 2)
