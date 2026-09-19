from __future__ import annotations
import os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from runtime.workspace_context_v130 import WorkspaceContextServiceV130
from runtime.workspace_live_conversation_bridge_v130 import dispatch_workspace_conversation_intent_v130
from runtime.personal_integrations import IntegrationRuntimeReply,PersonalIntegrationDispatcher

with tempfile.TemporaryDirectory(prefix="aura_w130d_r1_") as td:
    td=Path(td); os.environ["AURA_WORKSPACE_STORAGE_ROOT"]=str(td/"store")
    svc=WorkspaceContextServiceV130(storage_root=td/"store")
    a=svc.create_workspace("AURA v2.0",workspace_id="ws_aura",root_path=td/"AURA",tags=("aura","development"))
    svc.update_workspace(a.workspace_id,last_action="W130-C certified",next_action="W130-D live Conversation bridge")
    svc.add_artifact(a.workspace_id,td/"AURA"/"roadmap.html",kind="roadmap",label="Master Roadmap")
    svc.create_workspace("Neural Echo",workspace_id="ws_neural_echo",root_path=td/"Neural Echo",tags=("music",),activate=False)

    assert dispatch_workspace_conversation_intent_v130("Quel projet est actif ?").capability_id=="workspace.active"
    assert dispatch_workspace_conversation_intent_v130("Affiche mes projets").payload["count"]==2
    assert dispatch_workspace_conversation_intent_v130("Aura, affiche mes contacts").handled is False
    switched=dispatch_workspace_conversation_intent_v130("Aura, reprends le projet Neural Echo")
    assert switched.capability_id=="workspace.activate" and svc.get_active_workspace().workspace_id=="ws_neural_echo"
    resumed=dispatch_workspace_conversation_intent_v130("reprends le projet actif")
    assert resumed.handled and resumed.status=="succeeded" and resumed.capability_id=="workspace.resume"
    assert "Neural Echo" in resumed.text
    assert dispatch_workspace_conversation_intent_v130("continue le projet actif").capability_id=="workspace.resume"

    class Broker: pending=None
    dispatcher=object.__new__(PersonalIntegrationDispatcher); dispatcher.confirmation_broker=Broker()
    fallback=[]
    dispatcher.dispatch_integration=lambda text:(fallback.append(text) or IntegrationRuntimeReply(handled=False))
    live=dispatcher.handle_text("reprends le projet actif")
    assert live.handled and live.status=="succeeded" and live.capability_id=="workspace.resume" and fallback==[]
    fall=dispatcher.handle_text("Aura, affiche mes contacts")
    assert fall.handled is False and fallback==["Aura, affiche mes contacts"]
    dispatcher.confirmation_broker.pending=object()
    dispatcher.dispatch_integration=lambda text:IntegrationRuntimeReply(handled=True,text="CONFIRMATION PRIORITAIRE",status="waiting_confirmation")
    pending=dispatcher.handle_text("Quel projet est actif ?")
    assert pending.text=="CONFIRMATION PRIORITAIRE" and pending.status=="waiting_confirmation"
    core=(ROOT/"core"/"aura_core.py").read_text(encoding="utf-8-sig",errors="replace")
    assert "_personal_integration_dispatcher" in core and ".handle_text(" in core
    del os.environ["AURA_WORKSPACE_STORAGE_ROOT"]

print("[PASS] active/list/switch workspace intents")
print("[PASS] resume-active precedence fixed")
print("[PASS] production dispatcher workspace resume")
print("[PASS] unrelated Personal Integrations fall through")
print("[PASS] pending integration confirmation priority")
print("[PASS] AuraCore dispatcher consumption preserved")
