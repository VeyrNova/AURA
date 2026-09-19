from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_roadmap_service import RoadmapService
from runtime.aura_roadmap_schedule_engine import RoadmapScheduleEngine

LIVE = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"
EXPECTED_LIVE_SHA = "c6d30d9b68b413266596b2d781e7e40681db55a013ccde697331f04a77179e1b"

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

assert LIVE.is_file()
assert sha(LIVE) == EXPECTED_LIVE_SHA

with tempfile.TemporaryDirectory(prefix="aura_schedule_v25c_") as td:
    troot = Path(td)
    roadmap = troot / "data" / "roadmap" / "aura_master_roadmap_v2.json"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE, roadmap)

    svc = RoadmapService(root=troot)
    svc.set_status(
        "RM25B", "done", progress_percent=100,
        actor="v25c-invariant", reason="simulate certified V25-B"
    )
    svc.update_milestone(
        "RM25C",
        {
            "forecast": {"status": "done", "progress_percent": 100},
            "actual": {"start": "2026-09-04", "end": "2026-09-04"},
            "reconciled_confidence": "certifié",
        },
        actor="v25c-invariant",
        reason="simulate certified V25-C",
    )

    engine = RoadmapScheduleEngine(root=troot, service=svc)
    caps = engine.capability_snapshot()
    assert caps["baseline_planned_progress"] is True
    assert caps["forecast_finish"] is True
    assert caps["project_schedule_variance_days"] is True
    assert caps["project_active_binding"] is False

    state = engine.compute(as_of=date(2026, 9, 4))
    assert state["schema"] == "aura.roadmap.schedule-state.v25c.v1"
    p = state["project"]
    assert p["project_start"] == "2026-08-02"
    assert p["baseline_finish"] == "2026-11-30"
    assert 0 <= p["planned_baseline_progress_percent"] <= 100
    assert 0 <= p["actual_baseline_progress_percent"] <= 100
    assert 0 <= p["actual_total_progress_percent"] <= 100
    assert isinstance(p["execution_variance_days"], int)
    assert isinstance(p["schedule_variance_days"], int)
    assert p["schedule_status"] in {"ahead", "on_track", "late"}
    assert 35 <= p["confidence_percent"] <= 95
    assert state["last_action"]["id"] == "RM25C"
    assert state["next_action"]["id"] == "RM25D"

    written = engine.write_state(as_of=date(2026, 9, 4))
    assert engine.state_path.is_file()
    reloaded = json.loads(engine.state_path.read_text(encoding="utf-8"))
    assert reloaded["project"]["forecast_finish"] == written["project"]["forecast_finish"]

assert sha(LIVE) == EXPECTED_LIVE_SHA
print("[PASS] V25-C Schedule Engine invariant")
print(f"[PASS] live roadmap unchanged during temp invariant sha256={EXPECTED_LIVE_SHA}")
