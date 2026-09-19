from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_roadmap_service import (
    RoadmapImmutableFieldError,
    RoadmapService,
)
LIVE = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"
EXPECTED = "c6d30d9b68b413266596b2d781e7e40681db55a013ccde697331f04a77179e1b"

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

assert LIVE.is_file()
assert sha(LIVE) == EXPECTED, (sha(LIVE), EXPECTED)

with tempfile.TemporaryDirectory(prefix="aura_roadmap_v25b_") as td:
    troot = Path(td)
    roadmap = troot / "data" / "roadmap" / "aura_master_roadmap_v2.json"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE, roadmap)

    svc = RoadmapService(root=troot)
    doc0 = svc.load()
    baseline0 = json.dumps(
        [(m["id"], m["baseline"]) for m in doc0["milestones"]],
        sort_keys=True,
        ensure_ascii=False,
    )
    count0 = len(doc0["milestones"])
    p0 = svc.calculate_progress(doc0)

    caps = svc.capability_snapshot()
    assert caps["baseline_dates_immutable"] is True
    assert caps["revision_before_every_mutation"] is True
    assert caps["soft_delete_default"] is True
    assert caps["project_active_binding"] is False

    svc.add_milestone({
        "id": "TEST-V25B",
        "phase": "Roadmap test",
        "version": "test",
        "title": "Temporary roadmap service probe",
        "description": "temp only",
        "weight": 0.5,
        "forecast": {
            "status": "planned",
            "progress_percent": 0,
            "start": "2026-09-10",
            "end": "2026-09-10"
        },
        "actual": {"start": None, "end": None},
    }, after_id="RM25B", actor="invariant", reason="probe add")

    doc1 = svc.load()
    assert len(doc1["milestones"]) == count0 + 1
    m = svc.get_milestone("TEST-V25B", doc1)
    assert m["baseline"]["start"] is None
    assert m["baseline"]["end"] is None

    svc.update_milestone(
        "TEST-V25B",
        {
            "title": "Updated probe",
            "weight": 0.75,
            "forecast": {"progress_percent": 40, "status": "in_progress"},
        },
        actor="invariant",
        reason="probe update",
    )
    doc2 = svc.load()
    m2 = svc.get_milestone("TEST-V25B", doc2)
    assert m2["title"] == "Updated probe"
    assert m2["weight"] == 0.75
    assert m2["forecast"]["progress_percent"] == 40

    try:
        svc.update_milestone(
            "TEST-V25B",
            {"baseline": {"end": "2099-01-01"}},
            actor="invariant",
            reason="must fail",
        )
        raise AssertionError("post-baseline milestone baseline mutation unexpectedly allowed")
    except RoadmapImmutableFieldError:
        pass

    # Original 2026-08-30 baseline remains protected too.
    original_baseline_id = next(
        m["id"] for m in doc2["milestones"]
        if m["id"] != "TEST-V25B"
        and m.get("baseline", {}).get("start") is not None
        and m.get("baseline", {}).get("end") is not None
    )
    try:
        svc.update_milestone(
            original_baseline_id,
            {"baseline": {"end": "2099-01-01"}},
            actor="invariant",
            reason="must also fail",
        )
        raise AssertionError("original baseline mutation unexpectedly allowed")
    except RoadmapImmutableFieldError:
        pass

    svc.move_milestone(
        "TEST-V25B", before_id="RM25C",
        actor="invariant", reason="probe move"
    )
    svc.archive_milestone(
        "TEST-V25B", actor="invariant", reason="probe archive"
    )
    doc3 = svc.load()
    assert svc.get_milestone("TEST-V25B", doc3)["lifecycle"]["archived"] is True

    svc.restore_milestone(
        "TEST-V25B", actor="invariant", reason="probe restore"
    )
    svc.delete_milestone_soft(
        "TEST-V25B", actor="invariant", reason="probe soft delete"
    )
    doc4 = svc.load()
    assert svc.get_milestone("TEST-V25B", doc4)["lifecycle"]["deleted"] is True

    revisions = svc.list_revisions()
    assert len(revisions) >= 6
    rid = revisions[0]["revision_id"]
    svc.restore_revision(rid, actor="invariant", reason="probe revision restore")

    doc5 = svc.load()
    baseline5 = json.dumps(
        [(m["id"], m["baseline"]) for m in doc5["milestones"] if m["id"] != "TEST-V25B"],
        sort_keys=True,
        ensure_ascii=False,
    )
    assert baseline5 == baseline0
    assert isinstance(doc5["project"]["current_progress_percent"], (int, float))
    assert svc.calculate_progress(doc5) >= 0

assert sha(LIVE) == EXPECTED
print("[PASS] V25-B Roadmap Core service invariant")
print(f"[PASS] live roadmap unchanged sha256={EXPECTED}")
