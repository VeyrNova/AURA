from __future__ import annotations
import os,re,unicodedata
from dataclasses import dataclass
from typing import Any
from runtime.workspace_context_v130 import WorkspaceContextError,WorkspaceContextServiceV130,WorkspaceRecord
from runtime.workspace_runtime_binding_v130 import WorkspaceRuntimeBindingV130

WORKSPACE_LIVE_BRIDGE_SCHEMA="aura.workspace.live-conversation-bridge.v1"

def _norm(value:Any)->str:
    raw=str(value or "").strip().lower()
    raw="".join(c for c in unicodedata.normalize("NFKD",raw) if not unicodedata.combining(c))
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9._+\-\s]"," ",raw)).strip()

def _service()->WorkspaceContextServiceV130:
    override=str(os.environ.get("AURA_WORKSPACE_STORAGE_ROOT") or "").strip()
    return WorkspaceContextServiceV130(storage_root=override or None)

@dataclass(frozen=True)
class WorkspaceConversationIntentReply:
    handled:bool
    text:str=""
    status:str="not_handled"
    capability_id:str|None=None
    clarification_required:bool=False
    payload:dict[str,Any]|None=None

def _available_rows(service): return service.list_workspaces(include_archived=False)

def _project_summary(record:WorkspaceRecord)->str:
    lines=[f"Le projet actif est {record.name}."]
    if record.last_action: lines.append(f"Dernière action : {record.last_action}.")
    if record.next_action: lines.append(f"Prochaine action : {record.next_action}.")
    if record.root_path: lines.append(f"Dossier : {record.root_path}.")
    lines.append(f"Artefacts liés : {len(record.artifacts)}.")
    return " ".join(lines)

def _project_payload(record:WorkspaceRecord)->dict[str,Any]:
    return {"schema":WORKSPACE_LIVE_BRIDGE_SCHEMA,"workspace_id":record.workspace_id,
            "name":record.name,"status":record.status,"root_path":record.root_path,
            "tags":list(record.tags),"last_action":record.last_action,
            "next_action":record.next_action,"artifact_count":len(record.artifacts),
            "updated_at":record.updated_at}

def _extract_activation_target(normalized:str)->str|None:
    for pattern in (
        r"^(?:aura\s+)?(?:reprends|reprend|ouvre|active|selectionne|passe sur|travaille sur)\s+(?:le\s+)?projet\s+(.+)$",
        r"^(?:aura\s+)?(?:reprends|reprend|ouvre|active|selectionne)\s+(.+?)\s+comme\s+projet(?:\s+actif)?$",
    ):
        m=re.match(pattern,normalized,flags=re.I)
        if m:
            target=str(m.group(1) or "").strip(" .,:;!?\"'")
            return target or None
    return None

def _find_project(service,target):
    needle=_norm(target); rows=_available_rows(service)
    exact=tuple(x for x in rows if needle in {_norm(x.workspace_id),_norm(x.name)})
    if len(exact)==1:return exact[0],exact
    if len(exact)>1:return None,exact
    prefix=tuple(x for x in rows if _norm(x.name).startswith(needle) or needle.startswith(_norm(x.name)))
    if len(prefix)==1:return prefix[0],prefix
    if len(prefix)>1:return None,prefix
    contains=tuple(x for x in rows if needle in _norm(x.name) or any(needle==_norm(t) for t in x.tags))
    if len(contains)==1:return contains[0],contains
    return None,contains

def dispatch_workspace_conversation_intent_v130(text:str)->WorkspaceConversationIntentReply:
    n=_norm(text)
    if not n:return WorkspaceConversationIntentReply(False)

    query_active=bool(re.search(r"\b(quel(?: est)?|c est quoi|sur quel|montre|affiche|donne)\b.*\bprojet actif\b",n)
                      or n in {"projet actif","quel projet est actif","quel est le projet actif",
                               "sur quel projet travaille aura","sur quel projet travailles tu",
                               "sur quel projet on travaille"})
    list_projects=bool(re.search(r"\b(liste|affiche|montre|quels sont|donne)\b.*\b(mes |les )?projets\b",n))
    resume_active=n in {"reprends le projet","reprend le projet","reprends le projet actif",
                        "reprend le projet actif","continue le projet","continue le projet actif",
                        "on reprend le projet","ou en est le projet actif"}

    # R1 FIX: resume-active commands must never become activation target "actif".
    target=None if resume_active else _extract_activation_target(n)

    if not (query_active or list_projects or resume_active or target):
        return WorkspaceConversationIntentReply(False)

    try:
        service=_service(); binding=WorkspaceRuntimeBindingV130(service=service)

        if list_projects:
            rows=_available_rows(service)
            if not rows:
                return WorkspaceConversationIntentReply(True,"Je n'ai encore aucun projet actif ou disponible dans le registre Workspace.",
                    "succeeded","workspace.list",payload={"schema":WORKSPACE_LIVE_BRIDGE_SCHEMA,"workspaces":[],"count":0})
            active=service.get_active_workspace(); lines=["Projets disponibles :"]; payload_rows=[]
            for row in rows:
                is_active=active is not None and row.workspace_id==active.workspace_id
                lines.append(f"- {row.name}"+(" — actif" if is_active else ""))
                item=_project_payload(row); item["active"]=is_active; payload_rows.append(item)
            return WorkspaceConversationIntentReply(True,"\n".join(lines),"succeeded","workspace.list",
                payload={"schema":WORKSPACE_LIVE_BRIDGE_SCHEMA,"workspaces":payload_rows,"count":len(payload_rows)})

        if resume_active:
            active=service.get_active_workspace()
            if active is None:
                return WorkspaceConversationIntentReply(True,"Aucun projet n'est actif pour le moment.","succeeded","workspace.resume",
                    payload={"schema":WORKSPACE_LIVE_BRIDGE_SCHEMA,"workspace":None})
            return WorkspaceConversationIntentReply(True,"Je reprends le contexte. "+_project_summary(active),
                "succeeded","workspace.resume",payload=_project_payload(active))

        if target:
            record,matches=_find_project(service,target)
            if record is None:
                if matches:
                    names=", ".join(x.name for x in matches[:6])
                    return WorkspaceConversationIntentReply(True,
                        f"Plusieurs projets correspondent à « {target} » : {names}. Précise lequel tu veux reprendre.",
                        "clarification_required","workspace.activate",True,
                        {"schema":WORKSPACE_LIVE_BRIDGE_SCHEMA,"matches":[_project_payload(x) for x in matches]})
                available=", ".join(x.name for x in _available_rows(service))
                suffix=f" Projets disponibles : {available}." if available else ""
                return WorkspaceConversationIntentReply(True,
                    f"Je ne trouve pas de projet correspondant à « {target} ».{suffix}",
                    "not_found","workspace.activate",payload={"schema":WORKSPACE_LIVE_BRIDGE_SCHEMA,"target":target})
            binding.activate(record.workspace_id); active=service.get_workspace(record.workspace_id)
            return WorkspaceConversationIntentReply(True,f"Projet {active.name} repris. "+_project_summary(active),
                "succeeded","workspace.activate",payload=_project_payload(active))

        active=service.get_active_workspace()
        if active is None:
            return WorkspaceConversationIntentReply(True,"Aucun projet n'est actif pour le moment.","succeeded","workspace.active",
                payload={"schema":WORKSPACE_LIVE_BRIDGE_SCHEMA,"workspace":None})
        return WorkspaceConversationIntentReply(True,_project_summary(active),"succeeded","workspace.active",
            payload=_project_payload(active))
    except WorkspaceContextError as exc:
        return WorkspaceConversationIntentReply(True,f"Le contexte Workspace est indisponible : {exc}",
            "failed","workspace.context",payload={"schema":WORKSPACE_LIVE_BRIDGE_SCHEMA,"error_type":type(exc).__name__})
