from __future__ import annotations

import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger("aura.local_action_context")


@dataclass
class PendingLocalAction:
    intent: str = ""
    slot: str = ""
    expires_at: float = 0.0

    @property
    def active(self) -> bool:
        return bool(self.intent and self.slot and self.expires_at > 0.0)


@dataclass(frozen=True)
class PendingResolution:
    handled: bool = False
    intent: str = ""
    params: dict | None = None
    response: str = ""


class LocalActionContext:
    """Short-lived slot filling for deterministic local actions.

    This state is intentionally ephemeral and is not personal memory. It exists
    only to complete a local command AURA has just asked the user to clarify,
    e.g. ``crée une tâche`` -> ``Quelle tâche ?`` -> ``préparer le rapport``.
    """

    _CANCEL_EXACT = {
        "annule", "annuler", "laisse tomber", "oublie", "stop", "cancel",
        "non", "non merci", "rien", "finalement non",
    }

    # Clear the slot instead of hijacking an obvious new request. The list is
    # deliberately conservative; ordinary imperative task titles such as
    # "faire les levées des non conformités ICPE" remain valid.
    _TOPIC_CHANGE_PREFIXES = (
        "meteo ", "météo ", "quel temps", "quelle meteo", "quelle météo",
        "itineraire ", "itinéraire ", "trajet ", "route ",
        "carte ", "localise ", "localiser ", "ou se trouve", "où se trouve",
        "cherche sur internet", "recherche sur internet", "recherche web", "cherche web",
        "ouvre google maps", "ouvre la carte",
        "qui est ", "qu'est-ce", "qu’est-ce", "pourquoi ", "comment ",
        "combien ", "quel ", "quelle ", "quels ", "quelles ",
        "peux-tu ", "peux tu ", "donne-moi ", "donne moi ", "dis-moi ", "dis moi ",
        "rappelle-moi ", "rappelle moi ", "note ", "prends une note",
    )

    def __init__(self, *, clock: Callable[[], float] | None = None, ttl_seconds: float = 120.0):
        self._clock = clock or time.monotonic
        self.ttl_seconds = max(10.0, float(ttl_seconds))
        self.state = PendingLocalAction()

    @staticmethod
    def _normalize(text: str) -> str:
        text = unicodedata.normalize("NFKD", text or "")
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.casefold().replace("’", "'")
        text = re.sub(r"[^a-z0-9'\-\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def clear(self) -> None:
        self.state = PendingLocalAction()

    def _expire_if_needed(self) -> None:
        if self.state.active and self._clock() >= self.state.expires_at:
            self.clear()

    def open_task_title(self) -> None:
        self.state = PendingLocalAction(
            intent="CREATE_TASK",
            slot="task_title",
            expires_at=self._clock() + self.ttl_seconds,
        )
        logger.info("Pending local action opened intent=CREATE_TASK slot=task_title ttl=%.0fs", self.ttl_seconds)

    @property
    def active(self) -> bool:
        self._expire_if_needed()
        return self.state.active

    @classmethod
    def _is_topic_change(cls, text: str) -> bool:
        raw = (text or "").strip()
        normalized = cls._normalize(raw)
        if not normalized:
            return True
        if raw.endswith("?"):
            return True
        return any(normalized.startswith(cls._normalize(prefix)) for prefix in cls._TOPIC_CHANGE_PREFIXES)

    @staticmethod
    def _clean_task_title(text: str) -> str:
        title = (text or "").strip().strip(" \t\r\n")
        title = re.sub(r"^(?:la\s+t[âa]che\s+(?:est|c['’]est)\s*[:\-]?\s*)", "", title, flags=re.IGNORECASE)
        return title.strip().rstrip(".").strip()

    @classmethod
    def _looks_like_task_title(cls, text: str) -> bool:
        title = cls._clean_task_title(text)
        normalized = cls._normalize(title)
        if not title or not normalized:
            return False
        if len(title) > 220 or len(normalized.split()) > 32:
            return False
        if cls._is_topic_change(title):
            return False
        return True

    def resolve(self, text: str, *, explicit_intent: str | None = None) -> PendingResolution:
        """Resolve a reply against the active slot.

        Explicit deterministic commands always win and close the pending slot;
        this prevents a new local command from becoming task text.
        """
        self._expire_if_needed()
        if not self.state.active:
            return PendingResolution()

        normalized = self._normalize(text)
        if normalized in self._CANCEL_EXACT:
            self.clear()
            logger.info("Pending local action cancelled intent=CREATE_TASK slot=task_title")
            return PendingResolution(
                handled=True,
                response="D'accord, j'annule la création de la tâche.",
            )

        if explicit_intent:
            self.clear()
            return PendingResolution()

        if self.state.intent == "CREATE_TASK" and self.state.slot == "task_title":
            if self._looks_like_task_title(text):
                title = self._clean_task_title(text)
                self.clear()
                logger.info("Pending local action resolved intent=CREATE_TASK slot=task_title chars=%d", len(title))
                return PendingResolution(
                    handled=True,
                    intent="CREATE_TASK",
                    params={"raw": title},
                )
            # A clear topic change abandons the pending action rather than
            # swallowing a new request. Non-obvious text remains available to
            # the normal router/LLM path after the slot is cleared.
            if self._is_topic_change(text):
                self.clear()
            return PendingResolution()

        self.clear()
        return PendingResolution()
