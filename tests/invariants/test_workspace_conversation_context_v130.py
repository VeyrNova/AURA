from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from runtime.workspace_context_v130 import WorkspaceContextServiceV130
from runtime.workspace_runtime_binding_v130 import WorkspaceRuntimeBindingV130
from runtime.workspace_conversation_context_v130 import (
    CONVERSATION_CONTEXT_SCHEMA,
    PROJECT_CONTEXT_BEGIN,
    WorkspaceConversationContextInjectorV130,
)

with tempfile.TemporaryDirectory(prefix="aura_w130c_") as td:
    td=Path(td)
    svc=WorkspaceContextServiceV130(storage_root=td/"store")
    binding=WorkspaceRuntimeBindingV130(service=svc)
    injector=WorkspaceConversationContextInjectorV130(binding=binding)

    # No active workspace -> no injection.
    base=[
        {"role":"system","content":"Tu es AURA."},
        {"role":"user","content":"On continue ?"},
    ]
    assert injector.inject_messages(base)==base
    assert injector.inject_prompt("On continue ?")=="On continue ?"
    assert injector.envelope().active is False

    ws=svc.create_workspace(
        "AURA v2.0",
        workspace_id="ws_aura",
        root_path=td/"AURA",
        tags=("aura","development"),
        metadata={"canonical_version":"1.2.3"},
    )
    svc.update_workspace(
        ws.workspace_id,
        last_action="W130-B runtime binding certified",
        next_action="W130-C Conversation context injection",
        notes="Continue from the active project context.",
    )
    svc.add_artifact(
        ws.workspace_id,
        td/"AURA"/"roadmap.html",
        kind="roadmap",
        label="AURA Master Roadmap",
    )

    env=injector.envelope()
    assert env.schema==CONVERSATION_CONTEXT_SCHEMA
    assert env.active is True
    assert env.workspace_id=="ws_aura"
    assert PROJECT_CONTEXT_BEGIN in env.context_block
    assert "AURA v2.0" in env.context_block
    assert "W130-B runtime binding certified" in env.context_block
    assert "W130-C Conversation context injection" in env.context_block

    injected=injector.inject_messages(base)
    assert len(injected)==3
    assert injected[0]["role"]=="system"
    assert injected[1]["role"]=="system"
    assert PROJECT_CONTEXT_BEGIN in injected[1]["content"]
    assert injected[2]["role"]=="user"

    # Calling twice must never duplicate project context.
    twice=injector.inject_messages(injected)
    assert len(twice)==3
    assert sum(PROJECT_CONTEXT_BEGIN in m["content"] for m in twice)==1

    prompt=injector.inject_prompt("Continue le codage.")
    assert prompt.count(PROJECT_CONTEXT_BEGIN)==1
    prompt2=injector.inject_prompt(prompt)
    assert prompt2.count(PROJECT_CONTEXT_BEGIN)==1
    assert prompt2.endswith("Continue le codage.")

    info=injector.explain_active_project()
    assert info["active"] is True
    assert info["workspace"]["name"]=="AURA v2.0"
    assert info["workspace"]["next_action"]=="W130-C Conversation context injection"
    assert info["workspace"]["artifact_count"]==1

    meta=injector.conversation_metadata()
    assert meta["active_project"] is True
    assert meta["workspace_id"]=="ws_aura"

    # Archive active workspace -> injection disappears cleanly.
    svc.update_workspace("ws_aura",status="archived")
    assert injector.envelope().active is False
    cleaned=injector.inject_messages(injected)
    assert sum(PROJECT_CONTEXT_BEGIN in m["content"] for m in cleaned)==0
    assert injector.inject_prompt(prompt)=="Continue le codage."

print("[PASS] no active project => no context injection")
print("[PASS] active project context injected before user message")
print("[PASS] message injection is idempotent")
print("[PASS] plain prompt injection is idempotent")
print("[PASS] active-project explanation payload")
print("[PASS] archived project context removed cleanly")
