from __future__ import annotations

import copy
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

import runtime.aura_self_development_governance as governance
from runtime.aura_patch_transaction_engine import propose_edits, validate_in_staging
from runtime.aura_roadmap_developer_binding_rm26 import (
    roadmap_metadata_for_developer_task,
)

LIVE = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


live_sha = sha(LIVE)

with tempfile.TemporaryDirectory(prefix="aura_rm26_hook_") as td:
    troot = Path(td)

    roadmap = troot / "data" / "roadmap" / "aura_master_roadmap_v2.json"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE, roadmap)

    schedule_src = ROOT / "data" / "roadmap" / "aura_roadmap_schedule_state.json"
    schedule_dst = troot / "data" / "roadmap" / "aura_roadmap_schedule_state.json"
    if schedule_src.is_file():
        shutil.copy2(schedule_src, schedule_dst)

    ui = troot / "ui" / "dist"
    ui.mkdir(parents=True, exist_ok=True)
    (ui / "workspace_project_active_v130.json").write_text(json.dumps({
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
            "updated_at": ""
        }
    }), encoding="utf-8")
    os.environ["AURA_WORKSPACE_UI_ROOT"] = str(ui)

    # Metadata binding is explicit: arbitrary tasks do not attach Roadmap state.
    assert roadmap_metadata_for_developer_task(
        "Corrige docs/sample.txt", root=troot
    ) is None

    meta = roadmap_metadata_for_developer_task(
        "Implémente RM26 dans AURA Developer", root=troot
    )
    assert meta and meta["roadmap_auto_certify"] is True
    assert meta["roadmap_milestone_id"] == "RM26"

    docs = troot / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    target = docs / "sample.txt"
    target.write_text("VALUE=1\n", encoding="utf-8")

    proposal = propose_edits(
        troot,
        [{
            "path": "docs/sample.txt",
            "new_text": "VALUE=2\n",
            "reason": "RM26 synthetic production-hook acceptance",
        }],
        task="Implement RM26 synthetic hook",
        metadata=meta,
    )

    tests = [[
        sys.executable,
        "-c",
        "from pathlib import Path; assert Path('docs/sample.txt').read_text() == 'VALUE=2\\n'",
    ]]
    validation = validate_in_staging(proposal, tests)
    assert validation["passed"] is True

    assessment = governance.assess_proposal(proposal, troot)
    required = assessment["required_approvals"]

    # The test root has no real Developer Mode state; patch only the module-level
    # gate for this isolated invariant.
    governance.developer_mode_enabled = lambda _root: True

    kwargs = {
        "aura_root": troot,
        "approval_phrase": required[0],
        "post_test_commands": tests,
    }
    if len(required) >= 2:
        kwargs["critical_approval"] = required[1]
    if len(required) >= 3:
        kwargs["release_approval"] = required[2]
        kwargs["release_mode"] = True

    receipt = governance.apply_self_development(
        proposal,
        validation,
        **kwargs,
    )

    assert target.read_text(encoding="utf-8") == "VALUE=2\n"
    assert receipt["roadmap_certification"]["status"] == "CERTIFIED"
    assert receipt["proposal_metadata"]["roadmap_milestone_id"] == "RM26"

    after = json.loads(roadmap.read_text(encoding="utf-8"))
    rm26 = next(m for m in after["milestones"] if m["id"] == "RM26")
    assert rm26["forecast"]["status"] == "done"
    assert float(rm26["forecast"]["progress_percent"]) == 100

    rollback = governance.rollback_self_development(
        receipt,
        approval_phrase=receipt["rollback_phrase"],
    )
    assert rollback["rolled_back"] is True
    assert rollback["roadmap_reconciliation"]["status"] == "REVERTED"
    assert target.read_text(encoding="utf-8") == "VALUE=1\n"

    reverted = json.loads(roadmap.read_text(encoding="utf-8"))
    rm26_reverted = next(
        m for m in reverted["milestones"] if m["id"] == "RM26"
    )
    assert rm26_reverted["forecast"]["status"] == "planned"

assert sha(LIVE) == live_sha
print("[PASS] RM26-2 explicit Developer task metadata binding")
print("[PASS] RM26-2 production apply hook certifies only after post-apply PASS")
print("[PASS] RM26-2 source rollback reconciles Roadmap")
print("[PASS] RM26-2 live Roadmap unchanged by isolated acceptance")
