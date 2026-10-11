from pathlib import Path
from aura_native.core.contracts import CommandError, CommandResult, Event
from aura_native.storage.conversation_repository import ConversationRepository
from aura_native.storage.database import NativeDatabase
import os

class ConversationService:
    def __init__(self, db_path: str|Path): self.database=NativeDatabase(db_path); self.repository=ConversationRepository(self.database); self._bus=None
    def bind(self,bus):
        self._bus=bus
        for name, handler in (("conversation.new",self._new),("conversation.send",self._send),("conversation.list",self._list),("conversation.get",self._get),("conversation.clear",self._clear)): bus.register_handler(name,handler)
    def _result(self,c,ok,status,payload=None,error=None): return CommandResult(c.command_id,ok,status,payload=payload or {},error=error,correlation_id=c.correlation_id,session_id=c.session_id,source="conversation")
    def _publish(self,c,name,payload): self._bus.publish(Event(name=name,payload=payload,correlation_id=c.correlation_id,session_id=c.session_id,source="conversation"))
    def _new(self,c,t):
        record=self.repository.create(c.session_id,c.payload.get("title", "")); payload={"conversation":record.as_payload()}; self._publish(c,"conversation.created",payload); return self._result(c,True,"created",payload)
    def _send(self,c,t):
        try:
            conversation_id=str(c.payload.get("conversation_id") or "").strip()
            if not conversation_id: record=self.repository.create(c.session_id,c.payload.get("title", "")); self._publish(c,"conversation.created",{"conversation":record.as_payload()}); conversation_id=record.conversation_id
            message=self.repository.add_message(conversation_id,c.session_id,"user",c.payload.get("text",""),c.source); payload={"message":message.as_payload(),"conversation_id":conversation_id}; self._publish(c,"conversation.message_created",payload); self._publish(c,"conversation.updated",{"conversation_id":conversation_id}); metadata=dict(c.payload.get("metadata") or {}); voice_id=str(metadata.get("voice_request_id", ""));
            if voice_id and os.environ.get("AURA_PTT_DIAGNOSTICS") == "1": print(f"VOICE_REQUEST_SERVICE_RECEIVED voice_request_id={voice_id}", flush=True)
            self._bus.submit(__import__('aura_native.core.contracts',fromlist=['Command']).Command(name="agent.submit",payload={"text":message.content,"conversation_id":conversation_id,"user_message_id":message.message_id,"metadata":metadata},session_id=c.session_id,source="voice" if voice_id else "conversation")); return self._result(c,True,"sent",payload)
        except ValueError as exc:return self._result(c,False,"invalid",error=CommandError("invalid_conversation",str(exc)))
    def _list(self,c,t):
        rows=self.repository.list(c.session_id,c.payload.get("limit",50)); payload={"conversations":tuple(x.as_payload() for x in rows)}; self._publish(c,"conversation.loaded",payload); return self._result(c,True,"ok",payload)
    def _get(self,c,t):
        ident=str(c.payload.get("conversation_id") or ""); record=self.repository.get(ident,c.session_id); payload={"conversation":record.as_payload() if record else None,"messages":tuple(x.as_payload() for x in self.repository.messages(ident,c.session_id)) if record else ()}; self._publish(c,"conversation.loaded",payload); return self._result(c,record is not None,"ok" if record else "not_found",payload)
    def _clear(self,c,t):
        ident=str(c.payload.get("conversation_id") or ""); record=self.repository.clear(ident,c.session_id); payload={"conversation_id":ident,"cleared":record is not None};
        if record:self._publish(c,"conversation.cleared",payload); self._publish(c,"conversation.updated",payload)
        return self._result(c,record is not None,"cleared" if record else "not_found",payload)
