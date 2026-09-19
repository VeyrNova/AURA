from __future__ import annotations
import hashlib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "ci" / "baseline_v092.json"
REPORT = ROOT / "ci" / "reports" / "critical_baseline_v092.json"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
baseline = json.loads(BASELINE.read_text(encoding="utf-8-sig"))
checks=[]
for rec in baseline.get("files",[]):
    p=Path(rec["path"])
    if not p.is_absolute(): p=ROOT/p
    exists=p.is_file(); actual=sha(p) if exists else None; expected=str(rec["sha256"]).lower()
    checks.append({"path":str(p),"pass":exists and actual==expected,"expected":expected,"actual":actual})
passed=sum(1 for x in checks if x["pass"])
result={"schema":"aura.ci.critical-baseline.v092.v1","pass":passed==len(checks),"checks_total":len(checks),"checks_passed":passed,"checks_failed":len(checks)-passed,"checks":checks}
REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2)); print("PASS GLOBAL" if result["pass"] else "FAIL GLOBAL")
raise SystemExit(0 if result["pass"] else 2)
