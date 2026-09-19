from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_patch_transaction_engine import propose_edits
from runtime.aura_roadmap_service import RoadmapService
from runtime.aura_roadmap_developer_certifier_rm26 import (
    RoadmapDeveloperCertificationError,
    certify_after_post_apply,
    reconcile_rollback,
)

LIVE = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


live_sha = sha(LIVE)
assert callable(getattr(RoadmapService, "update_milestone", None))
print("[INFO] RoadmapService.update_milestone", inspect.signature(RoadmapService.update_milestone))

with tempfile.TemporaryDirectory(prefix="aura_rm26_core_r2_") as td:
    troot = Path(td)
    roadmap = troot / "data" / "roadmap" / "aura_master_roadmap_v2.json"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE, roadmap)

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

    target = troot / "sample.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")

    plain = propose_edits(
        troot,
        [{"path": "sample.py", "new_text": "VALUE = 2\n"}],
        task="plain",
    )
    assert "metadata" not in plain

    proposal = propose_edits(
        troot,
        [{"path": "sample.py", "new_text": "VALUE = 2\n"}],
        task="Roadmap RM26 synthetic",
        metadata={
            "roadmap_auto_certify": True,
            "roadmap_milestone_id": "RM26",
            "roadmap_source": "synthetic-invariant",
        },
    )
    assert proposal["metadata"]["roadmap_milestone_id"] == "RM26"

    bad_receipt = {
        "transaction_id": proposal["transaction_id"],
        "base_transaction_receipt": {
            "applied": True,
            "rolled_back": False,
            "post_apply_tests": [],
        },
    }
    try:
        certify_after_post_apply(proposal, bad_receipt, root=troot)
    except RoadmapDeveloperCertificationError:
        pass
    else:
        raise AssertionError(
            "missing post-apply tests incorrectly certified Roadmap"
        )

    before = json.loads(roadmap.read_text(encoding="utf-8"))
    before_rm26 = copy.deepcopy(
        next(m for m in before["milestones"] if m["id"] == "RM26")
    )
    assert before_rm26["forecast"]["status"] == "planned"

    good_receipt = {
        "transaction_id": proposal["transaction_id"],
        "base_transaction_receipt": {
            "applied": True,
            "rolled_back": False,
            "post_apply_tests": [
                {"passed": True, "command": ["python", "-c", "pass"]}
            ],
        },
    }

    result = certify_after_post_apply(proposal, good_receipt, root=troot)
    assert result["status"] == "CERTIFIED"

    after = json.loads(roadmap.read_text(encoding="utf-8"))
    rm26 = next(m for m in after["milestones"] if m["id"] == "RM26")
    assert rm26["forecast"]["status"] == "done"
    assert float(rm26["forecast"]["progress_percent"]) == 100

    again = certify_after_post_apply(proposal, good_receipt, root=troot)
    assert again["status"] == "IDEMPOTENT"

    rb = reconcile_rollback(
        proposal,
        good_receipt,
        {"rolled_back": True},
        root=troot,
    )
    assert rb["status"] == "REVERTED"

    reverted = json.loads(roadmap.read_text(encoding="utf-8"))
    rm26_reverted = next(m for m in reverted["milestones"] if m["id"] == "RM26")
    assert rm26_reverted["forecast"] == before_rm26["forecast"]
    assert rm26_reverted.get("actual") == before_rm26.get("actual")

assert sha(LIVE) == live_sha
print("[PASS] RM26 R2 service API compatibility")
print("[PASS] metadata remains optional for legacy proposals")
print("[PASS] no certification without passed post-apply tests")
print("[PASS] successful post-apply certification")
print("[PASS] idempotent transaction + milestone certification")
print("[PASS] rollback reconciliation")
print("[PASS] live Roadmap unchanged")
