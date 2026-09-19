
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, asdict, replace
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable
from integrations.registry import IntegrationCapability, IntegrationManifest, IntegrationRequest

READ_CAPABILITIES = ("email.search","email.read","email.read_thread","email.list_attachments")
WRITE_CAPABILITIES = ("email.create_draft","email.send","email.reply","email.forward","email.archive","email.trash","email.label")
CONFIRMATION_CAPABILITIES = ("email.send","email.reply","email.forward","email.archive","email.trash","email.label")
EMAIL_CAPABILITIES = READ_CAPABILITIES + WRITE_CAPABILITIES

class EmailProviderError(RuntimeError): pass
class EmailValidationError(EmailProviderError): pass
class EmailLookupError(EmailProviderError): pass

def _now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def _sid(prefix,*parts):
    raw=json.dumps(parts,sort_keys=True,default=str,separators=(",",":")).encode()
    return prefix+hashlib.sha256(raw).hexdigest()[:24]

@dataclass(frozen=True)
class EmailAddress:
    address: str
    display_name: Optional[str]=None
    def __post_init__(self):
        if "@" not in self.address or not self.address.strip(): raise EmailValidationError("invalid email address")
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class EmailAttachment:
    attachment_id: str
    filename: str
    content_type: str
    size_bytes: int
    inline: bool=False
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class EmailMessage:
    message_id: str
    thread_id: str
    subject: str
    sender: EmailAddress
    to: tuple[EmailAddress,...]
    date: str
    body_text: str
    cc: tuple[EmailAddress,...]=()
    bcc: tuple[EmailAddress,...]=()
    labels: tuple[str,...]=()
    attachments: tuple[EmailAttachment,...]=()
    draft: bool=False
    def to_dict(self):
        return {
            "message_id":self.message_id,"thread_id":self.thread_id,"subject":self.subject,
            "sender":self.sender.to_dict(),"to":[x.to_dict() for x in self.to],"date":self.date,
            "body_text":self.body_text,"cc":[x.to_dict() for x in self.cc],"bcc":[x.to_dict() for x in self.bcc],
            "labels":list(self.labels),"attachments":[x.to_dict() for x in self.attachments],"draft":self.draft,
        }

@dataclass(frozen=True)
class EmailThread:
    thread_id: str
    messages: tuple[EmailMessage,...]
    def to_dict(self): return {"thread_id":self.thread_id,"messages":[x.to_dict() for x in self.messages]}

@dataclass(frozen=True)
class EmailDraft:
    draft_id: str
    to: tuple[EmailAddress,...]
    subject: str
    body_text: str
    cc: tuple[EmailAddress,...]=()
    bcc: tuple[EmailAddress,...]=()
    thread_id: Optional[str]=None
    attachment_refs: tuple[str,...]=()
    def to_dict(self):
        return {"draft_id":self.draft_id,"to":[x.to_dict() for x in self.to],"subject":self.subject,
                "body_text":self.body_text,"cc":[x.to_dict() for x in self.cc],"bcc":[x.to_dict() for x in self.bcc],
                "thread_id":self.thread_id,"attachment_refs":list(self.attachment_refs)}

@dataclass(frozen=True)
class EmailQuery:
    text: str=""
    sender: Optional[str]=None
    subject: Optional[str]=None
    labels: tuple[str,...]=()
    unread_only: bool=False
    limit: int=50

@dataclass(frozen=True)
class EmailResult:
    operation: str
    ok: bool
    message_ids: tuple[str,...]=()
    thread_ids: tuple[str,...]=()
    draft_id: Optional[str]=None
    detail: Optional[str]=None
    def to_dict(self): return asdict(self)

@runtime_checkable
class EmailBackend(Protocol):
    def search_messages(self, query: EmailQuery) -> Sequence[EmailMessage]: ...
    def get_message(self, message_id: str) -> EmailMessage: ...
    def get_thread(self, thread_id: str) -> EmailThread: ...
    def list_attachments(self, message_id: str) -> Sequence[EmailAttachment]: ...
    def create_draft(self, draft: EmailDraft) -> EmailDraft: ...
    def send_message(self, **kwargs) -> EmailMessage: ...
    def reply_message(self, **kwargs) -> EmailMessage: ...
    def forward_message(self, **kwargs) -> EmailMessage: ...
    def archive_message(self, message_id: str) -> EmailResult: ...
    def trash_message(self, message_id: str) -> EmailResult: ...
    def set_labels(self, **kwargs) -> EmailResult: ...
    def health_snapshot(self) -> Mapping[str,Any]: ...

def _addr(v):
    if isinstance(v, EmailAddress): return v
    if isinstance(v,str): return EmailAddress(v)
    if isinstance(v,Mapping): return EmailAddress(str(v.get("address") or ""), v.get("display_name"))
    raise EmailValidationError("invalid address")
def _addrs(v):
    if v is None: return ()
    if isinstance(v,(str,Mapping,EmailAddress)): v=[v]
    return tuple(_addr(x) for x in v)

def _cap(cid, risk, confirm, effect):
    return IntegrationCapability(
        capability_id=cid, action=cid, description=cid, risk_tier=risk,
        requires_confirmation=confirm, side_effect_class=effect, evidence_required=True
    )

EMAIL_MANIFEST = IntegrationManifest(
    provider_id="email.provider",
    display_name="AURA Email Provider",
    provider_version="0.9.1-contract",
    capabilities=(
        _cap("email.search","low",False,"read"),
        _cap("email.read","low",False,"read"),
        _cap("email.read_thread","low",False,"read"),
        _cap("email.list_attachments","low",False,"read"),
        _cap("email.create_draft","low",False,"draft"),
        _cap("email.send","high",True,"external_write"),
        _cap("email.reply","high",True,"external_write"),
        _cap("email.forward","high",True,"external_write"),
        _cap("email.archive","medium",True,"mailbox_write"),
        _cap("email.trash","high",True,"mailbox_write"),
        _cap("email.label","medium",True,"mailbox_write"),
    ),
    auth_kind="external-provider-owned",
    metadata={"provider_neutral":True,"real_network_connection":False},
)

class EmailProvider:
    def __init__(self, backend: EmailBackend):
        if not isinstance(backend, EmailBackend): raise EmailValidationError("invalid backend")
        self.backend=backend
    @property
    def manifest(self): return EMAIL_MANIFEST
    def health_snapshot(self): return dict(self.backend.health_snapshot())
    def execute(self, request: IntegrationRequest):
        c=request.capability_id; p=dict(request.params or {})
        if c=="email.search":
            q=p.get("query") or {}
            if isinstance(q,EmailQuery): query=q
            else: query=EmailQuery(
                text=str(q.get("text","")),sender=q.get("sender"),subject=q.get("subject"),
                labels=tuple(q.get("labels") or ()),unread_only=bool(q.get("unread_only",False)),
                limit=int(q.get("limit",50))
            )
            return {"messages":[m.to_dict() for m in self.backend.search_messages(query)],"evidence_refs":[]}
        if c=="email.read":
            return {"message":self.backend.get_message(str(p.get("message_id") or "")).to_dict(),"evidence_refs":[]}
        if c=="email.read_thread":
            return {"thread":self.backend.get_thread(str(p.get("thread_id") or "")).to_dict(),"evidence_refs":[]}
        if c=="email.list_attachments":
            return {"attachments":[a.to_dict() for a in self.backend.list_attachments(str(p.get("message_id") or ""))],"evidence_refs":[]}
        if c=="email.create_draft":
            d=EmailDraft(
                draft_id=_sid("drf_",p.get("to"),p.get("subject"),p.get("body_text"),p.get("thread_id")),
                to=_addrs(p.get("to")),subject=str(p.get("subject") or ""),body_text=str(p.get("body_text") or ""),
                cc=_addrs(p.get("cc")),bcc=_addrs(p.get("bcc")),thread_id=p.get("thread_id"),
                attachment_refs=tuple(str(x) for x in (p.get("attachment_refs") or ())),
            )
            return {"draft":self.backend.create_draft(d).to_dict(),"evidence_refs":[]}
        if c=="email.send":
            m=self.backend.send_message(
                draft_id=p.get("draft_id"),to=_addrs(p.get("to")),subject=str(p.get("subject") or ""),
                body_text=str(p.get("body_text") or ""),cc=_addrs(p.get("cc")),bcc=_addrs(p.get("bcc"))
            ); return {"message":m.to_dict(),"evidence_refs":[]}
        if c=="email.reply":
            m=self.backend.reply_message(message_id=str(p.get("message_id") or ""),body_text=str(p.get("body_text") or ""),reply_all=bool(p.get("reply_all",False)))
            return {"message":m.to_dict(),"evidence_refs":[]}
        if c=="email.forward":
            m=self.backend.forward_message(message_id=str(p.get("message_id") or ""),to=_addrs(p.get("to")),body_text=str(p.get("body_text") or ""))
            return {"message":m.to_dict(),"evidence_refs":[]}
        if c=="email.archive":
            return {"result":self.backend.archive_message(str(p.get("message_id") or "")).to_dict(),"evidence_refs":[]}
        if c=="email.trash":
            return {"result":self.backend.trash_message(str(p.get("message_id") or "")).to_dict(),"evidence_refs":[]}
        if c=="email.label":
            return {"result":self.backend.set_labels(message_id=str(p.get("message_id") or ""),add=tuple(p.get("add") or ()),remove=tuple(p.get("remove") or ())).to_dict(),"evidence_refs":[]}
        raise EmailValidationError("unsupported capability")

class SyntheticEmailBackend:
    def __init__(self,messages=()):
        self.messages={m.message_id:m for m in messages}; self.drafts={}; self.calls=[]; self.counter=0
    def _msg(self,mid):
        m=self.messages.get(mid)
        if m is None: raise EmailLookupError("message not found")
        return m
    def search_messages(self,q):
        self.calls.append("search_messages")
        out=[]
        for m in self.messages.values():
            hay=(m.subject+"\n"+m.body_text).casefold()
            if q.text and q.text.casefold() not in hay: continue
            if q.sender and q.sender.casefold() not in m.sender.address.casefold(): continue
            if q.subject and q.subject.casefold() not in m.subject.casefold(): continue
            if q.labels and not set(q.labels).issubset(set(m.labels)): continue
            if q.unread_only and "UNREAD" not in m.labels: continue
            out.append(m)
        return tuple(out[:q.limit])
    def get_message(self,mid): self.calls.append("get_message"); return self._msg(mid)
    def get_thread(self,tid):
        self.calls.append("get_thread"); msgs=tuple(m for m in self.messages.values() if m.thread_id==tid)
        if not msgs: raise EmailLookupError("thread not found")
        return EmailThread(tid,msgs)
    def list_attachments(self,mid): self.calls.append("list_attachments"); return self._msg(mid).attachments
    def create_draft(self,d): self.calls.append("create_draft"); self.drafts[d.draft_id]=d; return d
    def _new(self,subject,to,body,thread=None,attachments=()):
        self.counter+=1; mid=_sid("msg_",self.counter,subject,body); tid=thread or _sid("thr_",mid,subject)
        m=EmailMessage(mid,tid,subject,EmailAddress("aura.synthetic@example.invalid","AURA Synthetic"),tuple(to),_now(),body,labels=("SENT",),attachments=tuple(attachments))
        self.messages[mid]=m; return m
    def send_message(self,**k):
        self.calls.append("send_message"); to=tuple(k.get("to") or ())
        if not to: raise EmailValidationError("send requires recipient")
        return self._new(k.get("subject",""),to,k.get("body_text",""))
    def reply_message(self,**k):
        self.calls.append("reply_message"); src=self._msg(k["message_id"])
        return self._new("Re: "+src.subject,(src.sender,),k.get("body_text",""),thread=src.thread_id)
    def forward_message(self,**k):
        self.calls.append("forward_message"); src=self._msg(k["message_id"]); to=tuple(k.get("to") or ())
        if not to: raise EmailValidationError("forward requires recipient")
        return self._new("Fwd: "+src.subject,to,k.get("body_text",""),attachments=src.attachments)
    def archive_message(self,mid):
        self.calls.append("archive_message"); m=self._msg(mid); labs=set(m.labels); labs.discard("INBOX"); labs.add("ARCHIVE"); self.messages[mid]=replace(m,labels=tuple(sorted(labs)))
        return EmailResult("archive_message",True,(mid,))
    def trash_message(self,mid):
        self.calls.append("trash_message"); m=self._msg(mid); labs=set(m.labels); labs.discard("INBOX"); labs.add("TRASH"); self.messages[mid]=replace(m,labels=tuple(sorted(labs)))
        return EmailResult("trash_message",True,(mid,))
    def set_labels(self,**k):
        self.calls.append("set_labels"); mid=k["message_id"]; m=self._msg(mid); labs=set(m.labels); labs.update(k.get("add") or ()); labs.difference_update(k.get("remove") or ())
        self.messages[mid]=replace(m,labels=tuple(sorted(labs))); return EmailResult("set_labels",True,(mid,))
    def health_snapshot(self): return {"available":True,"health_state":"healthy"}
