from __future__ import annotations
from dataclasses import asdict, is_dataclass
from typing import Any, Mapping
import re

# AURA_V123_PRESENTER_NESTED_PRIMITIVE_DEPTH_FIX
def _plain(v: Any, depth: int = 0) -> Any:
    if v is None or isinstance(v,(str,int,float,bool)): return v
    if depth > 5: return None
    if is_dataclass(v):
        try: return _plain(asdict(v), depth+1)
        except Exception: pass
    if isinstance(v, Mapping):
        return {str(k):_plain(x,depth+1) for k,x in v.items() if str(k).lower() not in {"access_token","refresh_token","client_secret","authorization","credentials","oauth_token"}}
    if isinstance(v,(list,tuple)): return [_plain(x,depth+1) for x in list(v)[:100]]
    if hasattr(v,"to_dict"):
        try: return _plain(v.to_dict(),depth+1)
        except Exception: pass
    if hasattr(v,"__dict__"):
        try: return _plain({k:x for k,x in vars(v).items() if not str(k).startswith("_")},depth+1)
        except Exception: pass
    return str(v)

def _kind(provider:str, capability:str)->str:
    s=f"{provider} {capability}".lower()
    if "email" in s or "mail" in s: return "mail"
    if "calendar" in s or "agenda" in s: return "calendar"
    if "contact" in s or "people" in s: return "contacts"
    if "task" in s or "todo" in s: return "tasks"
    if "file" in s or "drive" in s or "document" in s: return "drive"
    return "generic"

def _find_list(node:Any, keys:tuple[str,...])->list[Any]:
    wanted={k.lower() for k in keys}
    if isinstance(node,Mapping):
        for k,v in node.items():
            if str(k).lower() in wanted and isinstance(v,list): return v[:50]
        for v in node.values():
            r=_find_list(v,keys)
            if r:return r
    elif isinstance(node,list):
        for v in node:
            r=_find_list(v,keys)
            if r:return r
    return []


def _has_authoritative_list(node: Any, keys: tuple[str,...]) -> bool:
    wanted={k.lower() for k in keys}
    if isinstance(node,Mapping):
        for k,v in node.items():
            if str(k).lower() in wanted and isinstance(v,list):
                return True
        return any(_has_authoritative_list(v,keys) for v in node.values() if isinstance(v,(Mapping,list,tuple)))
    if isinstance(node,(list,tuple)):
        return any(_has_authoritative_list(v,keys) for v in node if isinstance(v,(Mapping,list,tuple)))
    return False


# AURA_V130_TASKS_FAILED_RECEIPT_TRUTH_BEGIN
def _failed_task_receipt_text_v130(value: Any) -> bool:
    text = " ".join(str(value or "").strip().casefold().split())
    if not text:
        return False
    return (
        text.startswith("action non executee")
        or text.startswith("action non exécutée")
        or text.startswith("recu d'action")
        or text.startswith("reçu d'action")
        or ("statut" in text and "failed" in text and "action" in text)
    )


def _is_failed_task_receipt_v130(item: Any) -> bool:
    if not isinstance(item, Mapping):
        return _failed_task_receipt_text_v130(item)
    status = str(item.get("status") or "").strip().casefold()
    values = [
        item.get("title"),
        item.get("summary"),
        item.get("content"),
        item.get("name"),
        item.get("subject"),
        item.get("text"),
        item.get("preview"),
        item.get("receipt"),
        item.get("receipt_id"),
    ]
    joined = " ".join(str(v or "") for v in values if v is not None)
    return status == "failed" or _failed_task_receipt_text_v130(joined)
# AURA_V130_TASKS_FAILED_RECEIPT_TRUTH_END


def _pick(d:Mapping[str,Any],*keys:str):
    low={str(k).lower():v for k,v in d.items()}
    for k in keys:
        if k.lower() in low and low[k.lower()] not in (None,"",[],{}): return low[k.lower()]
    return None

def _norm(kind:str,item:Any)->dict[str,Any]:
    item=_plain(item)
    if not isinstance(item,Mapping): return {"title":str(item)}
    if kind=="mail":
        return {"sender":_pick(item,"sender","from","from_name"),"subject":_pick(item,"subject","title"),"preview":_pick(item,"preview","snippet","summary","body_text"),"date_time":_pick(item,"date_time","date","received_at"),"read_state":_pick(item,"read_state","is_read","read","unread")}
    if kind=="calendar":
        return {"start_time":_pick(item,"start_time","start","time","date"),"title":_pick(item,"title","summary","name"),"duration":_pick(item,"duration","duration_minutes","end"),"location_or_meet":_pick(item,"location","meet","hangout_link"),"participants_optional":_pick(item,"participants","attendees")}
    if kind=="contacts":
        return {"name":_pick(item,"name","display_name","full_name"),"organization_role":_pick(item,"organization","company","job_title","role"),"email":_pick(item,"email","emails"),"phone":_pick(item,"phone","phones")}
    if kind=="tasks":
        return {
            "title":_pick(item,"title","name"),
            "due":_pick(item,"due","due_at","date"),
            "status":_pick(item,"status","state"),
            "notes":_pick(item,"notes","description","summary"),
            "completed":_pick(item,"completed","completed_at"),
            "task_id":_pick(item,"task_id","id"),
            "tasklist_id":_pick(item,"tasklist_id","list_id"),
            "updated":_pick(item,"updated","modified"),
        }
    if kind=="drive":
        return {"type_icon":_pick(item,"mime_type","type","kind","is_dir"),"name":_pick(item,"name","title","filename"),"location":_pick(item,"location","path","folder"),"modified":_pick(item,"modified","modified_time","date"),"size_optional":_pick(item,"size","size_bytes")}
    return dict(list(item.items())[:8])

def _fallback(kind:str,text:str)->list[dict[str,Any]]:
    lines=[x.strip(" \t•*-") for x in str(text or "").splitlines() if x.strip()]
    labels={"mail":{"de":"sender","from":"sender","objet":"subject","subject":"subject","aperçu":"preview","apercu":"preview","date":"date_time"},"calendar":{"heure":"start_time","début":"start_time","debut":"start_time","titre":"title","lieu":"location_or_meet","durée":"duration","duree":"duration"},"contacts":{"nom":"name","email":"email","téléphone":"phone","telephone":"phone","société":"organization_role","societe":"organization_role"},"drive":{"nom":"name","fichier":"name","dossier":"location","emplacement":"location","modifié":"modified","modifie":"modified","taille":"size_optional","type":"type_icon"}}.get(kind,{})
    out=[]; cur={}
    for line in lines:
        m=re.match(r"^([^:]{1,30})\s*:\s*(.+)$",line)
        if m and m.group(1).strip().lower() in labels:
            field=labels[m.group(1).strip().lower()]
            if field in cur and cur: out.append(cur); cur={}
            cur[field]=m.group(2).strip()
        else:
            if cur: out.append(cur); cur={}
            out.append({"title":line})
    if cur: out.append(cur)
    return out[:30]

def build_personal_result_payload_v123(reply:Any,request:Any=None)->dict[str,Any]:
    provider=str(getattr(request,"provider_id","") or getattr(reply,"provider_id","") or "")
    capability=str(getattr(request,"capability_id","") or getattr(reply,"capability_id","") or "")
    kind=_kind(provider,capability); text=str(getattr(reply,"text","") or ""); raw=_plain(reply)
    keys={"mail":("messages","emails","items","results"),"calendar":("events","items","results"),"contacts":("contacts","people","items","results"),"tasks":("tasks","items","results"),"drive":("files","documents","items","results"),"generic":("items","results")}[kind]
    has_authoritative_list=_has_authoritative_list(raw,keys)
    items=[_norm(kind,x) for x in _find_list(raw,keys)]
    items=[{k:v for k,v in x.items() if v not in (None,"",[],{})} for x in items]; items=[x for x in items if x]
    source="reply_object"
    if not items and not has_authoritative_list: items=_fallback(kind,text); source="text_fallback"
    if kind=="tasks":
        _before_failed_receipts_v130=len(items)
        items=[x for x in items if not _is_failed_task_receipt_v130(x)]
        if len(items)!=_before_failed_receipts_v130:
            source="failed_receipt_filtered"
    return {"schema":"aura.personal-result.v123","kind":kind,"provider_id":provider,"capability_id":capability,"status":str(getattr(reply,"status","") or ""),"count":len(items),"items":items[:50],"fallback_text":text,"source":source}

def summarize_personal_result_for_tts_v123(payload:Mapping[str,Any],fallback_text:str="")->str:
    # AURA_V130_TASKS_FAILED_RECEIPT_SUMMARY_TRUTH_BEGIN
    _kind_v130=str(payload.get("kind") or "generic")
    if _kind_v130=="tasks":
        _breakdown_v130=payload.get("source_breakdown")
        if not isinstance(_breakdown_v130,Mapping):
            _breakdown_v130={}
        try:
            _google_v130=max(0,int(_breakdown_v130.get("google") or 0))
        except Exception:
            _google_v130=0
        try:
            _local_v130=max(0,int(_breakdown_v130.get("aura_local") or 0))
        except Exception:
            _local_v130=0
        _failed_v130=str(payload.get("source") or "")=="failed_receipt_filtered"
        if _failed_v130 and _google_v130==0:
            if _local_v130>0:
                return (
                    "La lecture Google Tasks a échoué. "
                    "J'affiche seulement "
                    + str(_local_v130)
                    + (" tâche AURA locale." if _local_v130==1 else " tâches AURA locales.")
                )
            return "La lecture Google Tasks a échoué. Je n'ai aucune tâche Google valide à afficher."
        if _google_v130>0 and _local_v130>0:
            return (
                "J'ai trouvé "
                + str(_google_v130)
                + (" tâche Google et " if _google_v130==1 else " tâches Google et ")
                + str(_local_v130)
                + (" tâche AURA locale. Je te les affiche." if _local_v130==1 else " tâches AURA locales. Je te les affiche.")
            )
        if _google_v130>0:
            return (
                "J'ai trouvé "
                + str(_google_v130)
                + (" tâche Google. Je te l'affiche." if _google_v130==1 else " tâches Google. Je te les affiche.")
            )
        if _local_v130>0:
            return (
                "J'affiche "
                + str(_local_v130)
                + (" tâche AURA locale." if _local_v130==1 else " tâches AURA locales.")
            )
    # AURA_V130_TASKS_FAILED_RECEIPT_SUMMARY_TRUTH_END

    kind=str(payload.get("kind") or "generic"); n=int(payload.get("count") or 0)
    if kind=="mail": return f"J'ai trouvé {n} mail{'s' if n!=1 else ''}. Je te les affiche." if n else "Je n'ai trouvé aucun mail à afficher."
    if kind=="calendar": return f"J'ai trouvé {n} rendez-vous à venir. Je te les affiche." if n else "Je n'ai trouvé aucun rendez-vous à afficher."
    if kind=="contacts": return f"J'ai trouvé {n} contact{'s' if n!=1 else ''}. Je te les affiche." if n else "Je n'ai trouvé aucun contact à afficher."
    if kind=="tasks": return f"J'ai trouvé {n} tâche{'s' if n!=1 else ''} Google. Je te les affiche." if n else "Je n'ai trouvé aucune tâche Google à afficher."
    if kind=="drive": return f"J'ai trouvé {n} élément{'s' if n!=1 else ''} dans Drive. Je te les affiche." if n else "Je n'ai trouvé aucun élément Drive à afficher."
    t=str(fallback_text or "").strip()
    return t if len(t)<=260 else t[:257].rstrip()+"..."

# AURA ROADMAP W131-3C R3 — PC RESULT CLASSIFICATION / SUMMARY
_aura_w131_r3_build_personal_result_original = build_personal_result_payload_v123
_aura_w131_r3_summarize_original = summarize_personal_result_for_tts_v123

def _aura_w131_r3_pc_identity(reply, request):
    provider = str(getattr(request, "provider_id", "") or "").strip()
    capability = str(getattr(request, "capability_id", "") or "").strip()
    if not capability:
        capability = str(getattr(reply, "capability_id", "") or "").strip()
    reply_payload = getattr(reply, "payload", None)
    if isinstance(reply_payload, Mapping):
        provider = str(reply_payload.get("provider_id") or provider).strip()
        capability = str(reply_payload.get("capability_id") or capability).strip()
    return (provider == "pc-control.windows" or capability.startswith("pc.")), provider, capability

def _aura_w131_r3_pc_payload(reply, request):
    is_pc, provider, capability = _aura_w131_r3_pc_identity(reply, request)
    if not is_pc:
        return None

    raw = getattr(reply, "payload", None)
    output = raw if isinstance(raw, Mapping) else {}
    pc_result = output.get("pc_result") if isinstance(output, Mapping) else {}
    if not isinstance(pc_result, Mapping):
        pc_result = {}
    data = pc_result.get("data")
    items = []
    title = "PC WINDOWS"

    if capability == "pc.discover_windows":
        title = "FENETRES WINDOWS"
        for row in (data or []):
            if not isinstance(row, Mapping):
                continue
            window_title = str(row.get("title") or "").strip()
            if not window_title:
                continue
            pid = row.get("pid")
            hwnd = row.get("hwnd")
            parts = []
            if pid not in (None, ""):
                parts.append("PID " + str(pid))
            if hwnd not in (None, ""):
                parts.append("HWND " + str(hwnd))
            if row.get("foreground") is True:
                parts.append("PREMIER PLAN")
            items.append({
                "source": "WINDOWS",
                "title": window_title,
                "subtitle": " · ".join(parts),
                "pid": pid,
                "hwnd": hwnd,
                "foreground": bool(row.get("foreground")),
            })

    elif capability == "pc.discover_processes":
        title = "PROCESSUS WINDOWS"
        for row in (data or []):
            if not isinstance(row, Mapping):
                continue
            image_name = str(row.get("image_name") or "").strip()
            pid = row.get("pid")
            parent_pid = row.get("parent_pid")
            if not image_name and pid in (None, ""):
                continue
            parts = []
            if pid not in (None, ""):
                parts.append("PID " + str(pid))
            if parent_pid not in (None, "", 0):
                parts.append("Parent " + str(parent_pid))
            items.append({
                "source": "WINDOWS",
                "title": image_name or ("PID " + str(pid)),
                "subtitle": " · ".join(parts),
                "pid": pid,
                "parent_pid": parent_pid,
            })

    elif capability == "pc.get_foreground_window":
        title = "FENETRE ACTIVE"
        row = data if isinstance(data, Mapping) else {}
        window_title = str(row.get("title") or "").strip()
        if window_title:
            items.append({
                "source": "WINDOWS",
                "title": window_title,
                "subtitle": "PID " + str(row.get("pid") or ""),
                "pid": row.get("pid"),
                "hwnd": row.get("hwnd"),
                "foreground": True,
            })

    elif capability in {"pc.focus_window", "pc.minimize_window", "pc.maximize_window", "pc.restore_window_state"}:
        labels = {
            "pc.focus_window": "MISE AU PREMIER PLAN",
            "pc.minimize_window": "MINIMISATION",
            "pc.maximize_window": "MAXIMISATION",
            "pc.restore_window_state": "RESTAURATION",
        }
        title = labels[capability]
        row = {}
        if isinstance(data, Mapping):
            row = data.get("after") or data.get("before") or {}
        if isinstance(row, Mapping):
            window_title = str(row.get("title") or "").strip()
            if window_title:
                items.append({
                    "source": "WINDOWS",
                    "title": window_title,
                    "subtitle": title,
                    "pid": row.get("pid"),
                    "hwnd": row.get("hwnd"),
                })

    return {
        "kind": "generic",
        "title": title,
        "source": "WINDOWS",
        "sources": ["WINDOWS"],
        "provider_id": "pc-control.windows",
        "capability_id": capability,
        "status": str(getattr(reply, "status", "") or ""),
        "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
        "fallback_text": str(getattr(reply, "text", "") or ""),
        "count": len(items),
        "items": items,
        "w131_pc_control": True,
    }

def build_personal_result_payload_v123(reply, request=None):
    pc_payload = _aura_w131_r3_pc_payload(reply, request)
    if pc_payload is not None:
        return pc_payload
    return _aura_w131_r3_build_personal_result_original(reply, request)

def summarize_personal_result_for_tts_v123(payload, fallback_text=""):
    if isinstance(payload, Mapping) and payload.get("w131_pc_control") is True:
        capability = str(payload.get("capability_id") or "")
        count = int(payload.get("count") or 0)
        if capability == "pc.discover_windows":
            return "J'ai detecte " + str(count) + " fenetre(s) Windows visible(s)."
        if capability == "pc.discover_processes":
            return "J'ai detecte " + str(count) + " processus Windows."
        if capability == "pc.get_foreground_window":
            items = list(payload.get("items") or [])
            title = str((items[0] if items else {}).get("title") or "").strip()
            if title:
                return "La fenetre au premier plan est : " + title + "."
        text = str(fallback_text or "").strip()
        return text or "Action Windows terminee."
    return _aura_w131_r3_summarize_original(payload, fallback_text)

# AURA ROADMAP W131-3D1 — PC INTENT CAPABILITY TRUTH
_aura_w131_3d1_pc_identity_base = _aura_w131_r3_pc_identity


def _aura_w131_r3_pc_identity(reply, request):
    is_pc, provider, capability = _aura_w131_3d1_pc_identity_base(reply, request)
    reply_capability = str(getattr(reply, "capability_id", "") or "").strip()
    if reply_capability.startswith("pc."):
        capability = reply_capability
        is_pc = True
        if not provider:
            provider = "pc-control.windows"
    return is_pc, provider, capability

# AURA_O140_R2_OBSIDIAN_PERSONAL_RESULT_TRUTH
_AURA_O140_R2_ORIGINAL_BUILD_PERSONAL_RESULT = build_personal_result_payload_v123
_AURA_O140_R2_ORIGINAL_TTS_SUMMARY = summarize_personal_result_for_tts_v123


def _aura_o140_r2_obsidian_payload(reply, request):
    provider = str(getattr(request, "provider_id", "") or "")
    capability = str(getattr(request, "capability_id", "") or getattr(reply, "capability_id", "") or "")
    if provider != "obsidian.creative" and not capability.startswith("obsidian."):
        return None

    raw = getattr(reply, "payload", None)
    output = raw if isinstance(raw, Mapping) else {}
    result = output.get("obsidian_result") if isinstance(output, Mapping) else {}
    result = result if isinstance(result, Mapping) else {}
    kind = str(result.get("kind") or "")
    items = []

    if kind == "vaults":
        for row in result.get("items") or []:
            if isinstance(row, Mapping):
                items.append({"source": "OBSIDIAN", "title": str(row.get("name") or "Vault Obsidian"), "note_type": "vault", "relative_path": str(row.get("path") or ""), "snippet": "Vault local Obsidian"})
    elif kind == "creative_snapshot":
        counts = result.get("counts") if isinstance(result.get("counts"), Mapping) else {}
        labels = [
            ("chapters", "Chapitres"), ("characters", "Personnages"),
            ("scenes", "Scenes"), ("continuity", "Continuite"),
            ("world", "Univers"), ("locations", "Lieux"), ("notes", "Notes"),
        ]
        for key, label in labels:
            count = int(counts.get(key) or 0)
            items.append({"source": "OBSIDIAN", "title": label, "note_type": "project_section", "relative_path": str(result.get("vault") or ""), "snippet": str(count) + " element(s)"})
    elif kind == "search":
        for row in result.get("results") or []:
            if isinstance(row, Mapping):
                items.append({"source": "OBSIDIAN", "title": str(row.get("title") or "Note"), "note_type": str(row.get("note_type") or "note"), "relative_path": str(row.get("relative_path") or ""), "snippet": str(row.get("snippet") or "")[:420]})
    elif kind == "note":
        items.append({"source": "OBSIDIAN", "title": str(result.get("title") or "Note"), "note_type": str(result.get("note_type") or "note"), "relative_path": str(result.get("relative_path") or ""), "snippet": str(result.get("body") or "")[:420]})

    titles = {
        "obsidian.discover_vaults": "VAULTS OBSIDIAN",
        "obsidian.creative_snapshot": "PROJET OBSIDIAN",
        "obsidian.search_context": "RECHERCHE OBSIDIAN",
        "obsidian.read_note": "NOTE OBSIDIAN",
    }
    return {
        "schema": "aura.personal-result.v123",
        "kind": "obsidian",
        "provider_id": "obsidian.creative",
        "capability_id": capability,
        "status": str(getattr(reply, "status", "") or ""),
        "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
        "title": titles.get(capability, "OBSIDIAN"),
        "count": len(items),
        "items": items[:50],
        "fallback_text": str(getattr(reply, "text", "") or ""),
        "source": "OBSIDIAN",
        "sources": ["OBSIDIAN"],
        "o140_obsidian": True,
    }


def build_personal_result_payload_v123(reply: Any, request: Any = None) -> dict[str, Any]:
    obsidian = _aura_o140_r2_obsidian_payload(reply, request)
    if obsidian is not None:
        return obsidian
    return _AURA_O140_R2_ORIGINAL_BUILD_PERSONAL_RESULT(reply, request)


def summarize_personal_result_for_tts_v123(payload: Mapping[str, Any], fallback_text: str = "") -> str:
    if isinstance(payload, Mapping) and payload.get("source") == "OBSIDIAN":
        count = int(payload.get("count") or 0)
        title = str(payload.get("title") or "OBSIDIAN")
        return f"{title}. {count} resultat(s)."
    return _AURA_O140_R2_ORIGINAL_TTS_SUMMARY(payload, fallback_text)

# AURA_O140_R3_CATEGORY_PERSONAL_RESULT
_AURA_O140_R3_PREVIOUS_BUILD_PERSONAL_RESULT = build_personal_result_payload_v123


def build_personal_result_payload_v123(reply: Any, request: Any = None) -> dict[str, Any]:
    provider = str(getattr(request, "provider_id", "") or "")
    capability = str(
        getattr(request, "capability_id", "")
        or getattr(reply, "capability_id", "")
        or ""
    )
    raw = getattr(reply, "payload", None)
    output = raw if isinstance(raw, Mapping) else {}
    ob = output.get("obsidian_result") if isinstance(output, Mapping) else {}
    ob = ob if isinstance(ob, Mapping) else {}

    if (
        (provider == "obsidian.creative" or capability.startswith("obsidian."))
        and str(ob.get("kind") or "") == "category"
    ):
        category = str(ob.get("category") or "notes")
        items = []
        for row in ob.get("items") or []:
            if not isinstance(row, Mapping):
                continue
            tags = row.get("tags") if isinstance(row.get("tags"), (list, tuple)) else []
            links = row.get("wikilinks") if isinstance(row.get("wikilinks"), (list, tuple)) else []
            details = []
            if tags:
                details.append("Tags: " + ", ".join(str(x) for x in tags[:8]))
            if links:
                details.append(str(len(links)) + " lien(s)")
            items.append({
                "source": "OBSIDIAN",
                "title": str(row.get("title") or "Note"),
                "note_type": str(row.get("note_type") or "note"),
                "relative_path": str(row.get("relative_path") or ""),
                "snippet": " | ".join(details),
            })

        titles = {
            "chapters": "CHAPITRES OBSIDIAN",
            "characters": "PERSONNAGES OBSIDIAN",
            "scenes": "SCENES OBSIDIAN",
            "continuity": "CONTINUITE OBSIDIAN",
            "world": "UNIVERS OBSIDIAN",
            "locations": "LIEUX OBSIDIAN",
            "notes": "NOTES OBSIDIAN",
        }
        return {
            "schema": "aura.personal-result.v123",
            "kind": "obsidian",
            "provider_id": "obsidian.creative",
            "capability_id": capability,
            "status": str(getattr(reply, "status", "") or ""),
            "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
            "title": titles.get(category, "OBSIDIAN"),
            "count": len(items),
            "items": items[:50],
            "fallback_text": str(getattr(reply, "text", "") or ""),
            "source": "OBSIDIAN",
            "sources": ["OBSIDIAN"],
            "o140_obsidian": True,
            "category": category,
        }

    return _AURA_O140_R3_PREVIOUS_BUILD_PERSONAL_RESULT(reply, request)

# AURA_O141_R2_LONGFORM_PERSONAL_RESULT
_AURA_O141_R2_PREVIOUS_BUILD_PERSONAL_RESULT = build_personal_result_payload_v123


def build_personal_result_payload_v123(reply: Any, request: Any = None) -> dict[str, Any]:
    provider = str(getattr(request, "provider_id", "") or "")
    capability = str(
        getattr(request, "capability_id", "")
        or getattr(reply, "capability_id", "")
        or ""
    )
    if provider != "longform.revision" and not capability.startswith("longform."):
        return _AURA_O141_R2_PREVIOUS_BUILD_PERSONAL_RESULT(reply, request)

    raw = getattr(reply, "payload", None)
    output = raw if isinstance(raw, Mapping) else {}
    result = output.get("longform_result") if isinstance(output, Mapping) else {}
    result = result if isinstance(result, Mapping) else {}
    kind = str(result.get("kind") or "")
    items = []
    title = "REVISION LONG-FORM"

    if kind == "manuscript_outline":
        title = "PLAN DU MANUSCRIT"
        for row in result.get("chapters") or []:
            if isinstance(row, Mapping):
                refs = row.get("references") if isinstance(row.get("references"), Mapping) else {}
                detail = (
                    str(row.get("word_count") or 0)
                    + " mots | "
                    + str(len(refs.get("characters") or []))
                    + " personnage(s) | "
                    + str(len(refs.get("locations") or []))
                    + " lieu(x)"
                )
                items.append({
                    "source": "OBSIDIAN",
                    "title": str(row.get("title") or "Chapitre"),
                    "note_type": "chapter",
                    "relative_path": str(row.get("relative_path") or ""),
                    "snippet": detail,
                })

    elif kind == "continuity_audit":
        title = "AUDIT DE CONTINUITE"
        for issue in result.get("issues") or []:
            if isinstance(issue, Mapping):
                code = str(issue.get("code") or "issue")
                detail = str(issue.get("link") or issue.get("title") or issue.get("chapter_number") or "")
                path = str(issue.get("from") or "")
                if not path and isinstance(issue.get("paths"), (list, tuple)) and issue.get("paths"):
                    path = str(issue.get("paths")[0])
                items.append({
                    "source": "OBSIDIAN",
                    "title": code.replace("_", " ").upper(),
                    "note_type": str(issue.get("severity") or "info"),
                    "relative_path": path,
                    "snippet": detail,
                })

    elif kind == "chapter_context":
        title = "CONTEXTE DE CHAPITRE"
        for row in result.get("chapters") or []:
            if isinstance(row, Mapping):
                items.append({
                    "source": "OBSIDIAN",
                    "title": str(row.get("title") or "Chapitre"),
                    "note_type": str(row.get("role") or "context"),
                    "relative_path": str(row.get("relative_path") or ""),
                    "snippet": str(row.get("excerpt") or "")[:420],
                })

    elif kind == "revision_brief":
        title = "BRIEF DE REVISION"
        for row in result.get("context") or []:
            if isinstance(row, Mapping):
                items.append({
                    "source": "OBSIDIAN",
                    "title": str(row.get("title") or "Chapitre"),
                    "note_type": str(row.get("role") or "context"),
                    "relative_path": str(row.get("relative_path") or ""),
                    "snippet": str(row.get("excerpt") or "")[:420],
                })
        for issue in result.get("related_issues") or []:
            if isinstance(issue, Mapping):
                items.append({
                    "source": "OBSIDIAN",
                    "title": str(issue.get("code") or "issue").replace("_", " ").upper(),
                    "note_type": str(issue.get("severity") or "warning"),
                    "relative_path": str(issue.get("from") or result.get("target") or ""),
                    "snippet": str(issue.get("link") or issue.get("title") or ""),
                })

    elif kind == "context_search_pack":
        title = "CONTEXTE LONG-FORM"
        for row in result.get("results") or []:
            if isinstance(row, Mapping):
                items.append({
                    "source": "OBSIDIAN",
                    "title": str(row.get("title") or "Note"),
                    "note_type": str(row.get("note_type") or "note"),
                    "relative_path": str(row.get("relative_path") or ""),
                    "snippet": str(row.get("snippet") or "")[:420],
                })

    return {
        "schema": "aura.personal-result.v123",
        "kind": "obsidian",
        "provider_id": "longform.revision",
        "capability_id": capability,
        "status": str(getattr(reply, "status", "") or ""),
        "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
        "title": title,
        "count": len(items),
        "items": items[:50],
        "fallback_text": str(getattr(reply, "text", "") or ""),
        "source": "OBSIDIAN",
        "sources": ["OBSIDIAN"],
        "o141_longform": True,
    }

# AURA_O141_R3_REVISION_INTELLIGENCE_RESULTS
import json as _aura_o141_r3_json
_AURA_O141_R3_PREVIOUS_BUILD_RESULT = build_personal_result_payload_v123


def _aura_o141_r3_csv(values):
    vals = [str(x) for x in (values or []) if str(x).strip()]
    return ", ".join(vals) if vals else "Aucun"


def build_personal_result_payload_v123(reply: Any, request: Any = None) -> dict[str, Any]:
    raw = getattr(reply, "payload", None)
    output = raw if isinstance(raw, Mapping) else {}
    result = output.get("longform_result") if isinstance(output, Mapping) else {}
    result = result if isinstance(result, Mapping) else {}
    kind = str(result.get("kind") or "")

    if kind == "chapter_revision_report":
        metrics = result.get("metrics") if isinstance(result.get("metrics"), Mapping) else {}
        refs = result.get("references") if isinstance(result.get("references"), Mapping) else {}
        tin = result.get("transition_in") if isinstance(result.get("transition_in"), Mapping) else None
        tout = result.get("transition_out") if isinstance(result.get("transition_out"), Mapping) else None
        issues = result.get("related_issues") if isinstance(result.get("related_issues"), list) else []
        unresolved = result.get("unresolved_links") if isinstance(result.get("unresolved_links"), list) else []

        in_text = "Debut du manuscrit"
        if tin:
            chars = tin.get("characters") if isinstance(tin.get("characters"), Mapping) else {}
            in_text = (
                "Depuis " + str((tin.get("from") or {}).get("title") or "chapitre precedent")
                + " | nouveaux: " + _aura_o141_r3_csv(chars.get("introduced"))
                + " | communs: " + _aura_o141_r3_csv(chars.get("shared"))
            )

        out_text = "Fin du manuscrit"
        if tout:
            chars = tout.get("characters") if isinstance(tout.get("characters"), Mapping) else {}
            out_text = (
                "Vers " + str((tout.get("to") or {}).get("title") or "chapitre suivant")
                + " | nouveaux: " + _aura_o141_r3_csv(chars.get("introduced"))
                + " | communs: " + _aura_o141_r3_csv(chars.get("shared"))
            )

        items = [
            {
                "source": "OBSIDIAN",
                "title": str(result.get("title") or "Chapitre"),
                "note_type": "CHAPITRE",
                "relative_path": str(result.get("target") or ""),
                "snippet": (
                    str(metrics.get("word_count") or 0) + " mots | "
                    + str(metrics.get("paragraph_count") or 0) + " paragraphes | "
                    + str(metrics.get("sentence_count") or 0) + " phrases | moyenne "
                    + str(metrics.get("average_sentence_words") or 0) + " mots/phrase"
                ),
            },
            {
                "source": "OBSIDIAN",
                "title": "PERSONNAGES",
                "note_type": "REFERENCES",
                "relative_path": str(result.get("target") or ""),
                "snippet": _aura_o141_r3_csv(refs.get("characters")),
            },
            {
                "source": "OBSIDIAN",
                "title": "LIEUX",
                "note_type": "REFERENCES",
                "relative_path": str(result.get("target") or ""),
                "snippet": _aura_o141_r3_csv(refs.get("locations")),
            },
            {
                "source": "OBSIDIAN",
                "title": "TRANSITION ENTRANTE",
                "note_type": "CONTEXTE",
                "relative_path": str(result.get("target") or ""),
                "snippet": in_text,
            },
            {
                "source": "OBSIDIAN",
                "title": "TRANSITION SORTANTE",
                "note_type": "CONTEXTE",
                "relative_path": str(result.get("target") or ""),
                "snippet": out_text,
            },
            {
                "source": "OBSIDIAN",
                "title": "CONTINUITE",
                "note_type": "AUDIT",
                "relative_path": str(result.get("target") or ""),
                "snippet": (
                    str(len(issues)) + " probleme(s) rattache(s) | "
                    + str(len(unresolved)) + " wikilink(s) non resolu(s)"
                ),
            },
        ]
        return {
            "schema": "aura.personal-result.v123",
            "kind": "obsidian",
            "provider_id": "longform.revision",
            "capability_id": "longform.chapter_revision_report",
            "status": str(getattr(reply, "status", "") or ""),
            "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
            "title": "RAPPORT DE REVISION",
            "count": len(items),
            "items": items,
            "fallback_text": str(getattr(reply, "text", "") or ""),
            "source": "OBSIDIAN",
            "sources": ["OBSIDIAN"],
            "o141_revision_intelligence": True,
        }

    if kind == "chapter_transition":
        items = []
        for key, label in (
            ("characters", "PERSONNAGES"),
            ("locations", "LIEUX"),
            ("world", "UNIVERS"),
        ):
            delta = result.get(key) if isinstance(result.get(key), Mapping) else {}
            items.append({
                "source": "OBSIDIAN",
                "title": label,
                "note_type": "TRANSITION",
                "relative_path": str((result.get("to") or {}).get("relative_path") or ""),
                "snippet": (
                    "Communs: " + _aura_o141_r3_csv(delta.get("shared"))
                    + " | Introduits: " + _aura_o141_r3_csv(delta.get("introduced"))
                    + " | Sortants: " + _aura_o141_r3_csv(delta.get("dropped"))
                ),
            })
        items.append({
            "source": "OBSIDIAN",
            "title": "VOLUME",
            "note_type": "TRANSITION",
            "relative_path": str((result.get("to") or {}).get("relative_path") or ""),
            "snippet": "Delta de mots: " + str(result.get("word_count_delta") or 0),
        })
        return {
            "schema": "aura.personal-result.v123",
            "kind": "obsidian",
            "provider_id": "longform.revision",
            "capability_id": "longform.chapter_transition",
            "status": str(getattr(reply, "status", "") or ""),
            "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
            "title": "TRANSITION DE CHAPITRES",
            "count": len(items),
            "items": items,
            "fallback_text": str(getattr(reply, "text", "") or ""),
            "source": "OBSIDIAN",
            "sources": ["OBSIDIAN"],
            "o141_revision_intelligence": True,
        }

    if kind == "manuscript_revision_report":
        items = [
            {
                "source": "OBSIDIAN",
                "title": "MANUSCRIT",
                "note_type": "SYNTHESE",
                "relative_path": str(result.get("vault") or ""),
                "snippet": (
                    str(result.get("chapter_count") or 0) + " chapitre(s) | "
                    + str(result.get("total_words") or 0) + " mots"
                ),
            },
            {
                "source": "OBSIDIAN",
                "title": "CONTINUITE",
                "note_type": "AUDIT",
                "relative_path": str(result.get("vault") or ""),
                "snippet": (
                    str(result.get("continuity_issue_count") or 0)
                    + " point(s) | "
                    + _aura_o141_r3_json.dumps(result.get("issues_by_code") or {}, ensure_ascii=False)
                ),
            },
            {
                "source": "OBSIDIAN",
                "title": "TRANSITIONS",
                "note_type": "AUDIT",
                "relative_path": str(result.get("vault") or ""),
                "snippet": str(len(result.get("transitions") or [])) + " transition(s) analysee(s)",
            },
        ]
        for row in result.get("chapters") or []:
            if isinstance(row, Mapping):
                items.append({
                    "source": "OBSIDIAN",
                    "title": str(row.get("title") or "Chapitre"),
                    "note_type": "CHAPITRE",
                    "relative_path": str(row.get("relative_path") or ""),
                    "snippet": (
                        str(row.get("word_count") or 0) + " mots | "
                        + str(row.get("character_count") or 0) + " personnage(s) | "
                        + str(row.get("location_count") or 0) + " lieu(x) | "
                        + str(row.get("unresolved_link_count") or 0) + " lien(s) non resolu(s)"
                    ),
                })
        return {
            "schema": "aura.personal-result.v123",
            "kind": "obsidian",
            "provider_id": "longform.revision",
            "capability_id": "longform.manuscript_revision_report",
            "status": str(getattr(reply, "status", "") or ""),
            "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
            "title": "RAPPORT GLOBAL DE REVISION",
            "count": len(items),
            "items": items[:50],
            "fallback_text": str(getattr(reply, "text", "") or ""),
            "source": "OBSIDIAN",
            "sources": ["OBSIDIAN"],
            "o141_revision_intelligence": True,
        }

    return _AURA_O141_R3_PREVIOUS_BUILD_RESULT(reply, request)

# AURA_Y150_R2_YOUTUBE_PERSONAL_RESULT
_AURA_Y150_R2_PREVIOUS_BUILD=build_personal_result_payload_v123
def build_personal_result_payload_v123(reply:Any,request:Any=None)->dict[str,Any]:
 cap=str(getattr(request,"capability_id","") or getattr(reply,"capability_id","") or "")
 if not cap.startswith("youtube."):return _AURA_Y150_R2_PREVIOUS_BUILD(reply,request)
 raw=getattr(reply,"payload",None);out=raw if isinstance(raw,Mapping) else {};r=out.get("youtube_result") if isinstance(out,Mapping) else {};r=r if isinstance(r,Mapping) else {};items=[];title="YOUTUBE"
 if cap=="youtube.channel_snapshot":
  title="BILAN YOUTUBE";real=r.get("real_channel") if isinstance(r.get("real_channel"),Mapping) else {};s=real.get("current_stats") if isinstance(real.get("current_stats"),Mapping) else {};g=real.get("period_growth") if isinstance(real.get("period_growth"),Mapping) else {}
  items=[{"source":"YOUTUBE","title":"ABONNES","note_type":"KPI","relative_path":"","snippet":str(s.get("subscribers") or 0)},{"source":"YOUTUBE","title":"VUES TOTALES","note_type":"KPI","relative_path":"","snippet":str(s.get("views") or 0)},{"source":"YOUTUBE","title":"VIDEOS","note_type":"KPI","relative_path":"","snippet":str(s.get("videos") or 0)},{"source":"YOUTUBE","title":"CROISSANCE 29 JOURS","note_type":"KPI","relative_path":"","snippet":"+"+str(g.get("subscribers_gained") or 0)+" abonnes | +"+str(g.get("views_gained") or 0)+" vues"}]
  for x in r.get("top_videos") or []:items.append({"source":"YOUTUBE","title":str(x.get("title") or "Video"),"note_type":"VIDEO","relative_path":str(x.get("video_id") or ""),"snippet":"score "+str(x.get("score") or 0)+" | retention "+str(x.get("retention_percent") or 0)+"%"})
 elif cap=="youtube.opportunity_board":
  title="OPPORTUNITES YOUTUBE"
  for x in r.get("items") or []:items.append({"source":"YOUTUBE","title":str(x.get("title") or "Video"),"note_type":str(x.get("action") or "monitor").upper(),"relative_path":str(x.get("video_id") or ""),"snippet":str(x.get("reason") or "")})
 elif cap=="youtube.next_upload_brief":
  title="PROCHAINE VIDEO"
  for x in r.get("top_reference_videos") or []:items.append({"source":"YOUTUBE","title":str(x.get("title") or "Reference"),"note_type":"REFERENCE","relative_path":str(x.get("video_id") or ""),"snippet":"score "+str(x.get("score") or 0)})
  items.append({"source":"YOUTUBE","title":"FOCUS","note_type":"DECISION","relative_path":"","snippet":str(r.get("recommended_focus") or "")})
 elif cap=="youtube.publishing_cadence":
  title="CADENCE YOUTUBE";items=[{"source":"YOUTUBE","title":"ECART MEDIAN","note_type":"CADENCE","relative_path":"","snippet":str(r.get("median_gap_days") or 0)+" jours"},{"source":"YOUTUBE","title":"ECART MOYEN","note_type":"CADENCE","relative_path":"","snippet":str(r.get("average_gap_days") or 0)+" jours"}]
 elif cap=="youtube.scorecards":
  title="CLASSEMENT YOUTUBE"
  for x in r.get("items") or []:items.append({"source":"YOUTUBE","title":str(x.get("title") or "Video"),"note_type":"SCORE","relative_path":str(x.get("video_id") or ""),"snippet":"score "+str(x.get("score") or 0)+" | retention "+str(x.get("retention_percent") or 0)+"%"})
 return {"schema":"aura.personal-result.v123","kind":"generic","provider_id":"youtube.studio-copilot","capability_id":cap,"status":str(getattr(reply,"status","") or ""),"receipt_id":str(getattr(reply,"receipt_id","") or ""),"title":title,"count":len(items),"items":items[:50],"fallback_text":str(getattr(reply,"text","") or ""),"source":"YOUTUBE","sources":["YOUTUBE"],"y150_youtube":True}


# ==== AURA_Y150_R4_TRUE_ANALYTICS_PANEL ====
def _aura_y150_r4_safe_number(v):
    try:
        return int(v)
    except Exception:
        return 0

def _aura_y150_r4_compact(v):
    v = _aura_y150_r4_safe_number(v)
    return str(v)

def _aura_y150_r4_dashboard_payload():
    import base64 as _base64
    import json as _json
    from pathlib import Path as _Path

    _root = _Path(__file__).resolve().parents[1]
    _data_path = _root / "data" / "youtube" / "neural_echo_youtube_snapshot_v150.json"
    _data = _json.loads(_data_path.read_text(encoding="utf-8-sig"))
    _channel = _data.get("channel") or {}
    _stats = _channel.get("current_stats") or {}
    _growth = _channel.get("period_growth") or {}
    _videos = list(_data.get("videos") or [])

    def _score(row):
        for key in ("score", "opportunity_score", "total_score"):
            if key in row:
                try:
                    return float(row.get(key) or 0)
                except Exception:
                    return 0.0
        return 0.0

    def _views(row):
        for key in ("views", "view_count"):
            if key in row:
                try:
                    return int(row.get(key) or 0)
                except Exception:
                    return 0
        return 0

    def _vph(row):
        for key in ("vph", "views_per_hour"):
            if key in row:
                try:
                    return float(row.get(key) or 0)
                except Exception:
                    return 0.0
        return 0.0

    def _oppty(row):
        for key in ("recommended_action", "opportunity", "action", "primary_action"):
            raw = str(row.get(key) or "").strip()
            if raw:
                return raw
        return "watch"

    _top = sorted(_videos, key=lambda r: (_score(r), _views(r)), reverse=True)[:5]
    _opp = sorted(_videos, key=lambda r: (_score(r), _vph(r)), reverse=True)[:4]

    _payload = {
        "panel_kind": "youtube_analytics_dashboard",
        "channel_title": str(_channel.get("title") or "Neural Echo Music"),
        "captured_at": str(_data.get("captured_at") or ""),
        "kpis": {
            "subscribers": _aura_y150_r4_safe_number(_stats.get("subscribers")),
            "views": _aura_y150_r4_safe_number(_stats.get("views")),
            "videos": _aura_y150_r4_safe_number(_stats.get("videos")),
            "subs_growth": _aura_y150_r4_safe_number(_growth.get("subscribers_gained")),
            "views_growth": _aura_y150_r4_safe_number(_growth.get("views_gained")),
            "uploads_growth": _aura_y150_r4_safe_number(_growth.get("videos_published")),
            "snapshot_rows": len(_videos),
        },
        "top_videos": [
            {
                "title": str(v.get("title") or "Untitled"),
                "views": _views(v),
                "vph": _vph(v),
                "score": _score(v),
                "action": _oppty(v),
            }
            for v in _top
        ],
        "opportunities": [
            {
                "title": str(v.get("title") or "Untitled"),
                "action": _oppty(v),
                "score": _score(v),
                "views": _views(v),
            }
            for v in _opp
        ],
        "notes": [
            "CTR d impressions absent du snapshot : aucune recommandation packaging n est inventee.",
            "Source : snapshot local read-only de Neural Echo Music.",
            "Les videos listees sont des references analytiques, pas des actions mutantes.",
        ],
    }

    _raw = _json.dumps(_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "__AURA_Y150_ANALYTICS_JSON__:" + _base64.b64encode(_raw).decode("ascii")

try:
    _aura_y150_r4_original_build_personal_result_payload_v123 = build_personal_result_payload_v123
except Exception:
    _aura_y150_r4_original_build_personal_result_payload_v123 = None

if _aura_y150_r4_original_build_personal_result_payload_v123 is not None:
    def build_personal_result_payload_v123(reply, last_request=None):  # type: ignore[override]
        payload = _aura_y150_r4_original_build_personal_result_payload_v123(reply, last_request)
        try:
            _source = str((payload or {}).get("source") or "").upper()
            _title = str((payload or {}).get("title") or "").upper()
            _cap = str(getattr(reply, "capability_id", "") or "").lower()
            if _cap == "youtube.channel_snapshot":
                _marker = _aura_y150_r4_dashboard_payload()
                _items = list((payload or {}).get("items") or [])
                _hidden = {
                    "source": "YOUTUBE",
                    "title": _marker,
                    "type": "META",
                    "note": "analytics dashboard bootstrap",
                    "context": "analytics dashboard bootstrap",
                }
                if not _items or str((_items[0] or {}).get("title") or "") != "__AURA_Y150_ANALYTICS_JSON__":
                    _items.insert(0, _hidden)
                payload["items"] = _items
                payload["title"] = "BILAN YOUTUBE"
                payload["source"] = "YOUTUBE"
                payload["count"] = 14
        except Exception:
            return payload
        return payload
# ==== /AURA_Y150_R4_TRUE_ANALYTICS_PANEL ====

# AURA_Y150_R4_R2_BOOTSTRAP_IN_RENDERED_TITLE


# ==== AURA_Y150_R4_R4_DATA_TRUTH ====
def _aura_y150_r4_r4_repair_text(value):
    raw = str(value or "")
    if not raw:
        return raw
    bad = sum(raw.count(x) for x in ("A", "A", "d", "a"))
    if not bad:
        return raw
    for enc in ("latin1", "cp1252"):
        try:
            candidate = raw.encode(enc).decode("utf-8")
            new_bad = sum(candidate.count(x) for x in ("A", "A", "d", "a"))
            if new_bad < bad:
                return candidate
        except Exception:
            pass
    return raw

def _aura_y150_r4_dashboard_payload():
    import base64 as _base64
    import json as _json
    from pathlib import Path as _Path
    from runtime.aura_youtube_studio_copilot_v150 import YouTubeStudioCopilot as _Studio

    _root = _Path(__file__).resolve().parents[1]
    _data_path = _root / "data" / "youtube" / "neural_echo_youtube_snapshot_v150.json"
    _data = _json.loads(_data_path.read_text(encoding="utf-8-sig"))
    _channel = _data.get("channel") or {}
    _stats = _channel.get("current_stats") or {}
    _growth = _channel.get("period_growth") or {}
    _videos = list(_data.get("videos") or [])

    _studio = _Studio(_videos, channel_name=str(_channel.get("title") or "Neural Echo Music"))
    _bench = _studio.benchmarks()
    _scores = _studio.scorecards()
    _board = _studio.opportunity_board()
    _actions = {
        str(row.get("video_id") or ""): row
        for row in (_board.get("items") or [])
        if isinstance(row, dict)
    }

    _priority = {
        "double_down": 0,
        "hook_retention": 1,
        "distribution": 2,
        "packaging": 3,
        "monitor": 4,
    }
    _opps = sorted(
        list(_board.get("items") or []),
        key=lambda row: (
            _priority.get(str(row.get("action") or "monitor"), 9),
            -float(row.get("score") or 0),
            -float((row.get("metrics") or {}).get("views_per_day") or 0),
        ),
    )[:4]

    _top = _scores[:5]

    def _title(row):
        return _aura_y150_r4_r4_repair_text(row.get("title") or "Untitled")

    _payload = {
        "panel_kind": "youtube_analytics_dashboard",
        "channel_title": _aura_y150_r4_r4_repair_text(_channel.get("title") or "Neural Echo Music"),
        "captured_at": str(_data.get("captured_at") or ""),
        "kpis": {
            "subscribers": int(_stats.get("subscribers") or 0),
            "views": int(_stats.get("views") or 0),
            "videos": int(_stats.get("videos") or 0),
            "subs_growth": int(_growth.get("subscribers_gained") or 0),
            "views_growth": int(_growth.get("views_gained") or 0),
            "uploads_growth": int(_growth.get("videos_published") or 0),
            "snapshot_rows": len(_videos),
            "median_retention": round(float(_bench.get("median_retention_percent") or 0), 1),
            "median_views_per_day": round(float(_bench.get("median_views_per_day") or 0), 1),
            "ctr_available": bool(_bench.get("ctr_available")),
        },
        "top_videos": [
            {
                "video_id": str(row.get("video_id") or ""),
                "title": _title(row),
                "views": int(row.get("views") or 0),
                "views_per_day": round(float(row.get("views_per_day") or 0), 1),
                "retention": round(float(row.get("retention_percent") or 0), 1),
                "engagement": round(float(row.get("engagement_percent") or 0), 1),
                "score": round(float(row.get("score") or 0), 1),
                "action": str((_actions.get(str(row.get("video_id") or "")) or {}).get("action") or "monitor"),
            }
            for row in _top
        ],
        "opportunities": [
            {
                "video_id": str(row.get("video_id") or ""),
                "title": _aura_y150_r4_r4_repair_text(row.get("title") or "Untitled"),
                "action": str(row.get("action") or "monitor"),
                "score": round(float(row.get("score") or 0), 1),
                "views": int((row.get("metrics") or {}).get("views") or 0),
                "views_per_day": round(float((row.get("metrics") or {}).get("views_per_day") or 0), 1),
                "retention": round(float((row.get("metrics") or {}).get("retention_percent") or 0), 1),
                "reason": str(row.get("reason") or ""),
            }
            for row in _opps
        ],
        "notes": [
            "Retention mediane : " + str(round(float(_bench.get("median_retention_percent") or 0), 1)) + "%.",
            "Vitesse mediane : " + str(round(float(_bench.get("median_views_per_day") or 0), 1)) + " vues/jour.",
            (
                "CTR d impressions indisponible : aucune recommandation packaging basee sur le CTR."
                if not _bench.get("ctr_available")
                else "CTR d impressions disponible et inclus dans le scoring."
            ),
        ],
    }

    _raw = _json.dumps(_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "__AURA_Y150_ANALYTICS_JSON__:" + _base64.b64encode(_raw).decode("ascii")
# ==== /AURA_Y150_R4_R4_DATA_TRUTH ====

# AURA_Y150_R5_R3_CHANNEL_SNAPSHOT_ONLY_DASHBOARD

# AURA_Y151_R2_CHANNEL_ANALYTICS_PUBLISHING_RESULTS
_AURA_Y151_R2_PREVIOUS_BUILD_RESULT = build_personal_result_payload_v123


def build_personal_result_payload_v123(reply: Any, request: Any = None) -> dict[str, Any]:
    provider = str(getattr(request, "provider_id", "") or "")
    capability = str(
        getattr(request, "capability_id", "")
        or getattr(reply, "capability_id", "")
        or ""
    )
    if provider != "channel.analytics-publishing" and not (
        capability.startswith("channel.")
        or capability.startswith("publishing.")
    ):
        return _AURA_Y151_R2_PREVIOUS_BUILD_RESULT(reply, request)

    raw = getattr(reply, "payload", None)
    output = raw if isinstance(raw, Mapping) else {}
    result = output.get("y151_result") if isinstance(output, Mapping) else {}
    result = result if isinstance(result, Mapping) else {}

    items = []
    title = "YOUTUBE WORKFLOW"

    if capability == "channel.compare_formats":
        title = "COMPARAISON FORMATS"
        formats = result.get("formats") if isinstance(result.get("formats"), Mapping) else {}
        for fmt, label in (("short", "SHORTS"), ("video", "VIDEOS LONGUES")):
            row = formats.get(fmt) if isinstance(formats.get(fmt), Mapping) else {}
            items.append({
                "source": "YOUTUBE",
                "title": label,
                "note_type": "FORMAT",
                "relative_path": fmt,
                "snippet": (
                    str(row.get("sample_size") or 0) + " exemples | "
                    + str(row.get("median_views_per_day") or 0) + " vues/j | "
                    + "ret. " + str(row.get("median_retention_percent") or 0) + "% | "
                    + "eng. " + str(row.get("median_engagement_percent") or 0) + "%"
                ),
            })
        items.append({
            "source": "YOUTUBE",
            "title": "RECOMMANDATION",
            "note_type": "DECISION",
            "relative_path": "",
            "snippet": (
                "Portee: " + str(result.get("reach_winner") or "?")
                + " | Retention: " + str(result.get("retention_winner") or "?")
            ),
        })

    elif capability == "channel.publishing_windows":
        title = "FENETRES DE PUBLICATION"
        windows = result.get("windows") if isinstance(result.get("windows"), list) else []
        for row in windows[:8]:
            if not isinstance(row, Mapping):
                continue
            sample = int(row.get("sample_size") or 0)
            confidence = "EXPLORATOIRE" if sample < 2 else "SIGNAL"
            items.append({
                "source": "YOUTUBE",
                "title": (
                    str(row.get("weekday_utc") or "?")
                    + " "
                    + str(row.get("hour_utc") or 0).zfill(2)
                    + ":00 UTC"
                ),
                "note_type": confidence,
                "relative_path": "",
                "snippet": (
                    "n=" + str(sample)
                    + " | " + str(row.get("median_views_per_day") or 0) + " vues/j"
                    + " | ret. " + str(row.get("median_retention_percent") or 0) + "%"
                ),
            })
        if not items:
            items.append({
                "source": "YOUTUBE",
                "title": "DONNEES INSUFFISANTES",
                "note_type": "INFO",
                "relative_path": "",
                "snippet": "Aucune fenetre historique exploitable.",
            })

    elif capability == "channel.recommendation_matrix":
        title = "MATRICE FORMATS"
        for row in result.get("formats") or []:
            if isinstance(row, Mapping):
                items.append({
                    "source": "YOUTUBE",
                    "title": str(row.get("format") or "").upper(),
                    "note_type": "FORMAT",
                    "relative_path": str(row.get("format") or ""),
                    "snippet": (
                        "Portee " + str(row.get("reach_score") or 0)
                        + " | Ret. " + str(row.get("retention_score") or 0)
                        + " | Eng. " + str(row.get("engagement_score") or 0)
                    ),
                })

    elif capability == "channel.editorial_mix":
        title = "MIX EDITORIAL"
        items = [
            {
                "source": "YOUTUBE",
                "title": "SHORTS",
                "note_type": "PLANNING",
                "relative_path": "",
                "snippet": str(result.get("short_slots") or 0) + " slot(s) / semaine",
            },
            {
                "source": "YOUTUBE",
                "title": "VIDEOS LONGUES",
                "note_type": "PLANNING",
                "relative_path": "",
                "snippet": str(result.get("long_form_slots") or 0) + " slot(s) / semaine",
            },
            {
                "source": "YOUTUBE",
                "title": "BASE",
                "note_type": "METHODE",
                "relative_path": "",
                "snippet": str(result.get("basis") or ""),
            },
        ]

    elif capability == "publishing.create_workflow_plan":
        title = "WORKFLOW DE PUBLICATION"
        draft = result.get("draft") if isinstance(result.get("draft"), Mapping) else {}
        gates = result.get("gates") if isinstance(result.get("gates"), list) else []
        items = [
            {
                "source": "YOUTUBE",
                "title": str(draft.get("title") or "Sans titre"),
                "note_type": "BROUILLON LOCAL",
                "relative_path": "",
                "snippet": (
                    "Format: " + str(draft.get("format") or "?")
                    + " | Etat: " + str(result.get("state") or "?")
                ),
            },
            {
                "source": "YOUTUBE",
                "title": "APPROBATION REQUISE",
                "note_type": "GARDE-FOU",
                "relative_path": "",
                "snippet": "Confirmation explicite obligatoire avant toute future publication.",
            },
            {
                "source": "YOUTUBE",
                "title": "AUCUNE PUBLICATION EFFECTUEE",
                "note_type": "SECURITE",
                "relative_path": "",
                "snippet": (
                    "Mutation externe: "
                    + str(bool(result.get("external_mutation_performed"))).lower()
                    + " | Gates: "
                    + ", ".join(str(x) for x in gates)
                ),
            },
        ]

    return {
        "schema": "aura.personal-result.v123",
        "kind": "youtube",
        "provider_id": "channel.analytics-publishing",
        "capability_id": capability,
        "status": str(getattr(reply, "status", "") or ""),
        "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
        "title": title,
        "count": len(items),
        "items": items[:50],
        "fallback_text": str(getattr(reply, "text", "") or ""),
        "source": "YOUTUBE",
        "sources": ["YOUTUBE"],
        "y151_channel_workflows": True,
    }

# AURA_Y151_R3_R2_CONTROLLED_WORKFLOW_RESULTS
_AURA_Y151_R3_R2_PREVIOUS_BUILD_RESULT = build_personal_result_payload_v123


def build_personal_result_payload_v123(reply: Any, request: Any = None) -> dict[str, Any]:
    capability = str(
        getattr(request, "capability_id", "")
        or getattr(reply, "capability_id", "")
        or ""
    )

    if capability == "publishing.workflow_status":
        raw = getattr(reply, "payload", None)
        output = raw if isinstance(raw, Mapping) else {}
        result = output.get("y151_result") if isinstance(output, Mapping) else {}
        result = result if isinstance(result, Mapping) else {}
        record = result.get("workflow_record") if isinstance(result.get("workflow_record"), Mapping) else {}
        if not record:
            items = [{
                "source": "YOUTUBE",
                "title": "AUCUN WORKFLOW",
                "note_type": "INFO",
                "relative_path": "",
                "snippet": "Aucun workflow local de publication n'est enregistre.",
            }]
        else:
            items = [
                {
                    "source": "YOUTUBE",
                    "title": "ID WORKFLOW",
                    "note_type": "LOCAL",
                    "relative_path": str(record.get("workflow_id") or ""),
                    "snippet": str(record.get("workflow_id") or ""),
                },
                {
                    "source": "YOUTUBE",
                    "title": str(record.get("title") or "Sans titre"),
                    "note_type": "BROUILLON LOCAL",
                    "relative_path": "",
                    "snippet": "Format: " + str(record.get("format") or "?"),
                },
                {
                    "source": "YOUTUBE",
                    "title": "ETAT",
                    "note_type": "GARDE-FOU",
                    "relative_path": "",
                    "snippet": str(record.get("state") or "?"),
                },
                {
                    "source": "YOUTUBE",
                    "title": "PUBLICATION BLOQUEE",
                    "note_type": "SECURITE",
                    "relative_path": "",
                    "snippet": "publish_available=false | external_mutation=false",
                },
            ]
        return {
            "schema": "aura.personal-result.v123",
            "kind": "youtube",
            "provider_id": "channel.analytics-publishing",
            "capability_id": capability,
            "status": str(getattr(reply, "status", "") or ""),
            "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
            "title": "ETAT WORKFLOW",
            "count": len(items),
            "items": items,
            "fallback_text": str(getattr(reply, "text", "") or ""),
            "source": "YOUTUBE",
            "sources": ["YOUTUBE"],
            "y151_controlled_workflow": True,
        }

    payload = _AURA_Y151_R3_R2_PREVIOUS_BUILD_RESULT(reply, request)
    if capability == "publishing.create_workflow_plan" and isinstance(payload, Mapping):
        raw = getattr(reply, "payload", None)
        output = raw if isinstance(raw, Mapping) else {}
        result = output.get("y151_result") if isinstance(output, Mapping) else {}
        result = result if isinstance(result, Mapping) else {}
        record = result.get("workflow_record") if isinstance(result.get("workflow_record"), Mapping) else {}
        if record:
            items = list(payload.get("items") or [])
            if items:
                first = dict(items[0])
                workflow_id = str(record.get("workflow_id") or "")
                workflow_state = str(record.get("state") or "?")
                first["relative_path"] = workflow_id
                base_snippet = str(first.get("snippet") or "")
                first["snippet"] = (
                    base_snippet
                    + " | ID "
                    + workflow_id
                    + " | etat "
                    + workflow_state
                ).strip(" |")
                items[0] = first
            payload["items"] = items
            payload["count"] = len(items)
            payload["workflow_id"] = str(record.get("workflow_id") or "")
            payload["workflow_state"] = str(record.get("state") or "")
            payload["y151_controlled_workflow"] = True
    return payload

# AURA_L170_R2_CONTROLLED_LEARNING_RESULTS
_AURA_L170_R2_PREVIOUS_BUILD_RESULT = build_personal_result_payload_v123


def build_personal_result_payload_v123(reply: Any, request: Any = None) -> dict[str, Any]:
    provider = str(getattr(request, "provider_id", "") or "")
    capability = str(
        getattr(request, "capability_id", "")
        or getattr(reply, "capability_id", "")
        or ""
    )
    if provider != "controlled.learning" and not capability.startswith("learning."):
        return _AURA_L170_R2_PREVIOUS_BUILD_RESULT(reply, request)

    raw = getattr(reply, "payload", None)
    output = raw if isinstance(raw, Mapping) else {}
    result = output.get("l170_result") if isinstance(output, Mapping) else {}
    result = result if isinstance(result, Mapping) else {}

    items = []
    title = "APPRENTISSAGE CONTROLE"

    def _candidate_item(row):
        prov = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
        return {
            "source": "MEMORY",
            "title": str(row.get("subject") or "Candidat"),
            "note_type": str(row.get("state") or "candidate").upper(),
            "relative_path": str(row.get("candidate_id") or ""),
            "snippet": (
                str(row.get("predicate") or "")
                + " = "
                + str(row.get("value") or "")
                + " | source "
                + str(prov.get("source_kind") or "?")
                + ":"
                + str(prov.get("source_ref") or "?")
            ),
        }

    if capability == "learning.propose_candidate":
        title = "CANDIDAT MEMOIRE"
        row = result
        prov = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
        items = [
            {
                "source": "MEMORY",
                "title": str(row.get("subject") or "Candidat"),
                "note_type": "CANDIDAT",
                "relative_path": str(row.get("candidate_id") or ""),
                "snippet": (
                    str(row.get("predicate") or "")
                    + " = "
                    + str(row.get("value") or "")
                ),
            },
            {
                "source": "MEMORY",
                "title": "ETAT",
                "note_type": str(row.get("state") or "?").upper(),
                "relative_path": "",
                "snippet": (
                    "duplicate_of="
                    + str(row.get("duplicate_of") or "-")
                    + " | conflicts="
                    + str(len(row.get("conflict_with") or []))
                ),
            },
            {
                "source": "MEMORY",
                "title": "PROVENANCE",
                "note_type": "SOURCE",
                "relative_path": "",
                "snippet": (
                    str(prov.get("source_kind") or "?")
                    + " | "
                    + str(prov.get("source_ref") or "?")
                    + " | confiance "
                    + str(prov.get("confidence") or 0)
                ),
            },
            {
                "source": "MEMORY",
                "title": "NON CONSOLIDE",
                "note_type": "GARDE-FOU",
                "relative_path": "",
                "snippet": "Candidat local uniquement. Aucune ecriture dans la memoire live ni dans les poids du modele.",
            },
        ]

    elif capability == "learning.list_candidates":
        title = "CANDIDATS MEMOIRE"
        rows = result.get("items") if isinstance(result.get("items"), list) else []
        items = [_candidate_item(x) for x in rows if isinstance(x, Mapping)]
        if not items:
            items = [{
                "source": "MEMORY",
                "title": "AUCUN CANDIDAT",
                "note_type": "INFO",
                "relative_path": "",
                "snippet": "Aucun candidat memoire local.",
            }]

    elif capability == "learning.list_conflicts":
        title = "CONFLITS MEMOIRE"
        rows = result.get("items") if isinstance(result.get("items"), list) else []
        items = [_candidate_item(x) for x in rows if isinstance(x, Mapping)]
        if not items:
            items = [{
                "source": "MEMORY",
                "title": "AUCUN CONFLIT",
                "note_type": "PASS",
                "relative_path": "",
                "snippet": "Aucun conflit memoire non resolu.",
            }]

    elif capability == "learning.consolidation_plan":
        title = "PLAN DE CONSOLIDATION"
        rows = result.get("items") if isinstance(result.get("items"), list) else []
        items = [_candidate_item(x) for x in rows if isinstance(x, Mapping)]
        if not items:
            items = [{
                "source": "MEMORY",
                "title": "AUCUN CANDIDAT APPROUVE",
                "note_type": "INFO",
                "relative_path": "",
                "snippet": "R2 n'expose encore aucune capability d'approbation. Aucune consolidation n'est possible.",
            }]

    return {
        "schema": "aura.personal-result.v123",
        "kind": "memory",
        "provider_id": "controlled.learning",
        "capability_id": capability,
        "status": str(getattr(reply, "status", "") or ""),
        "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
        "title": title,
        "count": len(items),
        "items": items[:50],
        "fallback_text": str(getattr(reply, "text", "") or ""),
        "source": "MEMORY",
        "sources": ["MEMORY"],
        "l170_controlled_learning": True,
        "live_memory_mutation_performed": False,
        "model_weight_mutation_performed": False,
    }

# AURA_L170_R3_EXPLICIT_APPROVAL_CONTROLLED_CONSOLIDATION
_AURA_L170_R3_PREVIOUS_BUILD_RESULT = build_personal_result_payload_v123

def build_personal_result_payload_v123(reply: Any, request: Any = None) -> dict[str, Any]:
    capability = str(
        getattr(request, "capability_id", "")
        or getattr(reply, "capability_id", "")
        or ""
    )
    if capability not in {
        "learning.approve_candidate",
        "learning.resolve_conflict",
        "learning.consolidate_candidate",
        "learning.list_consolidated",
    }:
        return _AURA_L170_R3_PREVIOUS_BUILD_RESULT(reply, request)

    raw = getattr(reply, "payload", None)
    output = raw if isinstance(raw, Mapping) else {}
    result = output.get("l170_result") if isinstance(output, Mapping) else {}
    result = result if isinstance(result, Mapping) else {}

    if capability == "learning.approve_candidate":
        title = "CANDIDAT APPROUVE"
        items = [
            {
                "source": "MEMORY",
                "title": str(result.get("subject") or "Candidat"),
                "note_type": "APPROUVE",
                "relative_path": str(result.get("candidate_id") or ""),
                "snippet": str(result.get("predicate") or "") + " = " + str(result.get("value") or ""),
            },
            {
                "source": "MEMORY",
                "title": "APPROBATION EXPLICITE",
                "note_type": "GARDE-FOU",
                "relative_path": "",
                "snippet": "Validation utilisateur recue. Consolidation encore separee.",
            },
        ]
    elif capability == "learning.resolve_conflict":
        title = "CONFLIT MEMOIRE RESOLU"
        items = [
            {
                "source": "MEMORY",
                "title": str(result.get("subject") or "Candidat"),
                "note_type": str(result.get("state") or "").upper(),
                "relative_path": str(result.get("candidate_id") or ""),
                "snippet": str(result.get("predicate") or "") + " = " + str(result.get("value") or ""),
            },
            {
                "source": "MEMORY",
                "title": "RESOLUTION",
                "note_type": "EXPLICITE",
                "relative_path": "",
                "snippet": str(result.get("conflict_resolution") or ""),
            },
        ]
    elif capability == "learning.consolidate_candidate":
        title = "MEMOIRE CONSOLIDEE"
        candidate = result.get("candidate") if isinstance(result.get("candidate"), Mapping) else {}
        memory = result.get("memory") if isinstance(result.get("memory"), Mapping) else {}
        prov = memory.get("provenance") if isinstance(memory.get("provenance"), Mapping) else {}
        items = [
            {
                "source": "MEMORY",
                "title": str(memory.get("subject") or "Souvenir"),
                "note_type": "CONSOLIDE",
                "relative_path": str(memory.get("memory_id") or ""),
                "snippet": str(memory.get("predicate") or "") + " = " + str(memory.get("value") or ""),
            },
            {
                "source": "MEMORY",
                "title": "PROVENANCE CONSERVEE",
                "note_type": "SOURCE",
                "relative_path": "",
                "snippet": str(prov.get("source_kind") or "?") + " | " + str(prov.get("source_ref") or "?"),
            },
            {
                "source": "MEMORY",
                "title": "ECRITURE CONTROLEE",
                "note_type": "SECURITE",
                "relative_path": str(candidate.get("candidate_id") or ""),
                "snippet": "Registre local L170 uniquement. Injection backend live=false | poids modele=false.",
            },
        ]
    else:
        title = "MEMOIRES CONSOLIDEES"
        items = []
        for row in result.get("items") or []:
            if isinstance(row, Mapping):
                items.append({
                    "source": "MEMORY",
                    "title": str(row.get("subject") or "Souvenir"),
                    "note_type": "CONSOLIDE",
                    "relative_path": str(row.get("memory_id") or ""),
                    "snippet": str(row.get("predicate") or "") + " = " + str(row.get("value") or ""),
                })
        if not items:
            items = [{
                "source": "MEMORY",
                "title": "AUCUN SOUVENIR CONSOLIDE",
                "note_type": "INFO",
                "relative_path": "",
                "snippet": "Le registre d'apprentissage controle est vide.",
            }]

    return {
        "schema": "aura.personal-result.v123",
        "kind": "memory",
        "provider_id": "controlled.learning",
        "capability_id": capability,
        "status": str(getattr(reply, "status", "") or ""),
        "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
        "title": title,
        "count": len(items),
        "items": items[:50],
        "fallback_text": str(getattr(reply, "text", "") or ""),
        "source": "MEMORY",
        "sources": ["MEMORY"],
        "l170_controlled_learning": True,
        "live_memory_backend_injection_performed": False,
        "model_weight_mutation_performed": False,
    }

# AURA_M180_R2_LOCAL_MEDIA_RESULTS
_AURA_M180_R2_PREVIOUS_BUILD_RESULT = build_personal_result_payload_v123


def build_personal_result_payload_v123(reply: Any, request: Any = None) -> dict[str, Any]:
    provider = str(getattr(request, "provider_id", "") or "")
    capability = str(
        getattr(request, "capability_id", "")
        or getattr(reply, "capability_id", "")
        or ""
    )
    if provider != "music.media-center" and not capability.startswith("media."):
        return _AURA_M180_R2_PREVIOUS_BUILD_RESULT(reply, request)

    raw = getattr(reply, "payload", None)
    output = raw if isinstance(raw, Mapping) else {}
    result = output.get("m180_result") if isinstance(output, Mapping) else {}
    result = result if isinstance(result, Mapping) else {}

    items = []
    title = "MEDIA CENTER"

    def media_item(row, note_type="MEDIA"):
        return {
            "source": "MEDIA",
            "title": str(row.get("title") or "Media"),
            "note_type": note_type,
            "relative_path": str(row.get("path") or row.get("media_id") or ""),
            "snippet": (
                (str(row.get("artist") or "") + " | " if row.get("artist") else "")
                + str(row.get("media_type") or "")
                + (" | " + str(row.get("album") or "") if row.get("album") else "")
            ),
        }

    if capability == "media.catalog_summary":
        title = "BIBLIOTHEQUE MEDIA"
        items = [
            {
                "source": "MEDIA",
                "title": "TOTAL",
                "note_type": "CATALOGUE",
                "relative_path": "",
                "snippet": str(result.get("total") or 0) + " medias indexes",
            },
            {
                "source": "MEDIA",
                "title": "AUDIO",
                "note_type": "CATALOGUE",
                "relative_path": "",
                "snippet": str(result.get("audio") or 0) + " fichiers audio",
            },
            {
                "source": "MEDIA",
                "title": "VIDEO",
                "note_type": "CATALOGUE",
                "relative_path": "",
                "snippet": str(result.get("video") or 0) + " fichiers video",
            },
            {
                "source": "MEDIA",
                "title": "INDEX LOCAL",
                "note_type": "LECTURE SEULE",
                "relative_path": "",
                "snippet": "Scan local en lecture seule. Aucune modification de fichier.",
            },
        ]

    elif capability == "media.search":
        title = "RECHERCHE MEDIA"
        rows = result.get("items") if isinstance(result.get("items"), list) else []
        items = [media_item(x, "RESULTAT") for x in rows if isinstance(x, Mapping)]
        if not items:
            items = [{
                "source": "MEDIA",
                "title": "AUCUN RESULTAT",
                "note_type": "INFO",
                "relative_path": "",
                "snippet": "Aucun media correspondant dans l'index local.",
            }]

    elif capability == "media.smart_queue":
        title = "FILE MEDIA"
        rows = result.get("items") if isinstance(result.get("items"), list) else []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            card = media_item(row, "QUEUE")
            card["snippet"] += (
                " | score "
                + str(row.get("queue_score") or 0)
                + " | "
                + ", ".join(str(x) for x in (row.get("reasons") or []))
            )
            items.append(card)
        if not items:
            items = [{
                "source": "MEDIA",
                "title": "FILE VIDE",
                "note_type": "INFO",
                "relative_path": "",
                "snippet": "Aucun media exploitable pour cette selection.",
            }]

    elif capability == "media.playlist_proposal":
        title = "PLAYLIST PROPOSEE"
        rows = result.get("items") if isinstance(result.get("items"), list) else []
        items = [media_item(x, "PLAYLIST") for x in rows if isinstance(x, Mapping)]
        items.append({
            "source": "MEDIA",
            "title": "AUCUNE ECRITURE EXTERNE",
            "note_type": "GARDE-FOU",
            "relative_path": "",
            "snippet": "Proposition locale uniquement. Aucun service media externe n'a ete modifie.",
        })

    elif capability == "media.playback_intent":
        title = "INTENTION DE LECTURE"
        media = result.get("media") if isinstance(result.get("media"), Mapping) else {}
        if media:
            items.append(media_item(media, "A LIRE"))
        items.extend([
            {
                "source": "MEDIA",
                "title": "APPROBATION REQUISE",
                "note_type": "GARDE-FOU",
                "relative_path": "",
                "snippet": "Une confirmation explicite sera requise avant tout futur controle du lecteur.",
            },
            {
                "source": "MEDIA",
                "title": "AUCUNE LECTURE EFFECTUEE",
                "note_type": "SECURITE",
                "relative_path": "",
                "snippet": "player_mutation=false | external_account_mutation=false",
            },
        ])

    return {
        "schema": "aura.personal-result.v123",
        "kind": "media",
        "provider_id": "music.media-center",
        "capability_id": capability,
        "status": str(getattr(reply, "status", "") or ""),
        "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
        "title": title,
        "count": len(items),
        "items": items[:50],
        "fallback_text": str(getattr(reply, "text", "") or ""),
        "source": "MEDIA",
        "sources": ["MEDIA"],
        "m180_music_media_center": True,
        "player_mutation_performed": False,
        "external_account_mutation_performed": False,
    }

# AURA_M180_R3_CONTROLLED_LOCAL_PLAYER
_AURA_M180_R3_PREVIOUS_BUILD_RESULT = build_personal_result_payload_v123


def build_personal_result_payload_v123(reply: Any, request: Any = None) -> dict[str, Any]:
    capability = str(
        getattr(request, "capability_id", "")
        or getattr(reply, "capability_id", "")
        or ""
    )
    if capability not in {
        "media.list_items",
        "media.play_confirmed",
        "media.player_status",
    }:
        return _AURA_M180_R3_PREVIOUS_BUILD_RESULT(reply, request)

    raw = getattr(reply, "payload", None)
    output = raw if isinstance(raw, Mapping) else {}
    result = output.get("m180_result") if isinstance(output, Mapping) else {}
    result = result if isinstance(result, Mapping) else {}

    items = []

    if capability == "media.list_items":
        title = "MEDIAS LOCAUX"
        rows = result.get("items") if isinstance(result.get("items"), list) else []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            items.append({
                "source": "MEDIA",
                "title": str(row.get("title") or "Media"),
                "note_type": str(row.get("media_type") or "MEDIA").upper(),
                "relative_path": str(row.get("path") or row.get("media_id") or ""),
                "snippet": (
                    (str(row.get("artist") or "") + " | " if row.get("artist") else "")
                    + str(row.get("album") or "")
                ).strip(" |"),
            })
        if not items:
            items = [{
                "source": "MEDIA",
                "title": "INDEX VIDE",
                "note_type": "INFO",
                "relative_path": "",
                "snippet": "Ajoute un dossier avec ADD_AURA_MEDIA_FOLDER.bat puis rafraichis l'index.",
            }]

    elif capability == "media.play_confirmed":
        title = "LECTURE LOCALE"
        items = [
            {
                "source": "MEDIA",
                "title": str(result.get("title") or "Media"),
                "note_type": "LECTURE CONFIRMEE",
                "relative_path": str(result.get("path") or ""),
                "snippet": (
                    str(result.get("media_type") or "")
                    + " | backend "
                    + str(result.get("backend") or "?")
                ),
            },
            {
                "source": "MEDIA",
                "title": "CONFIRMATION EXPLICITE",
                "note_type": "GARDE-FOU",
                "relative_path": "",
                "snippet": "La lecture a ete lancee uniquement apres la commande explicite de confirmation.",
            },
            {
                "source": "MEDIA",
                "title": "FICHIERS INCHANGES",
                "note_type": "SECURITE",
                "relative_path": "",
                "snippet": "delete=false | move=false | rename=false | external_account_mutation=false",
            },
        ]

    else:
        title = "STATUT LECTEUR MEDIA"
        if not bool(result.get("session_present")):
            items = [{
                "source": "MEDIA",
                "title": "AUCUNE SESSION",
                "note_type": "IDLE",
                "relative_path": "",
                "snippet": "Aucune lecture locale controlee n'a encore ete enregistree.",
            }]
        else:
            items = [
                {
                    "source": "MEDIA",
                    "title": str(result.get("title") or "Media"),
                    "note_type": str(result.get("state") or "").upper(),
                    "relative_path": str(result.get("path") or ""),
                    "snippet": (
                        "backend "
                        + str(result.get("backend") or "?")
                        + " | pid "
                        + str(result.get("pid") or "-")
                    ),
                },
                {
                    "source": "MEDIA",
                    "title": "SESSION CONTROLEE",
                    "note_type": "SECURITE",
                    "relative_path": "",
                    "snippet": (
                        "confirmation=true | filesystem_mutation=false | "
                        "external_account_mutation=false"
                    ),
                },
            ]

    return {
        "schema": "aura.personal-result.v123",
        "kind": "media",
        "provider_id": "music.media-center",
        "capability_id": capability,
        "status": str(getattr(reply, "status", "") or ""),
        "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
        "title": title,
        "count": len(items),
        "items": items[:50],
        "fallback_text": str(getattr(reply, "text", "") or ""),
        "source": "MEDIA",
        "sources": ["MEDIA"],
        "m180_music_media_center": True,
        "controlled_local_player": True,
        "filesystem_mutation_performed": False,
        "external_account_mutation_performed": False,
    }

# AURA_M180_UI1_MUSIC_PLAYER_PANEL
_AURA_M180_UI1_PREVIOUS_BUILD_RESULT = build_personal_result_payload_v123

def build_personal_result_payload_v123(reply: Any, request: Any = None) -> dict[str, Any]:
    capability = str(
        getattr(request, "capability_id", "")
        or getattr(reply, "capability_id", "")
        or ""
    )
    if capability != "media.player_key":
        return _AURA_M180_UI1_PREVIOUS_BUILD_RESULT(reply, request)
    raw = getattr(reply, "payload", None)
    output = raw if isinstance(raw, Mapping) else {}
    result = output.get("m180_result") if isinstance(output, Mapping) else {}
    result = result if isinstance(result, Mapping) else {}
    action = str(result.get("action") or "").upper()
    return {
        "schema": "aura.personal-result.v123",
        "kind": "media",
        "provider_id": "music.media-center",
        "capability_id": capability,
        "status": str(getattr(reply, "status", "") or ""),
        "receipt_id": str(getattr(reply, "receipt_id", "") or ""),
        "title": "CONTROLE MUSIQUE",
        "count": 1,
        "items": [{
            "source": "MEDIA",
            "title": action or "CONTROLE",
            "note_type": "LECTEUR LOCAL",
            "relative_path": "",
            "snippet": "Commande media locale envoyee. Fichiers inchanges | compte externe inchange.",
        }],
        "fallback_text": str(getattr(reply, "text", "") or ""),
        "source": "MEDIA",
        "sources": ["MEDIA"],
        "m180_music_media_center": True,
        "music_player_ui": True,
        "filesystem_mutation_performed": False,
        "external_account_mutation_performed": False,
    }

# AURA_M180_UI3_PC_BROWSER
_AURA_M180_UI3_PREVIOUS_BUILD_RESULT = build_personal_result_payload_v123

def build_personal_result_payload_v123(reply: Any, request: Any = None) -> dict[str, Any]:
    capability = str(
        getattr(request,"capability_id","")
        or getattr(reply,"capability_id","")
        or ""
    )
    if capability not in {
        "media.pick_local_music",
        "media.pick_local_playlist",
        "media.pick_local_folder",
    }:
        return _AURA_M180_UI3_PREVIOUS_BUILD_RESULT(reply, request)

    raw = getattr(reply,"payload",None)
    output = raw if isinstance(raw,Mapping) else {}
    result = output.get("m180_result") if isinstance(output,Mapping) else {}
    result = result if isinstance(result,Mapping) else {}
    selected = (
        result.get("selected")
        if isinstance(result.get("selected"),list)
        else []
    )

    title = (
        "MUSIQUE DEPUIS LE PC"
        if capability=="media.pick_local_music"
        else "PLAYLIST DEPUIS LE PC"
        if capability=="media.pick_local_playlist"
        else "DOSSIER MEDIA DU PC"
    )

    items=[]
    if result.get("cancelled"):
        items=[{
            "source":"MEDIA",
            "title":"SÉLECTION ANNULÉE",
            "note_type":"INFO",
            "relative_path":"",
            "snippet":"Aucun fichier n'a été ajouté.",
        }]
    elif not selected:
        items=[{
            "source":"MEDIA",
            "title":"AUCUN MEDIA COMPATIBLE",
            "note_type":"INFO",
            "relative_path":str(result.get("source_path") or ""),
            "snippet":"Aucun fichier audio/vidéo compatible trouvé.",
        }]
    else:
        for row in selected[:20]:
            if not isinstance(row,Mapping):
                continue
            items.append({
                "source":"MEDIA",
                "title":str(row.get("title") or "Media"),
                "note_type":str(row.get("media_type") or "MEDIA").upper(),
                "relative_path":str(row.get("path") or ""),
                "snippet":(
                    ((str(row.get("artist") or "")+" | ") if row.get("artist") else "")
                    + "Ajouté à la bibliothèque locale AURA"
                ),
            })

    return {
        "schema":"aura.personal-result.v123",
        "kind":"media",
        "provider_id":"music.media-center",
        "capability_id":capability,
        "status":str(getattr(reply,"status","") or ""),
        "receipt_id":str(getattr(reply,"receipt_id","") or ""),
        "title":title,
        "count":len(items),
        "items":items,
        "fallback_text":str(getattr(reply,"text","") or ""),
        "source":"MEDIA",
        "sources":["MEDIA"],
        "native_pc_browser":True,
        "selected_count":int(result.get("selected_count") or 0),
        "new_index_items":int(result.get("new_index_items") or 0),
        "media_file_mutation_performed":False,
        "external_account_mutation_performed":False,
    }
