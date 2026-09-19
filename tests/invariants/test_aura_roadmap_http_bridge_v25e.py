from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_roadmap_http_bridge_v25e import RoadmapHttpBridgeV25E

LIVE = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

live_sha = sha(LIVE)

with tempfile.TemporaryDirectory(prefix="aura_v25e_bridge_") as td:
    troot = Path(td)
    roadmap = troot / "data" / "roadmap" / "aura_master_roadmap_v2.json"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE, roadmap)

    ui = troot / "ui" / "dist"
    ui.mkdir(parents=True, exist_ok=True)
    snapshot = ui / "workspace_project_active_v130.json"
    snapshot.write_text(json.dumps({
        "schema": "aura.workspace.ui-contract.v1",
        "project_active": {
            "schema": "aura.workspace.ui.project-active-card.v1",
            "title": "PROJET ACTIF",
            "visible": True,
            "project_name": "AURA v2.0",
            "status": "active",
            "root_path": str(troot),
            "last_action": "",
            "next_action": "",
            "artifact_count": 0,
            "progress_percent": 0,
            "progress_label": "0%",
            "tags": [],
            "updated_at": "",
        }
    }), encoding="utf-8")
    os.environ["AURA_WORKSPACE_UI_ROOT"] = str(ui)

    bridge = RoadmapHttpBridgeV25E(root=troot)
    snap0 = bridge.snapshot()
    assert snap0["ok"] is True
    assert snap0["capabilities"]["baseline_mutation"] is False
    assert len(snap0["roadmap"]["milestones"]) >= 64

    bridge.mutate({
        "operation": "add_milestone",
        "milestone": {
            "id": "TEST-V25E",
            "phase": "Roadmap UI Test",
            "version": "test",
            "title": "Temporary mutation probe",
            "description": "temp",
            "weight": 0.25,
            "forecast": {
                "status": "planned",
                "progress_percent": 0,
                "start": "2026-09-10",
                "end": "2026-09-10",
            },
            "actual": {"start": None, "end": None},
        },
    })

    bridge.mutate({
        "operation": "update_milestone",
        "milestone_id": "TEST-V25E",
        "patch": {
            "title": "Updated mutation probe",
            "weight": 0.5,
            "forecast": {"status": "in_progress", "progress_percent": 35},
            "dependencies": ["RM25E"],
        },
    })

    bridge.mutate({
        "operation": "rename_phase",
        "old_phase": "Roadmap UI Test",
        "new_phase": "Roadmap UI Test Renamed",
    })

    bridge.mutate({
        "operation": "archive_milestone",
        "milestone_id": "TEST-V25E",
    })

    bridge.mutate({
        "operation": "restore_milestone",
        "milestone_id": "TEST-V25E",
        "status": "planned",
    })

    snap1 = bridge.snapshot()
    row = next(m for m in snap1["roadmap"]["milestones"] if m["id"] == "TEST-V25E")
    assert row["phase"] == "Roadmap UI Test Renamed"
    assert row["title"] == "Updated mutation probe"
    assert float(row["weight"]) == 0.5
    assert len(snap1["revisions"]) >= 5
    assert snapshot.is_file()

assert sha(LIVE) == live_sha
print("[PASS] V25-E1 roadmap HTTP bridge invariant")
print("[PASS] live roadmap unchanged by temporary invariant")
