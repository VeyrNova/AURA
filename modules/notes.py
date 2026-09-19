"""
notes.py
Gestion des notes d'AURA (section 11 du cahier des charges).
"""
import logging
from datetime import datetime

logger = logging.getLogger("aura.notes")


class NotesManager:
    """CRUD sur la table `notes`. Ne connaît rien du routage d'intentions :
    reçoit des paramètres déjà propres et renvoie des données brutes."""

    def __init__(self, db):
        self.db = db

    def create_note(self, content: str, title: str = None, tags: str = None) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        cursor = self.db.conn.execute(
            "INSERT INTO notes (title, content, tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (title, content, tags, now, now),
        )
        self.db.conn.commit()
        note_id = cursor.lastrowid
        logger.info(f"Note créée (id={note_id})")
        return note_id

    def update_note(self, note_id: int, content: str = None, title: str = None) -> bool:
        note = self.get_note(note_id)
        if note is None:
            return False
        new_content = content if content is not None else note["content"]
        new_title = title if title is not None else note["title"]
        now = datetime.now().isoformat(timespec="seconds")
        self.db.conn.execute(
            "UPDATE notes SET content = ?, title = ?, updated_at = ? WHERE id = ?",
            (new_content, new_title, now, note_id),
        )
        self.db.conn.commit()
        logger.info(f"Note modifiée (id={note_id})")
        return True

    def delete_note(self, note_id: int) -> bool:
        cursor = self.db.conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self.db.conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Note supprimée (id={note_id})")
        return deleted

    def get_note(self, note_id: int):
        cursor = self.db.conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def search_notes(self, query: str, limit: int = 10):
        cursor = self.db.conn.execute(
            "SELECT * FROM notes WHERE content LIKE ? OR title LIKE ? "
            "ORDER BY created_at DESC LIMIT ?",
            (f"%{query}%", f"%{query}%", limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_notes(self, limit: int = 20):
        cursor = self.db.conn.execute(
            "SELECT * FROM notes ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
