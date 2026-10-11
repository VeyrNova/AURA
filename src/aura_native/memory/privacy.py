"""Conservative local sensitivity tagging.

This is a guard for passive use of memories, not a substitute for user consent.
Explicitly stored sensitive memories stay local and are excluded from list/search
unless the caller explicitly requests them.
"""
from __future__ import annotations
import re

_PATTERNS = [
    r"\b(?:mot de passe|password|code pin|code secret|cvv|cryptogramme|iban|bic|numero de carte|carte bancaire)\b",
    r"\b(?:token|api key|cle api|secret key|private key|cle privee)\b",
    r"\b(?:diagnostique|maladie|cancer|diabete|traitement medical|medicament|psychiatr|depression|anxiete)\b",
    r"\b(?:orientation sexuelle|sexualite|vie sexuelle)\b",
    r"\b(?:ma religion|je vote pour|mon parti politique)\b",
    r"\b(?:mon adresse est|j'habite au|j'habite a)\s+\d{1,5}\b",
    r"\b(?:numero de securite sociale|numero fiscal|passeport)\b",
]
_SENSITIVE_RE = re.compile("|".join(f"(?:{p})" for p in _PATTERNS), re.IGNORECASE)

def looks_sensitive(text: str) -> bool:
    return bool(_SENSITIVE_RE.search(text or ""))
