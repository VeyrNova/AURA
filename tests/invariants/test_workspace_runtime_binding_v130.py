from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from runtime.workspace_context_v130 import WorkspaceContextServiceV130
from runtime.workspace_runtime_binding_v130 import (
    RUNTIME_CONTEXT_SCHEMA,
    WorkspaceRuntimeBindingV130,
)

with tempfile.TemporaryDirectory(prefix="aura_w130b_") as td:
    td=Path(td)
    store=td/"store"
    svc=WorkspaceContextServiceV130(storage_root=store)

    ws=svc.create_workspace(
        "AURA v2.0",
        workspace_id="ws_aura",
        root_path=td/"AURA",
        tags=("aura","development"),
        metadata={"canonical_version":"1.2.3"},
    )
    svc.update_workspace(
        ws.workspace_id,
        last_action="W130-A certified",
        next_action="W130-B runtime binding",
        notes="Workspace persistence foundation is ready.",
    )
    svc.add_artifact(
        ws.workspace_id,
        td/"AURA"/"roadmap.html",
        kind="roadmap",
        label="AURA Master Roadmap",
    )

    binding=WorkspaceRuntimeBindingV130(service=svc)
    ctx=binding.require_active_context()
    assert ctx.schema==RUNTIME_CONTEXT_SCHEMA
    assert ctx.workspace_id=="ws_aura"
    assert ctx.name=="AURA v2.0"
    assert ctx.last_action=="W130-A certified"
    assert ctx.next_action=="W130-B runtime binding"
    assert ctx.artifact_count==1

    prompt=binding.prompt_context_block()
    assert "[AURA_ACTIVE_PROJECT]" in prompt
    assert "AURA v2.0" in prompt
    assert "W130-A certified" in prompt
    assert "W130-B runtime binding" in prompt
    assert "AURA Master Roadmap" in prompt

    binding.update_resume_state(
        last_action="W130-B active context loaded",
        next_action="W130-C Conversation binding",
        metadata_patch={"runtime_binding":"active"},
    )
    changed=binding.require_active_context()
    assert changed.last_action=="W130-B active context loaded"
    assert changed.next_action=="W130-C Conversation binding"
    assert changed.metadata["runtime_binding"]=="active"
    assert len(changed.recent_activity)>=1

    binding.bind_artifact(
        td/"AURA"/"workspace_notes.md",
        kind="notes",
        label="Workspace Notes",
        metadata={"source":"runtime"},
    )
    assert binding.require_active_context().artifact_count==2

    payload=binding.resume_payload()
    assert payload["resume"]["next_action"]=="W130-C Conversation binding"
    assert payload["resume"]["artifact_count"]==2

    # Fresh service + fresh binding must recover the active project automatically.
    fresh_svc=WorkspaceContextServiceV130(storage_root=store)
    fresh_binding=WorkspaceRuntimeBindingV130(service=fresh_svc)
    fresh=fresh_binding.require_active_context()
    assert fresh.workspace_id=="ws_aura"
    assert fresh.next_action=="W130-C Conversation binding"
    assert fresh.artifact_count==2
    assert fresh_binding.runtime_snapshot()["active"] is True

print("[PASS] active workspace -> runtime context")
print("[PASS] prompt context block is deterministic and structured")
print("[PASS] resume state updates persist")
print("[PASS] runtime artifact binding persists")
print("[PASS] fresh-process runtime recovery")
