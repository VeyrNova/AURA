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

from runtime.aura_project_active_roadmap_binding_v25d import (
    project_active_overlay_v25d,
    sync_project_active_projection_v25d,
)
from runtime.aura_roadmap_service import RoadmapService

LIVE_ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

live_sha_before = sha(LIVE_ROADMAP)

base = {
    "schema": "aura.workspace.ui-contract.v1",
    "project_active": {
        "schema": "aura.workspace.ui.project-active-card.v1",
        "title": "PROJET ACTIF",
        "visible": True,
        "project_name": "AURA v2.0",
        "status": "active",
        "root_path": r"C:\AURA GPT version",
        "last_action": "stale",
        "next_action": "stale",
        "artifact_count": 1,
        "progress_percent": None,
        "progress_label": "—",
        "tags": ["aura", "development"],
        "updated_at": "stale"
    }
}

with tempfile.TemporaryDirectory(prefix="aura_v25d_") as td:
    troot = Path(td)
    road = troot / "data" / "roadmap" / "aura_master_roadmap_v2.json"
    road.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE_ROADMAP, road)

    svc = RoadmapService(root=troot)
    # Simulate V25-D being certified before projection.
    svc.set_status(
        "RM25D", "done", progress_percent=100,
        actor="v25d-invariant", reason="temporary V25-D certification"
    )

    ui = troot / "ui"
    ui.mkdir(parents=True, exist_ok=True)
    snap = ui / "workspace_project_active_v130.json"
    snap.write_text(json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8")

    result = sync_project_active_projection_v25d(
        root=troot,
        ui_root=ui,
        service=svc,
        as_of=date(2026, 9, 4),
        require_live_ui=False,
    )
    assert result["ok"] is True
    assert isinstance(result["progress_percent"], (int, float))
    assert result["last_action"].startswith("RM25D")
    assert result["next_action"].startswith("RM25E")
    assert result["baseline_finish"] == "2026-11-30"
    assert isinstance(result["schedule_variance_days"], int)
    assert result["confidence_percent"] >= 35

    payload = json.loads(snap.read_text(encoding="utf-8"))
    card = payload["project_active"]
    assert card["roadmap_live"] is True
    assert card["roadmap_binding_schema"] == "aura.project-active.roadmap-binding.v25d.v1"
    assert card["progress_label"].endswith("%")
    assert "JOURS" in card["schedule_label"] or card["schedule_label"] == "DANS LES TEMPS"

assert sha(LIVE_ROADMAP) == live_sha_before
print("[PASS] V25-D Project Active roadmap binding invariant")
print("[PASS] live roadmap unchanged by temporary binding invariant")
