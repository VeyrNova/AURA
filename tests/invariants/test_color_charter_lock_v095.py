from __future__ import annotations
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from core.version import AURA_VERSION

UI_ROOT=Path(os.environ.get("LOCALAPPDATA",""))/"AURA"/"ui"/"v0.7.2.2-rc4.2"
MAIN_CSS=UI_ROOT/"src"/"aura-p0702-left-rail.css"
P081_PROJECT=ROOT/"aura-p081-event-watchers.css"
P081_DIST=UI_ROOT/"dist"/"assets"/"aura-p081-event-watchers.css"
MANIFEST=ROOT/"ci"/"color_charter_lock_v095.json"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

assert AURA_VERSION=="0.9.5"
assert MANIFEST.is_file()
data=json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
assert data.get("status")=="LOCKED"
assert data.get("manual_visual_approval") is True
assert data.get("future_module_requirement",{}).get("must_inherit_current_palette") is True
assert sha(MAIN_CSS)=="2162fb9b4f39cd1b0113e2cd06d949fc19bff360251143ef438a37f3b44be4d5"
assert sha(P081_PROJECT)=="a76481dce897874f5b5912be7176f0655ec15bbe4351e8876bfa49ef7cc3b5d4"
assert sha(P081_DIST)=="a76481dce897874f5b5912be7176f0655ec15bbe4351e8876bfa49ef7cc3b5d4"

print("[PASS] AURA v0.9.5 Color Charter Lock")
print("[PASS] Existing palette authorities are byte-exact")
print("[PASS] Future modules must inherit the certified palette")
