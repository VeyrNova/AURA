# AURA v0.8.7.2 - spoken product version authority
from __future__ import annotations

import re

from core import version as _version_authority

_DIGITS_FR = {
    "0": "zero",
    "1": "un",
    "2": "deux",
    "3": "trois",
    "4": "quatre",
    "5": "cinq",
    "6": "six",
    "7": "sept",
    "8": "huit",
    "9": "neuf",
}

_SEMVER_RE = re.compile(r"(?<![A-Za-z0-9_])v?\d+(?:\.\d+){2,4}(?![A-Za-z0-9_])", re.I)
_AURA_VERSION_PHRASE_RE = re.compile(
    r"(?i)(\bAURA\b.{0,48}?\bversion\b\s*)v?\d+(?:\.\d+){2,4}"
)


def canonical_product_version() -> str:
    return str(_version_authority.AURA_VERSION)


def _speak_numeric_segment(segment: str) -> str:
    segment = str(segment)
    if len(segment) == 1:
        return _DIGITS_FR.get(segment, segment)
    return " ".join(_DIGITS_FR.get(ch, ch) for ch in segment)


def format_spoken_product_version(version: str | None = None) -> str:
    raw = str(version or canonical_product_version()).strip()
    if raw.lower().startswith("v"):
        raw = raw[1:]
    parts = raw.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError("product version must contain only numeric dot-separated segments")
    return " point ".join(_speak_numeric_segment(part) for part in parts)


def product_identity_text() -> str:
    return "AURA, version " + canonical_product_version()


def product_identity_spoken() -> str:
    return "AURA, version " + format_spoken_product_version()


def is_product_version_query(text: str) -> bool:
    # R1: distinguish AURA self-version questions from questions about
    # Python, Windows, XTTS, bridge, UI, models or other components.
    import unicodedata as _unicodedata

    raw = _unicodedata.normalize("NFKD", str(text or ""))
    norm = raw.encode("ascii", "ignore").decode("ascii").lower()
    norm = " ".join(norm.split())

    if "version" not in norm:
        return False

    explicit_self = (
        "ta version",
        "ton numero de version",
        "ton numero",
        "version d'aura",
        "version de aura",
        "aura version",
        "version aura",
        "version es-tu",
        "version es tu",
        "version tu es",
        "tu es en quelle version",
        "es-tu en quelle version",
        "es tu en quelle version",
    )
    if "aura" in norm or any(term in norm for term in explicit_self):
        return True

    external_subjects = (
        "python",
        "windows",
        "xtts",
        "tts",
        "cuda",
        "bridge",
        "schema",
        "interface",
        "ui",
        "ollama",
        "llama",
        "groq",
        "gemini",
        "piper",
        "whisper",
        "modele",
        "model",
        "driver",
        "nvidia",
        "api",
    )
    if any(subject in norm for subject in external_subjects):
        return False

    compact = norm.strip(" ?!.:;")
    generic_self_only = (
        "quelle version",
        "quel version",
        "version actuelle",
        "version courante",
        "quelle est la version actuelle",
        "quelle est la version courante",
    )
    return compact in generic_self_only


def rewrite_aura_product_version_for_speech(text: str) -> str:
    value = str(text or "")
    spoken = format_spoken_product_version()

    # Exact canonical semver is always safe to verbalize.
    canonical = canonical_product_version()
    exact = re.compile(
        r"(?<![A-Za-z0-9_])v?" + re.escape(canonical) + r"(?![A-Za-z0-9_])",
        re.I,
    )
    value = exact.sub(spoken, value)

    # If AURA identifies herself with any stale numeric semver, the spoken
    # channel fail-closes to the canonical product version. P/RC bridge or
    # protocol labels are intentionally not matched by this rule.
    value = _AURA_VERSION_PHRASE_RE.sub(
        lambda match: match.group(1) + spoken,
        value,
    )
    return value
