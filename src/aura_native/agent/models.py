from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from uuid import uuid4
from datetime import datetime, timezone


class AgentState(str, Enum):
    IDLE="idle"; QUEUED="queued"; THINKING="thinking"; RESPONDING="responding"; COMPLETED="completed"; CANCELLED="cancelled"; ERROR="error"; UNAVAILABLE="unavailable"


ACTIVE_STATES=frozenset((AgentState.QUEUED,AgentState.THINKING,AgentState.RESPONDING))


def utc_now(): return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class AgentRequest:
    request_id: str=field(default_factory=lambda:str(uuid4()))
    session_id: str=""
    conversation_id: str=""
    user_message_id: str=""
    prompt: str=""
    created_at: str=field(default_factory=utc_now)
    updated_at: str=field(default_factory=utc_now)
    state: AgentState=AgentState.QUEUED
    source: str="ui"
    provider: str="unavailable"
    model: str=""
    error_code: str=""
    error_message: str=""
    metadata: object=field(default_factory=dict)
    def __post_init__(self):
        if not self.session_id or not self.conversation_id or not self.user_message_id or not self.prompt.strip(): raise ValueError("agent request needs session, conversation, user message and prompt")
        object.__setattr__(self,"metadata",MappingProxyType(dict(self.metadata)))
    def as_payload(self):
        return {"request_id":self.request_id,"session_id":self.session_id,"conversation_id":self.conversation_id,"user_message_id":self.user_message_id,"prompt":self.prompt,"created_at":self.created_at,"updated_at":self.updated_at,"state":self.state.value,"source":self.source,"provider":self.provider,"model":self.model,"error_code":self.error_code,"error_message":self.error_message,"metadata":dict(self.metadata)}
