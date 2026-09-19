"""AURA visual mood palette and deterministic local tone inference.

Patch 04 keeps emotion as a visual accent, not a second personality engine.
The orb always remains inside AURA's cyan/violet/magenta identity while the
current response tone biases the neural network colour. No network/model call
is required and no user profile is inferred from this helper.
"""
from __future__ import annotations

import re

MOOD_PALETTES = {
    "neutral": ((0.08, 0.76, 1.00), (0.64, 0.30, 1.00)),
    "warm":    ((0.28, 0.78, 1.00), (0.94, 0.34, 0.82)),
    "focused": ((0.03, 0.88, 1.00), (0.30, 0.48, 1.00)),
    "creative":((0.36, 0.46, 1.00), (0.92, 0.25, 1.00)),
    "soft":    ((0.34, 0.78, 1.00), (0.78, 0.48, 0.94)),
    "alert":   ((0.98, 0.22, 0.46), (1.00, 0.16, 0.72)),
}

MOOD_STRENGTH = {
    "neutral": 0.00,
    "warm": 0.66,
    "focused": 0.68,
    "creative": 0.72,
    "soft": 0.60,
    "alert": 0.82,
}


def normalize_mood(value: str | None) -> str:
    mood = str(value or "neutral").strip().lower()
    return mood if mood in MOOD_PALETTES else "neutral"


def mood_palette(value: str | None):
    return MOOD_PALETTES[normalize_mood(value)]


def _contains(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def infer_aura_mood(text: str | None) -> str:
    """Infer the *response tone* used only for orb colour animation.

    The ordering is intentional: safety/error language wins, then empathy,
    creativity, analysis and finally warm conversational language. Unknown or
    mixed text remains neutral, preventing colourful overreaction.
    """
    s = re.sub(r"\\s+", " ", str(text or "").casefold()).strip()
    if not s:
        return "neutral"

    if _contains(s, (
        "erreur", "échec", "echec", "impossible", "alerte", "attention",
        "danger", "critique", "bloqué", "bloque", "refus", "indisponible",
    )):
        return "alert"
    if _contains(s, (
        "désolé", "desole", "je comprends", "courage", "difficile",
        "inquiet", "inquiét", "prends soin", "doucement", "soutien",
    )):
        return "soft"
    if _contains(s, (
        "cré", "imagin", "concept", "design", "musique", "paroles",
        "inspir", "visuel", "artist", "story", "pochette", "ambiance",
    )):
        return "creative"
    if _contains(s, (
        "analyse", "diagnostic", "calcul", "vérif", "verif", "donnée",
        "donnee", "mesure", "résultat", "resultat", "configuration",
        "paramètre", "parametre", "étape", "etape", "compar", "test",
    )):
        return "focused"
    if _contains(s, (
        "parfait", "super", "excellent", "avec plaisir", "bien sûr",
        "bien sur", "merci", "bonne nouvelle", "prêt", "prete", "prête",
        "content", "heureux", "génial", "genial",
    )):
        return "warm"
    return "neutral"
