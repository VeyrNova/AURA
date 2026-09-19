from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_roadmap_schedule_engine import build_default_engine

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"
doc = json.loads(ROADMAP.read_text(encoding="utf-8-sig"))
engine = build_default_engine(ROOT)

def get(mid):
    for m in doc["milestones"]:
        if m.get("id") == mid:
            return m
    raise AssertionError(mid)

def iso_dt(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

w131 = get("W131")
rm26 = get("RM26")
w131_done = str((w131.get("forecast") or {}).get("status") or "").lower() == "done"
w131_progress = float((w131.get("forecast") or {}).get("progress_percent") or 0)

current = engine._last_next(doc)
if w131_done or w131_progress >= 100:
    assert current["last_action"]["id"] == "W131", current
    assert current["next_action"]["id"] == "W132", current
    print("[PASS] current post-certification W131/W132 truth preserved")
else:
    assert current["last_action"]["id"] == "RM26", current
    assert current["next_action"]["id"] == "W131", current
    print("[PASS] current pre-certification RM26/W131 truth preserved")

rm_end = iso_dt((rm26.get("actual") or {}).get("end"))
later_dt = rm_end + timedelta(seconds=1)
earlier_dt = rm_end - timedelta(seconds=1)

later = copy.deepcopy(doc)
for m in later["milestones"]:
    if m.get("id") == "W131":
        m["forecast"]["status"] = "done"
        m["forecast"]["progress_percent"] = 100
        m["actual"]["start"] = later_dt.isoformat()
        m["actual"]["end"] = later_dt.isoformat()
        break
later_actions = engine._last_next(later)
assert later_actions["last_action"]["id"] == "W131", later_actions
assert later_actions["next_action"]["id"] == "W132", later_actions
print("[PASS] later W131 completion outranks RM26")

earlier = copy.deepcopy(doc)
for m in earlier["milestones"]:
    if m.get("id") == "W131":
        m["forecast"]["status"] = "done"
        m["forecast"]["progress_percent"] = 100
        m["actual"]["start"] = earlier_dt.isoformat()
        m["actual"]["end"] = earlier_dt.isoformat()
        break
earlier_actions = engine._last_next(earlier)
assert earlier_actions["last_action"]["id"] == "RM26", earlier_actions
assert earlier_actions["next_action"]["id"] == "W132", earlier_actions
print("[PASS] earlier W131 completion does not outrank RM26")
print("[PASS] next_action advances to W132 when W131 is done")
