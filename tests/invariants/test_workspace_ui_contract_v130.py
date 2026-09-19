from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from runtime.workspace_context_v130 import WorkspaceContextServiceV130
from runtime.workspace_runtime_binding_v130 import WorkspaceRuntimeBindingV130
from runtime.workspace_ui_contract_v130 import (
    PROJECT_ACTIVE_CARD_SCHEMA,
    WORKSPACE_UI_SCHEMA,
    project_active_ui_card_v130,
    workspace_ui_snapshot_v130,
)

with tempfile.TemporaryDirectory(prefix="aura_w130e_contract_") as td:
    td=Path(td)
    svc=WorkspaceContextServiceV130(storage_root=td/"store")

    empty=project_active_ui_card_v130(service=svc)
    assert empty.schema==PROJECT_ACTIVE_CARD_SCHEMA
    assert empty.visible is False
    assert empty.title=="PROJET ACTIF"
    assert empty.progress_percent is None

    ws=svc.create_workspace(
        "AURA v2.0",
        workspace_id="ws_aura",
        root_path=td/"AURA",
        tags=("aura","development"),
        metadata={"progress_percent":72},
    )
    svc.update_workspace(
        ws.workspace_id,
        last_action="W130-D live bridge certified",
        next_action="W130-E real persistence acceptance",
    )
    svc.add_artifact(
        ws.workspace_id,
        td/"AURA"/"roadmap.html",
        kind="roadmap",
        label="AURA Master Roadmap",
    )

    binding=WorkspaceRuntimeBindingV130(service=svc)
    card=project_active_ui_card_v130(binding=binding)
    assert card.visible is True
    assert card.project_name=="AURA v2.0"
    assert card.progress_percent==72
    assert card.progress_label=="72%"
    assert card.last_action=="W130-D live bridge certified"
    assert card.next_action=="W130-E real persistence acceptance"
    assert card.artifact_count==1
    assert card.tags==("aura","development")

    snapshot=workspace_ui_snapshot_v130(binding=binding)
    assert snapshot["schema"]==WORKSPACE_UI_SCHEMA
    assert snapshot["active_workspace_id"]=="ws_aura"
    assert snapshot["project_active"]["title"]=="PROJET ACTIF"
    assert snapshot["project_active"]["progress_percent"]==72

    svc.update_workspace("ws_aura",metadata_patch={"progress_percent":"81%"})
    assert project_active_ui_card_v130(service=svc).progress_percent==81

    svc.update_workspace("ws_aura",metadata_patch={"progress_percent":220})
    assert project_active_ui_card_v130(service=svc).progress_percent==100

    svc.update_workspace("ws_aura",status="archived")
    hidden=project_active_ui_card_v130(service=svc)
    assert hidden.visible is False
    assert workspace_ui_snapshot_v130(service=svc)["active_workspace_id"] is None

print("[PASS] empty active-project UI contract")
print("[PASS] final UI project card fields")
print("[PASS] progress metadata normalization")
print("[PASS] archive hides Project Active card")
