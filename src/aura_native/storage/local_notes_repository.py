from datetime import datetime, timezone
from uuid import uuid4
class LocalNotesRepository:
    def __init__(self, database): self.database=database
    def list(self):
        with self.database.reader() as c: return [dict(r) for r in c.execute('SELECT note_id,title,content,created_at,updated_at FROM local_notes ORDER BY updated_at DESC,note_id')]
    def create(self,title,content):
        now=datetime.now(timezone.utc).isoformat(timespec='microseconds'); nid=str(uuid4())
        with self.database.transaction() as c: c.execute('INSERT INTO local_notes VALUES(?,?,?,?,?)',(nid,title,content,now,now))
        return {'note_id':nid,'title':title,'content':content,'created_at':now,'updated_at':now}
    def delete(self,note_id):
        with self.database.transaction() as c: return c.execute('DELETE FROM local_notes WHERE note_id=?',(str(note_id),)).rowcount==1
    def update(self,note_id,title,content):
        now=datetime.now(timezone.utc).isoformat(timespec='microseconds')
        with self.database.transaction() as c:
            changed=c.execute('UPDATE local_notes SET title=?,content=?,updated_at=? WHERE note_id=?',(title,content,now,str(note_id))).rowcount
        return changed == 1
