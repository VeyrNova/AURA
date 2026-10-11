from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4
from .models import SystemActionRequest, SystemActionType
from .service import SystemControlService
from aura_native.google.models import PreparedAction

@dataclass(frozen=True)
class WindowTarget:
    hwnd: int; pid: int; title: str

@dataclass(frozen=True)
class TargetResolution:
    status: str; target: WindowTarget | None = None; candidates: int = 0

class WindowTargetResolver:
    def __init__(self, service: SystemControlService): self.service=service
    @staticmethod
    def _norm(value): return " ".join(str(value or "").casefold().split())
    def resolve(self, title: str) -> TargetResolution:
        query=self._norm(title)
        if not query: return TargetResolution("INVALID",candidates=0)
        result=self.service.execute(SystemActionRequest(SystemActionType.DISCOVER_WINDOWS))
        rows=result.data or []
        matches=[x for x in rows if self._norm(x.get("title")) == query]
        if not matches: return TargetResolution("NOT_FOUND",candidates=0)
        if len(matches)>1: return TargetResolution("AMBIGUOUS",candidates=len(matches))
        x=matches[0]; return TargetResolution("RESOLVED",WindowTarget(int(x["hwnd"]),int(x["pid"]),str(x.get("title") or title)),1)

class SystemControlProductService:
    ACTIONS={"PC_MINIMIZE_WINDOW":("system.window.minimize",SystemActionType.MINIMIZE_WINDOW,"Minimiser"),"PC_MAXIMIZE_WINDOW":("system.window.maximize",SystemActionType.MAXIMIZE_WINDOW,"Maximiser"),"PC_FOCUS_WINDOW":("system.window.focus",SystemActionType.FOCUS_WINDOW,"Activer")}
    def __init__(self, control: SystemControlService, repository): self.control=control; self.repository=repository; self.resolver=WindowTargetResolver(control)
    READ_ACTIONS={"PC_LIST_WINDOWS":SystemActionType.DISCOVER_WINDOWS,"PC_LIST_PROCESSES":SystemActionType.DISCOVER_PROCESSES,"PC_GET_FOREGROUND_WINDOW":SystemActionType.GET_FOREGROUND_WINDOW}
    def read(self, intent):
        action=self.READ_ACTIONS.get(intent.intent)
        if action is None: return {"status":"UNAVAILABLE","intent":intent.intent,"count":0,"items":[],"summary":"Commande indisponible."}
        result=self.control.execute(SystemActionRequest(action))
        if result.status != "SUCCESS": return {"status":result.status,"intent":intent.intent,"count":0,"items":[],"summary":"Lecture système indisponible."}
        data=result.data
        if action is SystemActionType.GET_FOREGROUND_WINDOW:
            item = data if isinstance(data,dict) else None
            items=[] if not item else [{"title":str(item.get("title") or ""),"image_name":str(item.get("image_name") or "")}]
            title=items[0].get("title") if items else ""
            return {"status":"SUCCESS","intent":intent.intent,"count":len(items),"items":items,"summary":("La fenêtre au premier plan est : « %s »" % title) if title else "Aucune fenêtre au premier plan exploitable."}
        rows=[]
        for row in list(data or []):
            if action is SystemActionType.DISCOVER_WINDOWS:
                title = row.get('title','') if isinstance(row,dict) else getattr(row,'title','')
                rows.append({"title":str(title),"image_name":""})
            else:
                image_name = row.get('image_name','') if isinstance(row,dict) else getattr(row,'image_name','')
                rows.append({"image_name":str(image_name)})
        rows=rows[:50]
        label="fenêtre(s)" if action is SystemActionType.DISCOVER_WINDOWS else "processus"
        return {"status":"SUCCESS","intent":intent.intent,"count":len(data or []),"items":rows,"summary":f"{len(data or [])} {label} détecté(s)."}
    def prepare(self, intent):
        action_type,_,verb=self.ACTIONS[intent.intent]
        resolution=self.resolver.resolve(intent.slots.get("title"))
        if resolution.status != "RESOLVED": return resolution, None
        t=resolution.target
        payload={"hwnd":t.hwnd,"pid":t.pid,"title":t.title,"operation":action_type,"source":intent.source,"request_id":intent.request_id}
        return resolution, self.repository.create(PreparedAction(str(uuid4()),"system_control",action_type,payload,f"{verb} la fenêtre « {t.title} »",True))
    def execute_prepared_action(self, action_id):
        action=self.repository.get(action_id)
        if not action or action.state != "confirmed": raise ValueError("confirmation_required")
        mapping={v[0]:v[1] for v in self.ACTIONS.values()}; typ=mapping.get(action.action_type)
        if typ is None: raise ValueError("unsupported_action_type")
        p=action.payload; req=SystemActionRequest(typ,{"hwnd":int(p.get("hwnd",0)),"pid":int(p.get("pid",0)),"title":str(p.get("title",""))},confirmed=True)
        result=self.control.execute(req)
        if result.status != "SUCCESS": raise ValueError(result.status.lower())
        self.repository.mark_executed(action_id); return result
