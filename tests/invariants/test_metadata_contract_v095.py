from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from core.version import AURA_VERSION

BASELINE=ROOT/"ci"/"baseline_v095.json"
COLOR=ROOT/"ci"/"color_charter_lock_v095.json"

assert AURA_VERSION=="0.9.5"
assert BASELINE.is_file()
assert COLOR.is_file()

baseline=json.loads(BASELINE.read_text(encoding="utf-8-sig"))
color=json.loads(COLOR.read_text(encoding="utf-8-sig"))

assert baseline.get("schema")=="aura.ci.baseline.v095.v1"
assert baseline.get("milestone")=="Notifications"
assert baseline.get("version_contract",{}).get("product_version")=="0.9.5"
assert color.get("status")=="LOCKED"
assert color.get("version")=="0.9.5"

print("[PASS] AURA v0.9.5 metadata/version contract")
