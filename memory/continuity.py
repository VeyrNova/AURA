"""Session continuity metadata for AURA v0.6.

No conversation transcript is persisted here. The engine stores only timestamps
and message counters; semantic continuity comes from explicit/local memories.
"""
from __future__ import annotations

from datetime import datetime


class ContinuityEngine:
    def __init__(self, db):
        self.db = db
        self.session_id: int | None = None
        self.private_mode = False

    def start_session(self) -> int:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        cursor = self.db.conn.execute(
            "INSERT INTO conversation_sessions (started_at, user_messages, assistant_messages, private_mode) "
            "VALUES (?, 0, 0, 0)",
            (now,),
        )
        self.db.conn.commit()
        self.session_id = int(cursor.lastrowid)
        return self.session_id

    def set_private_mode(self, enabled: bool) -> None:
        self.private_mode = bool(enabled)
        if self.session_id is not None:
            self.db.conn.execute(
                "UPDATE conversation_sessions SET private_mode=? WHERE id=?",
                (1 if self.private_mode else 0, self.session_id),
            )
            self.db.conn.commit()

    def record_user_message(self) -> None:
        if self.private_mode or self.session_id is None:
            return
        self.db.conn.execute(
            "UPDATE conversation_sessions SET user_messages=user_messages+1 WHERE id=?",
            (self.session_id,),
        )
        self.db.conn.commit()

    def record_assistant_message(self) -> None:
        if self.private_mode or self.session_id is None:
            return
        self.db.conn.execute(
            "UPDATE conversation_sessions SET assistant_messages=assistant_messages+1 WHERE id=?",
            (self.session_id,),
        )
        self.db.conn.commit()

    def end_session(self) -> None:
        if self.session_id is None:
            return
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        self.db.conn.execute(
            "UPDATE conversation_sessions SET ended_at=? WHERE id=?",
            (now, self.session_id),
        )
        self.db.conn.commit()

    def previous_session(self):
        if self.session_id is None:
            return None
        row = self.db.conn.execute(
            "SELECT * FROM conversation_sessions WHERE id != ? AND ended_at IS NOT NULL "
            "ORDER BY id DESC LIMIT 1",
            (self.session_id,),
        ).fetchone()
        return dict(row) if row else None

    def session_count(self) -> int:
        return int(self.db.conn.execute("SELECT COUNT(*) FROM conversation_sessions").fetchone()[0])

    def render_compact_for_prompt(self) -> str:
        if self.private_mode:
            return (
                "CONTINUITE COURTE\n"
                "- Session privee : aucune continuite persistante ne doit etre supposee."
            )
        previous = self.previous_session()
        total = self.session_count()
        if previous:
            return (
                "CONTINUITE COURTE\n"
                f"- Sessions locales connues : {total}; une session precedente existe.\n"
                "- Tu peux parler comme quelqu'un qui retrouve un interlocuteur connu, sans inventer le contenu de la session precedente."
            )
        return (
            "CONTINUITE COURTE\n"
            "- Aucune session precedente terminee n'est disponible; ne simule pas de retrouvailles."
        )

    def render_for_prompt(self) -> str:
        if self.private_mode:
            return (
                "CONTINUITE DE SESSION\n"
                "- Mode prive actif : ne consulte ni n'ajoute de memoire long terme pour cette session.\n"
                "- La conversation courante reste seulement dans le contexte volatile de l'application."
            )
        previous = self.previous_session()
        total = self.session_count()
        if previous:
            last = previous.get("ended_at") or previous.get("started_at")
            return (
                "CONTINUITE DE SESSION\n"
                f"- Sessions locales connues : {total}.\n"
                f"- Derniere session terminee : {last}.\n"
                "- N'invente pas le contenu d'une ancienne conversation : seuls les souvenirs explicitement fournis par la memoire sont fiables."
            )
        return (
            "CONTINUITE DE SESSION\n"
            "- Aucune session precedente terminee n'est disponible.\n"
            "- N'invente pas de passe conversationnel."
        )
