from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from runtime.workspace_context_v130 import (
    WORKSPACE_SCHEMA,
    WorkspaceContextServiceV130,
    WorkspaceValidationError,
)

with tempfile.TemporaryDirectory(prefix="aura_v130_workspace_") as td:
    root=Path(td)/"store"
    svc=WorkspaceContextServiceV130(storage_root=root)

    assert svc.snapshot()["workspace_count"]==0
    assert svc.get_active_workspace() is None

    a=svc.create_workspace(
        "AURA v2.0",
        root_path=Path(td)/"AURA",
        tags=("aura","dev","aura"),
        metadata={"confidential":True,"progress":72},
        workspace_id="ws_aura_v2",
    )
    assert a.workspace_id=="ws_aura_v2"
    assert a.tags==("aura","dev")
    assert svc.get_active_workspace().workspace_id=="ws_aura_v2"

    b=svc.create_workspace(
        "Neural Echo",
        root_path=Path(td)/"Neural Echo",
        tags=("music",),
        activate=False,
        workspace_id="ws_neural_echo",
    )
    assert len(svc.list_workspaces())==2
    assert svc.get_active_workspace().workspace_id=="ws_aura_v2"

    art1=svc.add_artifact(
        "ws_aura_v2",
        Path(td)/"AURA"/"roadmap.html",
        kind="roadmap",
        label="Master Roadmap",
        metadata={"source":"user"},
    )
    art2=svc.add_artifact(
        "ws_aura_v2",
        Path(td)/"AURA"/"roadmap.html",
        kind="roadmap",
        label="Master Roadmap v2",
        metadata={"certified":True},
    )
    assert art1.artifact_id==art2.artifact_id
    rec=svc.get_workspace("ws_aura_v2")
    assert len(rec.artifacts)==1
    assert rec.artifacts[0].label=="Master Roadmap v2"
    assert rec.artifacts[0].metadata["source"]=="user"
    assert rec.artifacts[0].metadata["certified"] is True

    svc.update_workspace(
        "ws_aura_v2",
        last_action="Certification AURA 1.2.3",
        next_action="W130-B runtime binding",
        notes="Workspace foundation active.",
        metadata_patch={"canonical_version":"1.2.3"},
    )
    svc.record_activity(
        "ws_aura_v2",
        "workspace.foundation.created",
        detail="W130-A",
        result="PASS",
    )

    # Fresh service instance must recover persistent state.
    fresh=WorkspaceContextServiceV130(storage_root=root)
    active=fresh.get_active_workspace()
    assert active is not None
    assert active.workspace_id=="ws_aura_v2"
    assert active.last_action=="Certification AURA 1.2.3"
    assert active.next_action=="W130-B runtime binding"
    assert active.metadata["canonical_version"]=="1.2.3"
    assert len(active.activity)==1

    resumed=fresh.resume_workspace()
    assert resumed["name"]=="AURA v2.0"
    assert resumed["artifacts"][0]["artifact_id"]==art1.artifact_id
    assert resumed["recent_activity"][0]["result"]=="PASS"

    fresh.set_active_workspace("ws_neural_echo")
    assert fresh.get_active_workspace().workspace_id=="ws_neural_echo"
    fresh.update_workspace("ws_neural_echo",status="archived")
    assert fresh.get_active_workspace() is None
    assert len(fresh.list_workspaces())==1
    assert len(fresh.list_workspaces(include_archived=True))==2

    try:
        fresh.set_active_workspace("ws_neural_echo")
    except WorkspaceValidationError:
        pass
    else:
        raise AssertionError("archived workspace became active")

    raw=json.loads((root/"workspace_registry.json").read_text(encoding="utf-8"))
    assert raw["schema"]==WORKSPACE_SCHEMA
    assert "ws_aura_v2" in raw["workspaces"]

print("[PASS] workspace create/list/active persistence")
print("[PASS] artifact idempotency and metadata merge")
print("[PASS] resume state and activity persistence")
print("[PASS] archive guard and fresh-process recovery")
print("[PASS] deterministic local-only W130-A foundation")
