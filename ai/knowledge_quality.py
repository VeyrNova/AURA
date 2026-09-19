"""Conservative stable-knowledge quality gate for AURA v0.7.0.9.

This is not a general truth oracle. It only activates for explanatory factual
voice turns and high-confidence risk patterns. Known contradictions can be
fixed deterministically; otherwise an already-resident local voice model may
perform one tiny self-check. Current/live facts remain outside this gate and
must continue through controlled Internet tools.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from ai.speech_quality import split_spoken_sentences
from ai.voice_brevity import is_factual_explanation_request


@dataclass(frozen=True)
class KnowledgeRisk:
    sentence_index: int
    code: str
    excerpt: str


_NEUTRON_MASS_ELECTRON = re.compile(
    r"\bneutrons?\b.*?\b(?:masse|poids)\b.*?\b(?:similaire|semblable|égale?|equivalente?|proche|comparable)\b.*?"
    r"\b(?:protons?)\b.*?\b(?:et|ainsi que)\b.*?\b(?:électrons?|electrons?)\b",
    re.IGNORECASE,
)
_NEUTRON_CHARGE = re.compile(
    r"\bneutrons?\b.*?\bcharge\b.*?\b(?:positive|négative|negative)\b",
    re.IGNORECASE,
)
_NEUTRON_MALFORMED_DEFINITION = re.compile(
    r"(?:noyau\s+d['’]une\s+atomique|nombre\s+neutre|associ[ée]\s+à\s+l['’]hydrogène)",
    re.IGNORECASE,
)
_PROTON_NEGATIVE = re.compile(r"\bprotons?\b.*?\bcharge\b.*?\bnégative\b", re.IGNORECASE)
_ELECTRON_POSITIVE = re.compile(r"\bélectrons?\b.*?\bcharge\b.*?\bpositive\b", re.IGNORECASE)
_SCIENCE_TERMS = re.compile(
    r"\b(?:atome|atomique|neutron|proton|électron|electron|noyau|molécule|molecule|masse|charge|énergie|energie|"
    r"force|gravité|gravite|cellule|adn|gène|gene|virus|bactérie|bacterie)\w*\b",
    re.IGNORECASE,
)
_COMPARISON = re.compile(r"\b(?:similaire|semblable|égal|égale|equivalent|équivalent|proche|identique|comparable)\b", re.IGNORECASE)
_COMPOUND_COMPARISON = re.compile(
    r"\b(?:similaire|semblable|égal|égale|equivalent|équivalent|proche|identique|comparable)\b.{0,100}?\b(?:et|ainsi que)\b",
    re.IGNORECASE,
)
_ABSOLUTE = re.compile(r"\b(?:toujours|jamais|exactement|tous les|toutes les|aucun|aucune)\b", re.IGNORECASE)
_NUMERIC = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)?(?:\s*%|\s*[A-Za-z°]+)?")
_META_PREFIX = re.compile(r"^\s*(?:correction|phrase corrigée|phrase corrigee|voici|réponse|reponse)\s*:?", re.IGNORECASE)
_CURRENT = re.compile(
    r"\b(?:aujourd['’]hui|maintenant|actuellement|en ce moment|cette semaine|ce mois|cette année|cette annee|"
    r"météo|meteo|prix|cours|trafic|score|horaire)\b",
    re.IGNORECASE,
)


def find_knowledge_risks(user_text: str, answer: str) -> tuple[KnowledgeRisk, ...]:
    if not is_factual_explanation_request(user_text):
        return ()
    risks: list[KnowledgeRisk] = []
    question_mentions_neutron = bool(re.search(r"\bneutrons?\b", user_text or "", re.IGNORECASE))
    for index, sentence in enumerate(split_spoken_sentences(answer)):
        context_neutron_mass_error = bool(
            question_mentions_neutron
            and re.search(r"\b(?:masse|poids)\b", sentence, re.IGNORECASE)
            and re.search(r"\bprotons?\b", sentence, re.IGNORECASE)
            and re.search(r"\b(?:électrons?|electrons?)\b", sentence, re.IGNORECASE)
            and _COMPOUND_COMPARISON.search(sentence)
        )
        if context_neutron_mass_error:
            risks.append(KnowledgeRisk(index, "neutron_mass_electron", sentence[:120]))
            continue
        if question_mentions_neutron and _NEUTRON_MALFORMED_DEFINITION.search(sentence):
            risks.append(KnowledgeRisk(index, "neutron_malformed_definition", sentence[:120]))
            continue
        checks: tuple[tuple[str, re.Pattern[str]], ...] = (
            ("neutron_mass_electron", _NEUTRON_MASS_ELECTRON),
            ("neutron_charge", _NEUTRON_CHARGE),
            ("proton_negative", _PROTON_NEGATIVE),
            ("electron_positive", _ELECTRON_POSITIVE),
        )
        matched_specific = False
        for code, pattern in checks:
            match = pattern.search(sentence)
            if match:
                matched_specific = True
                risks.append(KnowledgeRisk(index, code, match.group(0)[:120]))
        if matched_specific:
            continue
        if _SCIENCE_TERMS.search(sentence) and _COMPOUND_COMPARISON.search(sentence):
            risks.append(KnowledgeRisk(index, "compound_science_comparison", sentence[:120]))
        elif _SCIENCE_TERMS.search(sentence) and _ABSOLUTE.search(sentence):
            risks.append(KnowledgeRisk(index, "absolute_science_claim", sentence[:120]))
        elif _SCIENCE_TERMS.search(sentence) and _NUMERIC.search(sentence):
            risks.append(KnowledgeRisk(index, "numeric_science_claim", sentence[:120]))
    return tuple(risks)


def deterministic_knowledge_fallback(sentence: str, user_text: str = "") -> str:
    """Correct only a tiny set of unambiguous stable science contradictions."""
    sentence = re.sub(r"\s+", " ", (sentence or "").strip())
    contextual_neutron_mass = bool(
        re.search(r"\bneutrons?\b", user_text or "", re.IGNORECASE)
        and re.search(r"\b(?:masse|poids)\b", sentence, re.IGNORECASE)
        and re.search(r"\bprotons?\b", sentence, re.IGNORECASE)
        and re.search(r"\b(?:électrons?|electrons?)\b", sentence, re.IGNORECASE)
        and _COMPOUND_COMPARISON.search(sentence)
    )
    if _NEUTRON_MALFORMED_DEFINITION.search(sentence) and re.search(r"\bneutrons?\b", user_text or "", re.IGNORECASE):
        return "Un neutron est une particule subatomique sans charge électrique présente dans le noyau de la plupart des atomes."
    if contextual_neutron_mass or _NEUTRON_MASS_ELECTRON.search(sentence):
        return "Le neutron n'a pas de charge électrique, et sa masse est proche de celle d'un proton."
    if _NEUTRON_CHARGE.search(sentence):
        return "Le neutron n'a pas de charge électrique."
    if _PROTON_NEGATIVE.search(sentence):
        return "Le proton porte une charge électrique positive."
    if _ELECTRON_POSITIVE.search(sentence):
        return "L'électron porte une charge électrique négative."
    return sentence


def knowledge_verification_messages(user_question: str, sentence: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Tu vérifies UNE phrase de connaissance générale stable avant lecture vocale. "
                "Si elle est factuellement correcte, réponds exactement OK. Sinon, corrige uniquement cette phrase en français simple, "
                "une seule phrase courte, sans ajouter de détail incertain. N'utilise aucune information actuelle ou temps réel. "
                "Ne commente pas ta correction."
            ),
        },
        {
            "role": "user",
            "content": f"Question d'origine : {user_question.strip()}\nPhrase à vérifier : {sentence.strip()}",
        },
    ]


def _numbers(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"(?<!\w)[+-]?\d+(?:[.,]\d+)?", text or ""))


def knowledge_candidate_is_safe(original: str, candidate: str) -> bool:
    original = re.sub(r"\s+", " ", (original or "").strip())
    candidate = re.sub(r"\s+", " ", (candidate or "").strip())
    if not original or not candidate or candidate.casefold() == "ok" or _META_PREFIX.search(candidate):
        return False
    if len(split_spoken_sentences(candidate)) != 1 or len(candidate) > 220:
        return False
    if _CURRENT.search(candidate):
        return False
    # A tiny verifier must not silently rewrite numeric claims. Numeric science
    # claims can be flagged, but their correction is rejected unless a future
    # grounded source explicitly supports it.
    if _numbers(original) != _numbers(candidate):
        return False
    similarity = SequenceMatcher(None, original.casefold(), candidate.casefold()).ratio()
    if similarity < 0.28:
        return False
    return True


def fail_closed_knowledge_sentence() -> str:
    """Safe spoken replacement when a flagged stable fact cannot be grounded."""
    return "Je préfère ne pas affirmer ce point sans source fiable."


def replace_knowledge_sentence(text: str, sentence_index: int, replacement: str) -> str:
    sentences = list(split_spoken_sentences(text))
    if not (0 <= sentence_index < len(sentences)):
        return text
    sentences[sentence_index] = replacement.strip()
    return " ".join(sentence for sentence in sentences if sentence).strip()
