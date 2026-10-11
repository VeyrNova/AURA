from datetime import datetime, timezone
from uuid import uuid4

class LocalTasksRepository:
    def __init__(self, database):
        self.database = database

    def list(self):
        with self.database.reader() as conn:
            return [dict(row) for row in conn.execute("SELECT task_id,title,due,completed,created_at,updated_at FROM local_tasks ORDER BY created_at,task_id")]

    def create(self, title, due=None):
        task_id = str(uuid4())
        created = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        with self.database.transaction() as conn:
            conn.execute("INSERT INTO local_tasks(task_id,title,due,completed,created_at,updated_at) VALUES(?,?,?,?,?,?)", (task_id, title, due, 0, created, created))
        return {"task_id": task_id, "title": title, "due": due, "completed": 0, "created_at": created, "updated_at": created}

    def update(self, task_id, title, due):
        stamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        with self.database.transaction() as conn:
            cur = conn.execute("UPDATE local_tasks SET title=?, due=?, updated_at=? WHERE task_id=?", (title, due, stamp, task_id))
        return cur.rowcount == 1

    def complete(self, task_id):
        stamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        with self.database.transaction() as conn:
            cur = conn.execute("UPDATE local_tasks SET completed=1, updated_at=? WHERE task_id=? AND completed=0", (stamp, task_id))
        return cur.rowcount == 1

    def delete(self, task_id):
        with self.database.transaction() as conn:
            cur = conn.execute("DELETE FROM local_tasks WHERE task_id=?", (task_id,))
        return cur.rowcount == 1
