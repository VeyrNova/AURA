"""Conservative visual-result follow-up detection for AURA v0.7.0.15.4."""
from __future__ import annotations

import re

_REFERENCE_RE = re.compile(
    r"\b(?:les|ces)\s+(?:titres?|id[eé]es?|r[eé]sultats?|options?|lieux?|destinations?|noms?|points?|exemples?|éléments?|elements?)\b"
    r"|\b(?:la|cette)\s+liste\b|\bce\s+r[eé]sultat\b",
    re.IGNORECASE,
)
_TRANSFORM_RE = re.compile(
    r"\b(?:traduis|traduire|mets|mettre|convertis|convertir|classe|classer|trie|trier|"
    r"reformule|reformuler|raccourcis|raccourcir|d[eé]veloppe|développe|ajoute|ajouter|retire|retirer)\b",
    re.IGNORECASE,
)
_PRONOUN_RE = re.compile(r"\b(?:les|ceux|celles|ça|cela|tout ça|tout cela)\b", re.IGNORECASE)


def is_visual_followup_request(text: str) -> bool:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return False
    if _REFERENCE_RE.search(clean):
        return True
    return bool(_TRANSFORM_RE.search(clean) and _PRONOUN_RE.search(clean))
