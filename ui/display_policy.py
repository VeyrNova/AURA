"""Deterministic visual display policy for AURA's ambient home surface.

Patch 26.4 adds a dedicated UI-command router for the Conversation popup.  The
router is intentionally Qt-free so voice/text variants are resolved before any
LLM or Resource Guardian path is considered.
"""
from __future__ import annotations

import re
import unicodedata


def _normalized(text: str) -> str:
    value = str(text or "").strip().lower().replace("’", "'")
    # Accent-insensitive command matching while leaving the original text intact
    # everywhere else in AURA.
    value = "".join(
        ch for ch in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(ch)
    )
    value = re.sub(r"[\t\r\n]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _strip_aura_address(value: str) -> str:
    """Remove an optional direct address such as ``Aura, ...``."""
    value = re.sub(r"^(?:bonjour|salut|coucou|hello|hey)\s+aura\s*[,;:!?.-]*\s*", "", value)
    value = re.sub(r"^aura\s*[,;:!?.-]*\s*", "", value)
    return value.strip()


def conversation_ui_command(text: str) -> str:
    """Return ``open``, ``close`` or ``""`` for explicit Conversation UI commands.

    These are UI navigation commands, not conversational prompts.  They must be
    handled locally for both typed and spoken input and never require Ollama.
    """
    value = _strip_aura_address(_normalized(text))
    if not value:
        return ""
    value = re.sub(r"[.!?…]+$", "", value).strip()

    conversation = r"(?:mode\s+)?(?:conversation|chat|discussion)"
    window = r"(?:fenetre\s+(?:de\s+|du\s+)?)?"

    open_patterns = (
        rf"^(?:lance|lancer|ouvre|ouvrir|affiche|afficher|active|activer|demarre|demarrer)\s+(?:le\s+|la\s+|du\s+)?{window}{conversation}$",
        rf"^(?:passe|passer|va|aller|bascule|basculer)\s+(?:en|au|sur|a)\s+(?:le\s+|la\s+)?{conversation}$",
        rf"^(?:je\s+veux\s+)?(?:ouvrir|lancer|afficher|activer)\s+(?:le\s+|la\s+)?{conversation}$",
        rf"^mode\s+(?:conversation|chat|discussion)$",
    )
    if any(re.match(pattern, value, flags=re.IGNORECASE) for pattern in open_patterns):
        return "open"

    close_patterns = (
        rf"^(?:ferme|fermer|quitte|quitter|desactive|desactiver|arrete|arreter)\s+(?:le\s+|la\s+)?{window}{conversation}$",
        rf"^(?:sors|sortir)\s+(?:du|de\s+la)\s+{conversation}$",
        r"^(?:retourne|reviens|revient|retour)\s+(?:a|sur)\s+(?:l')?accueil$",
        r"^(?:retour|accueil)$",
    )
    if any(re.match(pattern, value, flags=re.IGNORECASE) for pattern in close_patterns):
        return "close"
    return ""


def is_explicit_conversation_ui_request(text: str) -> bool:
    """True when the user explicitly asks to open the Conversation popup."""
    if conversation_ui_command(text) == "open":
        return True

    # Historical transcript/history requests are kept as explicit Conversation
    # display requests for backwards compatibility.
    value = _normalized(text)
    patterns = (
        r"^(?:ouvre|ouvrir|affiche|afficher|montre|montrer) (?:l'|la )?(?:historique|transcription) (?:de |des )?(?:la )?(?:conversation|messages?)[.!?]?$",
        r"^(?:affiche|montre) (?:mes|les) messages(?: de la conversation)?[.!?]?$",
    )
    return any(re.match(pattern, value, flags=re.IGNORECASE) for pattern in patterns)


def is_close_conversation_ui_request(text: str) -> bool:
    """True only for an explicit request to close the Conversation popup."""
    return conversation_ui_command(text) == "close"
