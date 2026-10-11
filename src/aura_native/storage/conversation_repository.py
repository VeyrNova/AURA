"""SQLite repository with strict native-session conversation isolation."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from aura_native.conversation.models import Conversation, ConversationMessage
from aura_native.storage.database import NativeDatabase

def _now(): return datetime.now(timezone.utc).isoformat(timespec="microseconds")

class ConversationRepository:
    def __init__(self,database:NativeDatabase): self.db=database
    @staticmethod
    def _conversation(row): return Conversation(row["conversation_id"],row["session_id"],row["title"],row["created_at"],row["updated_at"],row["status"])
    @staticmethod
    def _message(row): return ConversationMessage(row["message_id"],row["conversation_id"],row["role"],row["content"],row["created_at"],int(row["sequence"]),row["status"],row["source"])
    def create(self,session_id,title=""):
        session_id=str(session_id or "").strip()
        if not session_id: raise ValueError("session_id is required")
        now=_now(); value=Conversation(str(uuid4()),session_id,str(title or "").strip()[:200],now,now,"active")
        with self.db.transaction() as conn: conn.execute("INSERT INTO conversations(conversation_id,session_id,title,created_at,updated_at,status) VALUES(?,?,?,?,?,?)",(value.conversation_id,value.session_id,value.title,value.created_at,value.updated_at,value.status))
        return value
    def get(self,conversation_id,session_id):
        with self.db.reader() as conn: row=conn.execute("SELECT * FROM conversations WHERE conversation_id=? AND session_id=? AND status='active'",(str(conversation_id),str(session_id))).fetchone()
        return self._conversation(row) if row else None
    def list(self,session_id,limit=50):
        with self.db.reader() as conn: rows=conn.execute("SELECT * FROM conversations WHERE session_id=? AND status='active' ORDER BY updated_at DESC,conversation_id DESC LIMIT ?",(str(session_id),max(1,min(int(limit),100)))).fetchall()
        return [self._conversation(row) for row in rows]
    def add_message(self,conversation_id,session_id,role,content,source="qml"):
        value=str(content or "").strip()
        if not value: raise ValueError("message content is required")
        if role not in ("user","assistant"): raise ValueError("unsupported native conversation role")
        now=_now()
        with self.db.transaction() as conn:
            if conn.execute("SELECT 1 FROM conversations WHERE conversation_id=? AND session_id=? AND status='active'",(str(conversation_id),str(session_id))).fetchone() is None: raise ValueError("conversation not found")
            sequence=int(conn.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM conversation_messages WHERE conversation_id=?",(str(conversation_id),)).fetchone()[0])
            message=ConversationMessage(str(uuid4()),str(conversation_id),role,value,now,sequence,"active",str(source or "qml")[:80])
            conn.execute("INSERT INTO conversation_messages(message_id,conversation_id,role,content,created_at,sequence,status,source) VALUES(?,?,?,?,?,?,?,?)",(message.message_id,message.conversation_id,message.role,message.content,message.created_at,message.sequence,message.status,message.source))
            conn.execute("UPDATE conversations SET updated_at=? WHERE conversation_id=?",(now,message.conversation_id))
        return message
    def messages(self,conversation_id,session_id,limit=200):
        if self.get(conversation_id,session_id) is None:return []
        with self.db.reader() as conn: rows=conn.execute("SELECT * FROM conversation_messages WHERE conversation_id=? AND status='active' ORDER BY sequence,message_id LIMIT ?",(str(conversation_id),max(1,min(int(limit),500)))).fetchall()
        return [self._message(row) for row in rows]
    def clear(self,conversation_id,session_id):
        with self.db.transaction() as conn:
            row=conn.execute("SELECT * FROM conversations WHERE conversation_id=? AND session_id=? AND status='active'",(str(conversation_id),str(session_id))).fetchone()
            if row is None:return None
            conn.execute("DELETE FROM conversation_messages WHERE conversation_id=?",(str(conversation_id),)); conn.execute("UPDATE conversations SET updated_at=? WHERE conversation_id=?",(_now(),str(conversation_id)))
            return self._conversation(row)
