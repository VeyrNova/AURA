"""Deterministic zero-LLM replies for tiny social and self-state turns.

These functions are intentionally local and side-effect free. They keep AURA's
social identity available even when no cloud provider is needed and no local
LLM is installed. They never answer external factual questions.
"""
from __future__ import annotations

import re
import unicodedata


def _normalize(text: str) -> str:
    value = str(text or "").strip().casefold().replace("’", "'")
    value = value.replace("'", " ")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9' ]+", " ", value)
    return " ".join(value.split()).strip(" .!?")


def social_reply(
    text: str,
    *,
    mode: str = "NORMAL",
    familiarity: float = 0.0,
    returning: bool = False,
    private: bool = False,
    learning_revision: int = 0,
    learned_preferences: int = 0,
    **_ignored,
) -> str:
    del mode, familiarity, returning, private, learning_revision, learned_preferences
    q = _normalize(text)
    if not q:
        return ""
    if q in {"bonjour", "bonjour aura", "salut", "salut aura", "bonsoir", "bonsoir aura"}:
        return "Bonjour. Je suis opérationnelle."
    if q in {"merci", "merci aura", "merci beaucoup", "merci beaucoup aura"}:
        return "Avec plaisir."
    if q in {
        "ca va", "ca va aura", "comment vas tu", "comment vas tu aura",
        "comment allez vous", "comment allez vous aura",
    }:
        return "Oui, tout va bien. Je suis opérationnelle."
    return ""


def self_reply(
    text: str,
    *,
    mode: str = "NORMAL",
    familiarity: float = 0.0,
    returning: bool = False,
    private: bool = False,
    learning_revision: int = 0,
    learned_preferences: int = 0,
    **_ignored,
) -> str:
    """Answer only direct questions about AURA's own functional inner state."""
    del mode, familiarity, returning, private, learning_revision, learned_preferences
    q = _normalize(text)
    if not q:
        return ""

    # Do not hijack questions about another person, character, film, book, etc.
    external_markers = {
        "personnage", "film", "serie", "livre", "roman", "acteur", "actrice",
        "il ressent", "elle ressent", "ils ressentent", "elles ressentent",
    }
    if any(marker in q for marker in external_markers):
        return ""

    direct_patterns = (
        r"^(?:qu est ce que )?tu ressens(?: quoi)?$",
        r"^(?:qu est ce que )?tu ressents(?: quoi)?$",  # common STT typo
        r"^(?:qu est ce que )?tu eprouves(?: quoi)?$",
        r"^que ressens tu$",
        r"^que ressents tu$",
        r"^qu eprouves tu$",
        r"^comment tu te sens$",
        r"^comment te sens tu$",
    )
    if any(re.fullmatch(pattern, q) for pattern in direct_patterns):
        return (
            "Je n’éprouve pas d’émotions comme un humain, mais mon état fonctionnel est stable, "
            "attentif et orienté vers notre échange."
        )
    return ""

# AURA v0.8.7.2 - canonical self version reply
from core.spoken_version import (
    canonical_product_version as _aura_v0872_product_version,
    is_product_version_query as _aura_v0872_is_product_version_query,
)


_aura_v0872_original_self_reply = self_reply


def self_reply(*args, **kwargs):
    _texts = [x for x in args if isinstance(x, str)]
    _texts.extend(x for x in kwargs.values() if isinstance(x, str))
    _joined = " ".join(_texts)
    if _aura_v0872_is_product_version_query(_joined):
        return "Je suis AURA, version " + _aura_v0872_product_version() + "."
    return _aura_v0872_original_self_reply(*args, **kwargs)

