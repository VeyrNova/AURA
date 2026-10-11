from datetime import datetime, timezone
from uuid import uuid4

class LocalRemindersRepository:
    def __init__(self, database): self.database = database
    def list(self):
        with self.database.reader() as conn:
            return [dict(row) for row in conn.execute("SELECT reminder_id,content,trigger_at,created_at,claimed_at,notified_at,expired_at FROM local_reminders ORDER BY trigger_at,reminder_id")]
    def create(self, content, trigger_at):
        reminder_id = str(uuid4()); created = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        with self.database.transaction() as conn:
            conn.execute("INSERT INTO local_reminders(reminder_id,content,trigger_at,created_at) VALUES(?,?,?,?)", (reminder_id, content, trigger_at, created))
        return {"reminder_id": reminder_id, "content": content, "trigger_at": trigger_at, "created_at": created}
    def delete(self, reminder_id):
        identifier = str(reminder_id or '').strip()
        if not identifier:
            return False
        with self.database.transaction() as conn:
            return conn.execute("DELETE FROM local_reminders WHERE reminder_id=?", (identifier,)).rowcount == 1
    def list_due(self, now_utc, missed_window_seconds):
        cutoff = (datetime.fromisoformat(now_utc) - __import__('datetime').timedelta(seconds=missed_window_seconds)).isoformat()
        with self.database.reader() as conn:
            return [dict(row) for row in conn.execute("SELECT reminder_id,content,trigger_at,created_at,claimed_at,notified_at,expired_at FROM local_reminders WHERE notified_at IS NULL AND expired_at IS NULL ORDER BY trigger_at, reminder_id")]
    def next_pending(self):
        with self.database.reader() as conn:
            return conn.execute("SELECT MIN(trigger_at) FROM local_reminders WHERE notified_at IS NULL AND expired_at IS NULL").fetchone()[0]
    def try_claim(self, reminder_id, claimed_at, stale_before):
        with self.database.transaction() as conn:
            return conn.execute("UPDATE local_reminders SET claimed_at=? WHERE reminder_id=? AND notified_at IS NULL AND expired_at IS NULL AND (claimed_at IS NULL OR claimed_at < ?)", (claimed_at, str(reminder_id), stale_before)).rowcount == 1
    def mark_notified(self, reminder_id, notified_at):
        with self.database.transaction() as conn:
            return conn.execute("UPDATE local_reminders SET notified_at=?, claimed_at=NULL WHERE reminder_id=? AND notified_at IS NULL", (notified_at, str(reminder_id))).rowcount == 1
    def mark_expired(self, reminder_id, expired_at):
        with self.database.transaction() as conn:
            return conn.execute("UPDATE local_reminders SET expired_at=?, claimed_at=NULL WHERE reminder_id=? AND notified_at IS NULL AND expired_at IS NULL", (expired_at, str(reminder_id))).rowcount == 1
