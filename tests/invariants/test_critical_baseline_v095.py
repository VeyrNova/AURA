from __future__ import annotations
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from core.version import AURA_VERSION

BASELINE=ROOT/"ci"/"baseline_v095.json"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def path_key(record):
    for key in ("path","file","relative_path","relpath"):
        if key in record:
            return key
    raise AssertionError("baseline path key missing")

def hash_key(record):
    for key in ("sha256","hash","digest"):
        if key in record:
            return key
    raise AssertionError("baseline hash key missing")

assert AURA_VERSION=="0.9.5"
assert BASELINE.is_file()

data=json.loads(BASELINE.read_text(encoding="utf-8-sig"))
assert data.get("schema")=="aura.ci.baseline.v095.v1"
assert data.get("milestone")=="Notifications"
records=data.get("files")
assert isinstance(records,list) and records

failures=[]
for record in records:
    pk=path_key(record)
    hk=hash_key(record)
    rel=str(record[pk]).replace("\\","/")
    path=ROOT/rel
    if not path.is_file():
        failures.append({"path":rel,"reason":"missing"})
        continue
    actual=sha(path)
    expected=str(record[hk])
    if actual!=expected:
        failures.append({"path":rel,"expected":expected,"actual":actual})

assert not failures, json.dumps(failures,indent=2)

print("[PASS] AURA v0.9.5 critical baseline")
print("[PASS] baseline_v095 exact")
