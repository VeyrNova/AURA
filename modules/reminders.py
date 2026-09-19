"""
reminders.py
Gestion des rappels d'AURA (section 13 du cahier des charges).
"""
import logging
from datetime import datetime

logger = logging.getLogger("aura.reminders")


class ReminderManager:
    def __init__(self, db):
        self.db = db

    def create_reminder(self, content: str, trigger_at: datetime) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        cursor = self.db.conn.execute(
            "INSERT INTO reminders (content, trigger_at, is_done, created_at) VALUES (?, ?, 0, ?)",
            (content, trigger_at.isoformat(timespec="seconds"), now),
        )
        self.db.conn.commit()
        reminder_id = cursor.lastrowid
        logger.info(f"Rappel créé (id={reminder_id}) pour {trigger_at.isoformat(timespec='seconds')}")
        return reminder_id

    def list_reminders(self, include_done: bool = False, limit: int = 20):
        if include_done:
            cursor = self.db.conn.execute(
                "SELECT * FROM reminders ORDER BY trigger_at ASC LIMIT ?", (limit,)
            )
        else:
            cursor = self.db.conn.execute(
                "SELECT * FROM reminders WHERE is_done = 0 ORDER BY trigger_at ASC LIMIT ?", (limit,)
            )
        return [dict(row) for row in cursor.fetchall()]

    def get_reminder(self, reminder_id: int):
        cursor = self.db.conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def delete_reminder(self, reminder_id: int) -> bool:
        cursor = self.db.conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        self.db.conn.commit()
        return cursor.rowcount > 0

    def get_due_reminders(self, now: datetime = None):
        now = now or datetime.now()
        cursor = self.db.conn.execute(
            "SELECT * FROM reminders WHERE is_done = 0 AND trigger_at <= ? ORDER BY trigger_at ASC",
            (now.isoformat(timespec="seconds"),),
        )
        return [dict(row) for row in cursor.fetchall()]

    def mark_done(self, reminder_id: int) -> bool:
        cursor = self.db.conn.execute("UPDATE reminders SET is_done = 1 WHERE id = ?", (reminder_id,))
        self.db.conn.commit()
        return cursor.rowcount > 0
