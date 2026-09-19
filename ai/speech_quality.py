"""Deterministic French speech quality gate for AURA v0.7.0.13.

The gate is intentionally conservative: it only flags high-confidence language
problems before spoken output. A correction request may then be sent to the
already-resident local voice model. Normal replies incur zero extra LLM calls.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class SpeechQualityIssue:
    sentence_index: int
    code: str
    excerpt: str


# High-confidence patterns only. False negatives are preferable to rewriting a
# correct sentence unnecessarily.
_ISSUE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "article_plural_science",
        re.compile(
            r"\b(?:un|une|du|de la|d['’]un|d['’]une)\s+"
            r"(?:atomes|protons|neutrons|électrons|electrons|particules|noyaux|charges|forces)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "structure_agreement",
        re.compile(
            r"\bstructure\s+(?:stables|complexes|importantes|essentielles)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "role_agreement",
        re.compile(r"\brôle\s+(?:essentielles|importantes|majeures)\b", re.IGNORECASE),
    ),
    (
        "particule_agreement",
        re.compile(r"\bparticule\s+(?:subatomiques|chargées|chargees|neutres)\b", re.IGNORECASE),
    ),
    (
        "dangling_science_adjective",
        re.compile(
            r"\b(?:un|une|d['’]un|d['’]une)\s+(?:atomique|nucléaire|nucleaire|électrique|electrique|chimique|biologique)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "bad_pronoun_y_assurer",
        re.compile(r"\bm['’]y\s+assurer\b", re.IGNORECASE),
    ),
    (
        "missing_elision_me_aider",
        re.compile(r"\bme\s+aider\b", re.IGNORECASE),
    ),
    (
        "missing_elision_te_aider",
        re.compile(r"\bte\s+aider\b", re.IGNORECASE),
    ),
    (
        "missing_elision_se_assurer",
        re.compile(r"\bse\s+assurer\b", re.IGNORECASE),
    ),
    (
        "missing_elision_de_etre",
        re.compile(r"\bde\s+être\b", re.IGNORECASE),
    ),
    (
        "duplicate_word",
        re.compile(r"\b([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'-]{2,})\s+\1\b", re.IGNORECASE),
    ),
)

_FALLBACK_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bd['’]une\s+atomes\b", re.IGNORECASE), "des atomes"),
    (re.compile(r"\bd['’]un\s+atomes\b", re.IGNORECASE), "des atomes"),
    (re.compile(r"\bune\s+atomes\b", re.IGNORECASE), "des atomes"),
    (re.compile(r"\bun\s+atomes\b", re.IGNORECASE), "des atomes"),
    (re.compile(r"\bstructure\s+stables\b", re.IGNORECASE), "structure stable"),
    (re.compile(r"\bstructure\s+complexes\b", re.IGNORECASE), "structure complexe"),
    (re.compile(r"\bstructure\s+importantes\b", re.IGNORECASE), "structure importante"),
    (re.compile(r"\bstructure\s+essentielles\b", re.IGNORECASE), "structure essentielle"),
    (re.compile(r"\bnoyau\s+d['’]une\s+atomique\b", re.IGNORECASE), "noyau d'un atome"),
    (re.compile(r"\bd['’]une\s+atomique\b", re.IGNORECASE), "d'un atome"),
    (re.compile(r"\bune\s+atomique\b", re.IGNORECASE), "un atome"),
    (re.compile(r"\bm['’]y\s+assurer\b", re.IGNORECASE), "m'assurer"),
    (re.compile(r"\bme\s+aider\b", re.IGNORECASE), "m'aider"),
    (re.compile(r"\bte\s+aider\b", re.IGNORECASE), "t'aider"),
    (re.compile(r"\bse\s+assurer\b", re.IGNORECASE), "s'assurer"),
    (re.compile(r"\bde\s+être\b", re.IGNORECASE), "d'être"),
)

_META_PREFIX = re.compile(
    r"^\s*(?:voici|phrase\s+corrigée|phrase\s+corrigee|correction\s*:|version\s+corrigée|version\s+corrigee)",
    re.IGNORECASE,
)


def split_spoken_sentences(text: str) -> tuple[str, ...]:
    """Split conversational prose while retaining terminal punctuation."""
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return ()
    parts = re.findall(r".+?(?:[.!?…](?=\s|$)|$)", clean)
    return tuple(part.strip() for part in parts if part.strip())


def find_voice_quality_issues(text: str) -> tuple[SpeechQualityIssue, ...]:
    issues: list[SpeechQualityIssue] = []
    for index, sentence in enumerate(split_spoken_sentences(text)):
        for code, pattern in _ISSUE_PATTERNS:
            match = pattern.search(sentence)
            if match:
                issues.append(
                    SpeechQualityIssue(
                        sentence_index=index,
                        code=code,
                        excerpt=match.group(0)[:80],
                    )
                )
    return tuple(issues)


def quality_correction_messages(sentence: str) -> list[dict[str, str]]:
    """Build a tiny local correction request that forbids factual rewriting."""
    return [
        {
            "role": "system",
            "content": (
                "Tu es un correcteur grammatical français strict. Corrige uniquement les erreurs de français "
                "de la phrase fournie. Ne change aucun fait, nombre, nom propre, unité, degré de certitude ni sens. "
                "N'ajoute aucune information. Renvoie uniquement la phrase corrigée, sans commentaire."
            ),
        },
        {"role": "user", "content": sentence.strip()},
    ]


def _numbers(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"(?<!\w)[+-]?\d+(?:[.,]\d+)?", text or ""))


def correction_is_safe(original: str, candidate: str) -> bool:
    original = re.sub(r"\s+", " ", (original or "").strip())
    candidate = re.sub(r"\s+", " ", (candidate or "").strip())
    if not original or not candidate or _META_PREFIX.search(candidate):
        return False
    if _numbers(original) != _numbers(candidate):
        return False
    ratio = len(candidate) / max(1, len(original))
    if ratio < 0.55 or ratio > 1.45:
        return False
    similarity = SequenceMatcher(None, original.casefold(), candidate.casefold()).ratio()
    if similarity < 0.55:
        return False
    # A correction must not make the high-confidence issue count worse.
    if len(find_voice_quality_issues(candidate)) > len(find_voice_quality_issues(original)):
        return False
    return True


def deterministic_french_fallback(sentence: str) -> str:
    result = sentence
    for pattern, replacement in _FALLBACK_REPLACEMENTS:
        result = pattern.sub(replacement, result)
    # Collapse accidental immediate duplicate words while preserving the first.
    result = re.sub(
        r"\b([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'-]{2,})\s+\1\b",
        r"\1",
        result,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", result).strip()


def replace_sentence(text: str, sentence_index: int, replacement: str) -> str:
    sentences = list(split_spoken_sentences(text))
    if not (0 <= sentence_index < len(sentences)):
        return text
    sentences[sentence_index] = replacement.strip()
    return " ".join(sentence for sentence in sentences if sentence).strip()
