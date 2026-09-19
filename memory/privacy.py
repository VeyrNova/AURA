"""Privacy helpers for AURA's local memory subsystem.

The heuristics are intentionally conservative. They are not a substitute for
user consent; they exist to prevent passive/automatic capture of obviously
sensitive material. Explicit user memory commands may still store a sensitive
memory locally, but such records are flagged and are excluded from automatic
LLM context unless the user opts in via settings.
"""
from __future__ import annotations

import re

_SENSITIVE_PATTERNS = [
    # Credentials / financial / secrets
    r"\b(?:mot de passe|password|code pin|code secret|cvv|cryptogramme|iban|bic|num[ée]ro de carte|carte bancaire)\b",
    r"\b(?:token|api key|cl[ée] api|secret key|private key|cl[ée] priv[ée]e)\b",
    # Health and very personal data
    r"\b(?:diagnostiqu[ée]|maladie|cancer|diab[èe]te|traitement m[ée]dical|m[ée]dicament|psychiatr|d[ée]pression|anxi[ée]t[ée])\b",
    r"\b(?:orientation sexuelle|sexualit[ée]|vie sexuelle)\b",
    # Political / religious identity
    r"\b(?:je suis (?:musulman|chr[ée]tien|juif|bouddhiste|hindou|ath[ée]e)|ma religion|je vote pour|mon parti politique)\b",
    # Precise home address / government identifiers
    r"\b(?:mon adresse est|j'habite au|j'habite à)\s+\d{1,5}\b",
    r"\b(?:num[ée]ro de s[ée]curit[ée] sociale|num[ée]ro fiscal|passeport)\b",
]

_SENSITIVE_RE = re.compile("|".join(f"(?:{p})" for p in _SENSITIVE_PATTERNS), re.IGNORECASE)


def looks_sensitive(text: str) -> bool:
    return bool(_SENSITIVE_RE.search(text or ""))
