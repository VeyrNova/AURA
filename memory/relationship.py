"""Bounded relationship/familiarity model for AURA v0.6."""
from __future__ import annotations

from datetime import datetime


class RelationshipModel:
    """Tracks familiarity as a UX signal, never as an emotional claim."""

    KEY_FIRST_SEEN = "relationship.first_seen"
    KEY_USER_MESSAGES = "relationship.user_messages"
    KEY_SESSIONS = "relationship.sessions"

    def __init__(self, db):
        self.db = db
        if not self.db.get_preference(self.KEY_FIRST_SEEN):
            self.db.set_preference(self.KEY_FIRST_SEEN, datetime.now().astimezone().isoformat(timespec="seconds"))
        self._session_counted = False

    def start_session(self, *, private: bool = False) -> None:
        if private or self._session_counted:
            return
        sessions = self._get_int(self.KEY_SESSIONS) + 1
        self.db.set_preference(self.KEY_SESSIONS, str(sessions))
        self._session_counted = True

    def record_user_message(self, *, private: bool = False) -> None:
        if private:
            return
        count = self._get_int(self.KEY_USER_MESSAGES) + 1
        self.db.set_preference(self.KEY_USER_MESSAGES, str(count))

    def _get_int(self, key: str) -> int:
        raw = self.db.get_preference(key)
        try:
            return int(raw or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def sessions(self) -> int:
        return self._get_int(self.KEY_SESSIONS)

    @property
    def user_messages(self) -> int:
        return self._get_int(self.KEY_USER_MESSAGES)

    @property
    def familiarity(self) -> float:
        # Slow, bounded evolution. Familiarity tunes style only.
        value = 0.10 + min(0.30, self.sessions * 0.025) + min(0.55, self.user_messages * 0.004)
        return max(0.10, min(0.95, value))

    def render_compact_for_prompt(self, *, private: bool = False) -> str:
        if private:
            return (
                "RELATION / CONTINUITE\n"
                "- Mode prive actif : reste naturelle sans utiliser de familiarite persistante.\n"
                "- N'invente ni intimite, ni souvenir absent du contexte courant."
            )
        return (
            "RELATION / CONTINUITE\n"
            f"- Familiarite fonctionnelle : {self.familiarity:.2f}/1.00; adapte le naturel et la chaleur sans surjouer l'intimite.\n"
            "- Tu es la meme AURA d'une session a l'autre, mais tu ne cites jamais un souvenir qui n'est pas fourni dans MEMORY CONTEXT."
        )

    def render_for_prompt(self, *, private: bool = False) -> str:
        if private:
            return (
                "RELATIONSHIP MODEL\n"
                "- Mode prive actif : n'actualise pas le modele de familiarite pendant cette session.\n"
                "- Reste naturelle sans pretendre a une intimite ou a des souvenirs non fournis."
            )
        return (
            "RELATIONSHIP MODEL\n"
            f"- Sessions observees : {self.sessions}.\n"
            f"- Messages utilisateur observes : {self.user_messages}.\n"
            f"- Familiarite fonctionnelle : {self.familiarity:.2f}/1.00.\n"
            "- Cette valeur ajuste seulement le naturel, la concision et la familiarite de langage.\n"
            "- Ne la presente jamais comme de l'amour, de l'attachement, de la dependance ou une emotion humaine reelle."
        )
