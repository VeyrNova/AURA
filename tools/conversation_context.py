from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Callable

from config.settings import settings
from tools.models import ToolPlan, ToolResult


@dataclass
class ToolContextState:
    tool: str = ""
    category: str = ""
    location: str = ""
    tomorrow: bool = False
    pending_slot: str = ""
    expires_at: float = 0.0

    @property
    def active(self) -> bool:
        return bool(self.tool and self.expires_at > 0)


class ConversationalToolContext:
    """Short-lived, non-persistent context for deterministic tool follow-ups.

    This is deliberately not user memory. It only helps complete a tool turn
    such as "Quelle météo ?" -> "Vidauban" or "et demain ?".
    """

    _CANCEL = (
        "annule", "annuler", "laisse tomber", "oublie", "stop", "cancel", "never mind",
    )
    _NON_LOCATION = {
        "oui", "non", "merci", "ok", "okay", "d'accord", "daccord", "peut etre", "peut-être",
        "je sais pas", "je ne sais pas", "aucune idee", "aucune idée", "rien",
        # P0.6.4.8.2 — relative references must never become geocoder input.
        "place", "sur place", "ici", "la", "là", "la bas", "là-bas",
        "cet endroit", "a cet endroit", "à cet endroit", "ce lieu", "le lieu",
        "destination", "la destination",
    }

    def __init__(self, *, clock: Callable[[], float] | None = None):
        self._clock = clock or time.monotonic
        self.state = ToolContextState()

    @staticmethod
    def _normalize(text: str) -> str:
        text = unicodedata.normalize("NFKD", text or "")
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.casefold().replace("’", "'")
        text = re.sub(r"[^a-z0-9'\-\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def clear(self) -> None:
        self.state = ToolContextState()

    def _expire_if_needed(self) -> None:
        if self.state.active and self._clock() >= self.state.expires_at:
            self.clear()

    def _set_weather(self, *, location: str = "", tomorrow: bool = False, pending_slot: str = "", ttl: float) -> None:
        self.state = ToolContextState(
            tool="weather",
            category="weather",
            location=(location or "").strip(),
            tomorrow=bool(tomorrow),
            pending_slot=pending_slot,
            expires_at=self._clock() + max(1.0, float(ttl)),
        )

    @classmethod
    def _is_cancel(cls, text: str) -> bool:
        normalized = cls._normalize(text)
        return any(term in normalized for term in cls._CANCEL)

    @classmethod
    def _clean_location_candidate(cls, text: str) -> str:
        value = (text or "").strip().strip(".,!?;:")
        value = re.sub(r"^(?:et\s+)?(?:à|a|pour|sur)\s+", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+(?:s['’]il te pla[îi]t|stp)$", "", value, flags=re.IGNORECASE)
        return value.strip().strip(".,!?;:")

    @classmethod
    def _looks_like_location(cls, text: str) -> bool:
        candidate = cls._clean_location_candidate(text)
        normalized = cls._normalize(candidate)
        if not candidate or normalized in cls._NON_LOCATION:
            return False
        if len(candidate) < 2 or len(candidate) > 80:
            return False
        # A slot answer should look like a place, not a full sentence/question.
        words = normalized.split()
        if not (1 <= len(words) <= 7):
            return False
        if any(token in words for token in (
            "pourquoi", "comment", "quand", "combien", "quel", "quelle", "quels", "quelles",
            "peux", "peut", "veux", "veut", "fais", "fait", "fait-il", "faire", "cherche", "recherche", "rappelle",
            "note", "tache", "tâche", "score", "match", "bitcoin", "actualites", "actualités",
        )):
            return False
        # Letters/digits for postal suffixes, spaces, apostrophes and hyphens only.
        return bool(re.fullmatch(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'’\- ,.]*", candidate))

    @classmethod
    def _extract_followup_location(cls, text: str) -> str:
        patterns = (
            r"^(?:et\s+)?(?:à|a|pour|sur)\s+(.+?)[?.!]*$",
            r"^(?:et\s+)?(.+?)\s+(?:demain|aujourd['’]hui|maintenant)[?.!]*$",
        )
        for pattern in patterns:
            match = re.match(pattern, (text or "").strip(), re.IGNORECASE)
            if match:
                candidate = cls._clean_location_candidate(match.group(1))
                if cls._looks_like_location(candidate):
                    return candidate
        return ""

    def plan_followup(self, text: str) -> ToolPlan | None:
        self._expire_if_needed()
        if not self.state.active:
            return None
        if self._is_cancel(text):
            self.clear()
            return None

        normalized = self._normalize(text)
        if self.state.tool != "weather":
            return None

        # Missing-location slot: accept a concise place answer such as
        # "Vidauban", "à Toulon" or "Saint-Raphaël, France".
        if self.state.pending_slot == "location":
            if self._looks_like_location(text):
                location = self._clean_location_candidate(text)
                return ToolPlan(
                    "weather", "WEB_WEATHER",
                    {"location": location, "tomorrow": self.state.tomorrow},
                    "weather",
                )
            # Any non-slot answer is treated as a topic change so the pending
            # state cannot hijack a later unrelated one-word message.
            self.clear()
            return None

        location = self._extract_followup_location(text)
        temporal_only = normalized in {
            "demain", "et demain", "pour demain", "demain ?",
            "aujourd'hui", "aujourd hui", "et aujourd'hui", "et aujourd hui",
            "maintenant", "et maintenant",
        }
        weather_followup = bool(location) or temporal_only
        if not weather_followup:
            # Explicit short weather continuation can also reuse the last place.
            if any(term in normalized for term in ("et la meteo", "et la météo", "quel temps demain", "meteo demain", "météo demain")):
                weather_followup = True
            else:
                return None

        tomorrow = self.state.tomorrow
        if "demain" in normalized:
            tomorrow = True
        elif any(term in normalized for term in ("aujourd'hui", "aujourd hui", "maintenant")):
            tomorrow = False

        return ToolPlan(
            "weather", "WEB_WEATHER",
            {"location": location or self.state.location, "tomorrow": tomorrow},
            "weather",
        )

    def observe(self, plan: ToolPlan | None, result: ToolResult) -> None:
        """Update short-lived context after a tool result on the main thread."""
        self._expire_if_needed()
        if plan is None or plan.name != "weather":
            return

        location = str(plan.args.get("location") or "").strip()
        tomorrow = bool(plan.args.get("tomorrow"))

        if result.source == "missing_location" or not location:
            self._set_weather(
                tomorrow=tomorrow,
                pending_slot="location",
                ttl=settings.WEB_TOOL_PENDING_TTL_SECONDS,
            )
            return

        if result.ok:
            self._set_weather(
                location=location,
                tomorrow=tomorrow,
                pending_slot="",
                ttl=settings.WEB_TOOL_CONTEXT_TTL_SECONDS,
            )
            return

        # If the user supplied a place but the lookup failed, keep a short
        # location slot open so they can immediately correct the place name.
        if result.source == "weather_error":
            self._set_weather(
                tomorrow=tomorrow,
                pending_slot="location",
                ttl=settings.WEB_TOOL_PENDING_TTL_SECONDS,
            )
