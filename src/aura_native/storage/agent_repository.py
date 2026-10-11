from dataclasses import replace
from aura_native.agent.models import AgentRequest, AgentState, utc_now
from aura_native.storage.database import NativeDatabase


class AgentRepository:
    def __init__(self,database:NativeDatabase): self.db=database
    @staticmethod
    def _record(row):
        return AgentRequest(request_id=row["request_id"],session_id=row["session_id"],conversation_id=row["conversation_id"],user_message_id=row["user_message_id"],prompt=row["prompt"],created_at=row["created_at"],updated_at=row["updated_at"],state=AgentState(row["state"]),source=row["source"],provider=row["provider"],model=row["model"],error_code=row["error_code"],error_message=row["error_message"],metadata={})
    def create(self,request):
        with self.db.transaction() as c: c.execute("INSERT INTO agent_requests(request_id,session_id,conversation_id,user_message_id,prompt,state,provider,model,created_at,updated_at,source,error_code,error_message) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(request.request_id,request.session_id,request.conversation_id,request.user_message_id,request.prompt,request.state.value,request.provider,request.model,request.created_at,request.updated_at,request.source,request.error_code,request.error_message))
        return request
    def find_by_user_message(self,session_id,user_message_id):
        with self.db.reader() as c: row=c.execute("SELECT * FROM agent_requests WHERE session_id=? AND user_message_id=? ORDER BY created_at DESC,request_id DESC LIMIT 1",(session_id,user_message_id)).fetchone()
        return self._record(row) if row else None
    def recover_active(self,session_id=None):
        sql="SELECT * FROM agent_requests WHERE state IN ('queued','thinking','responding')"; params=[]
        if session_id is not None: sql+=" AND session_id=?";params.append(session_id)
        with self.db.reader() as c: rows=c.execute(sql,params).fetchall()
        recovered=[]
        for row in rows: recovered.append(self.transition(self._record(row),AgentState.ERROR,error_code="recovered_interrupted",error_message="Request interrupted before completion"))
        return recovered
    def get(self,request_id,session_id):
        with self.db.reader() as c: row=c.execute("SELECT * FROM agent_requests WHERE request_id=? AND session_id=?",(request_id,session_id)).fetchone()
        return self._record(row) if row else None
    def transition(self,request,state,*,error_code="",error_message=""):
        updated=replace(request,state=state,updated_at=utc_now(),error_code=error_code,error_message=error_message)
        with self.db.transaction() as c: c.execute("UPDATE agent_requests SET state=?,updated_at=?,error_code=?,error_message=? WHERE request_id=? AND session_id=?",(updated.state.value,updated.updated_at,updated.error_code,updated.error_message,updated.request_id,updated.session_id))
        return updated
    def update_provider_snapshot(self,request):
        with self.db.transaction() as c: c.execute("UPDATE agent_requests SET provider=?,model=?,updated_at=? WHERE request_id=? AND session_id=?",(request.provider,request.model,utc_now(),request.request_id,request.session_id))
        return request
