"""Fail-closed voice brain routing for AURA v0.7.0.15.4."""
from __future__ import annotations

import re
import unicodedata
from enum import Enum


class VoiceRoute(str, Enum):
    VOICE_BRAIN = "voice-brain"
    TEXT_BRAIN = "text-brain"


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().replace("’", "'")
    value = re.sub(r"[^a-z0-9'\s-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


_EXPLANATION_PATTERNS = (
    r"^(?:pourquoi|comment|explique|expliques|explique-moi|peux tu expliquer|peux-tu expliquer)\b",
    r"\b(?:quelle est la cause|quel est le principe|comment fonctionne|comment marche)\b",
    r"\b(?:difference entre|différence entre|compare|comparaison)\b",
)

_FACTUAL_DOMAINS = (
    "science", "scientifique", "physique", "chimie", "biologie", "astronomie",
    "histoire", "historique", "medecine", "médical", "juridique", "droit",
    "finance", "economie", "économie", "definition", "définition", "origine",
)

_SOCIAL_PREFIXES = (
    "bonjour", "bonsoir", "salut", "coucou", "hello", "merci", "ca va", "ça va",
    "comment vas tu", "comment vas-tu", "comment te sens tu", "comment te sens-tu", "bonne nuit",
)


def classify_voice_route(text: str, *, explicitly_factual: bool = False) -> VoiceRoute:
    """Route explanations to the stronger text brain; keep chat on the fast brain."""
    normalized = _normalize(text)
    if not normalized:
        return VoiceRoute.VOICE_BRAIN
    if explicitly_factual:
        return VoiceRoute.TEXT_BRAIN
    if any(normalized.startswith(_normalize(prefix)) for prefix in _SOCIAL_PREFIXES) and len(normalized) < 100:
        return VoiceRoute.VOICE_BRAIN
    if any(re.search(pattern, normalized) for pattern in _EXPLANATION_PATTERNS):
        return VoiceRoute.TEXT_BRAIN
    if any(domain in normalized for domain in (_normalize(item) for item in _FACTUAL_DOMAINS)):
        return VoiceRoute.TEXT_BRAIN
    # Direct conversational/personal questions remain low latency by default.
    return VoiceRoute.VOICE_BRAIN
