from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "ci" / "baseline_v094.json"
REPORT = ROOT / "ci" / "reports" / "critical_baseline_v094.json"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

baseline = json.loads(BASELINE.read_text(encoding="utf-8-sig"))
checks = []
for record in baseline.get("files", []):
    path = Path(record["path"])
    if not path.is_absolute():
        path = ROOT / path
    exists = path.is_file()
    actual = sha(path) if exists else None
    expected = str(record["sha256"]).lower()
    checks.append({"path":str(path),"pass":exists and actual==expected,"expected":expected,"actual":actual})
passed = sum(1 for item in checks if item["pass"])
result = {"schema":"aura.ci.critical-baseline.v094.v1","pass":passed==len(checks),"checks_total":len(checks),"checks_passed":passed,"checks_failed":len(checks)-passed,"checks":checks}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
print("PASS GLOBAL" if result["pass"] else "FAIL GLOBAL")
raise SystemExit(0 if result["pass"] else 2)
