from __future__ import annotations
import json
from dataclasses import replace
from datetime import datetime, timezone
from aura_native.google.models import PreparedAction

def _now(): return datetime.now(timezone.utc).isoformat(timespec="microseconds")
class PreparedActionRepository:
 def __init__(self,database): self.db=database
 def _row(self,row): return PreparedAction(row['action_id'],row['tool_name'],row['action_type'],json.loads(row['payload_json']),row['summary'],bool(row['requires_confirmation']),row['state'],row['created_at'],row['expires_at'],row['confirmed_at'],row['executed_at'],row['error_code'])
 def create(self,a):
  with self.db.transaction() as c:c.execute('INSERT INTO prepared_actions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(a.action_id,a.tool_name,a.action_type,json.dumps(a.payload,sort_keys=True),a.summary,int(a.requires_confirmation),a.state,a.created_at,a.expires_at,a.confirmed_at,a.executed_at,a.error_code))
  return a
 def get(self,i):
  with self.db.reader() as c:r=c.execute('SELECT * FROM prepared_actions WHERE action_id=?',(i,)).fetchone()
  return self._row(r) if r else None
 def get_pending(self):
  with self.db.reader() as c:rows=c.execute("SELECT * FROM prepared_actions WHERE state='prepared' AND (expires_at IS NULL OR expires_at>?) ORDER BY created_at",(_now(),)).fetchall()
  return [self._row(r) for r in rows]
 def _transition(self,i,old,new,**extra):
  fields={'state':new,**extra}; sets=','.join(k+'=?' for k in fields); vals=list(fields.values())+[i,old]
  with self.db.transaction() as c:
   if c.execute(f'UPDATE prepared_actions SET {sets} WHERE action_id=? AND state=?',vals).rowcount!=1: raise ValueError('invalid_prepared_action_transition')
  return self.get(i)
 def confirm(self,i): return self._transition(i,'prepared','confirmed',confirmed_at=_now())
 def cancel(self,i):
  a=self.get(i); return self._transition(i,a.state,'cancelled') if a and a.state in ('prepared','confirmed') else (_ for _ in ()).throw(ValueError('invalid_prepared_action_transition'))
 def mark_executed(self,i): return self._transition(i,'confirmed','executed',executed_at=_now())
 def mark_error(self,i,error_code): return self._transition(i,'confirmed','error',error_code=str(error_code))
 def expire_old(self,now):
  with self.db.transaction() as c:return c.execute("UPDATE prepared_actions SET state='expired' WHERE state='prepared' AND expires_at IS NOT NULL AND expires_at<=?",(str(now),)).rowcount
