"""Voice brevity policy for AURA v0.7.0.14.

The policy is deterministic. It shapes spoken LLM turns toward a short first
sentence and a compact 2-3 sentence answer, while preserving a larger budget
when the user explicitly asks for detail. Trimming only happens on complete
sentence boundaries; no mid-sentence text is ever invented or cut.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ai.speech_quality import split_spoken_sentences


_FACTUAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*(?:explique(?:-moi)?|définis|definis)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:qu['’]est[- ]ce que|c['’]est quoi|qui est|que signifie)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:comment fonctionne|à quoi sert|a quoi sert|pourquoi)\b", re.IGNORECASE),
    re.compile(r"\b(?:quelle est|quelles sont)\s+(?:la différence|les différences|le rôle|les rôles)\b", re.IGNORECASE),
)
_DETAIL_PATTERN = re.compile(
    r"\b(?:en détail|en details|détaill(?:e|é|ée|és|ées)|detaille|approfondis|approfondir|complet(?:e|ement)?|"
    r"précisément|precisement|longuement|pas à pas|pas a pas|développe|developpe)\b",
    re.IGNORECASE,
)
_CURRENT_PATTERN = re.compile(
    r"\b(?:aujourd['’]hui|maintenant|actuel(?:le|les|lement)?|en ce moment|météo|meteo|actualité|actualite|"
    r"prix|cours|trafic|score|horaire|disponibilit)\b",
    re.IGNORECASE,
)

_EXPLICIT_LENGTH_PATTERN = re.compile(
    r"\b(?:en\s+)?(?P<count>\d{1,2})\s*(?P<unit>"
    r"lignes?|phrases?|points?|étapes?|etapes?|paragraphes?|mots?"
    r")\b",
    re.IGNORECASE,
)


_MEMORY_VOICE_QUERY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bcomment\s+dois[- ]?tu\s+me\s+r[ée]pondre\b", re.IGNORECASE),
    re.compile(r"\bcomment\s+(?:me\s+r[ée]ponds[- ]?tu|dois[- ]?tu\s+t['’]?adapter(?:\s+[àa]\s+moi)?)\b", re.IGNORECASE),
    re.compile(r"\b(?:qu['’]est[- ]ce\s+que|que)\s+tu\s+sais\s+de\s+moi\b", re.IGNORECASE),
    re.compile(r"\bque\s+sais[- ]?tu\s+de\s+moi\b", re.IGNORECASE),
    re.compile(r"\b(?:quelles?\s+sont\s+)?mes\s+(?:pr[ée]f[ée]rences?|habitudes?|objectifs?|projets?)\b", re.IGNORECASE),
    re.compile(r"\b(?:souviens[- ]?toi|te\s+souviens[- ]?tu|rappelle[- ]?toi)\b", re.IGNORECASE),
    re.compile(r"\b(?:dans|selon)\s+(?:ta|notre)\s+m[ée]moire\b", re.IGNORECASE),
)

_EXPLICIT_VISUAL_DELIVERY_PATTERN = re.compile(
    r"\b(?:affiche|montre|fais[- ]?moi\s+voir|mets?|pr[ée]sente)\b.*"
    r"\b(?:[àa]\s+l['’]?[ée]cran|tableau|liste|fen[êe]tre|visuel|graphique)\b|"
    r"\b(?:[àa]\s+l['’]?[ée]cran|dans\s+un\s+tableau|sous\s+forme\s+de\s+liste)\b",
    re.IGNORECASE,
)


def is_memory_voice_query(text: str) -> bool:
    """Return True when a memory/personal-context answer should be spoken."""
    clean = re.sub(r"\s+", " ", str(text or "").strip())
    if not clean or _EXPLICIT_VISUAL_DELIVERY_PATTERN.search(clean):
        return False
    return any(pattern.search(clean) for pattern in _MEMORY_VOICE_QUERY_PATTERNS)


@dataclass(frozen=True)
class VoiceBrevityPolicy:
    factual_explanation: bool
    detailed: bool
    max_sentences: int
    max_chars: int
    first_sentence_target: int
    explicit_length: bool = False
    requested_count: int | None = None
    requested_unit: str | None = None


def last_user_text(messages: list[dict[str, str]] | tuple[dict[str, str], ...]) -> str:
    for message in reversed(messages or []):
        if message.get("role") == "user":
            return str(message.get("content") or "").strip()
    return ""


def is_factual_explanation_request(text: str) -> bool:
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean or _CURRENT_PATTERN.search(clean):
        return False
    return any(pattern.search(clean) for pattern in _FACTUAL_PATTERNS)


def voice_brevity_policy(
    user_text: str,
    *,
    max_sentences: int = 3,
    max_chars: int = 320,
    detail_max_sentences: int = 5,
    detail_max_chars: int = 560,
    first_sentence_target: int = 85,
) -> VoiceBrevityPolicy:
    value = str(user_text or "")
    explicit_match = _EXPLICIT_LENGTH_PATTERN.search(value)
    requested_count: int | None = None
    requested_unit: str | None = None
    explicit_length = False

    if explicit_match:
        requested_count = max(1, min(24, int(explicit_match.group("count"))))
        requested_unit = str(explicit_match.group("unit") or "").casefold()
        explicit_length = True

    detailed = bool(_DETAIL_PATTERN.search(value)) or explicit_length
    sentence_budget = max(1, int(detail_max_sentences if detailed else max_sentences))
    char_budget = max(80, int(detail_max_chars if detailed else max_chars))

    # P0.6.2.3.4 — an explicit user length/format request takes precedence over
    # AURA's default voice brevity. The budget is still bounded, but it is large
    # enough for the requested result instead of silently collapsing "10 lignes"
    # to the default 2–3 spoken sentences.
    if explicit_length and requested_count is not None:
        unit = requested_unit or ""
        if unit.startswith(("ligne", "phrase", "point", "étape", "etape")):
            sentence_budget = max(sentence_budget, requested_count + 2)
            char_budget = max(char_budget, min(2800, requested_count * 140))
        elif unit.startswith("paragraphe"):
            sentence_budget = max(sentence_budget, min(24, requested_count * 4))
            char_budget = max(char_budget, min(3600, requested_count * 320))
        elif unit.startswith("mot"):
            sentence_budget = max(sentence_budget, 10)
            char_budget = max(char_budget, min(3200, requested_count * 9))

    return VoiceBrevityPolicy(
        factual_explanation=is_factual_explanation_request(value),
        detailed=detailed,
        max_sentences=sentence_budget,
        max_chars=char_budget,
        first_sentence_target=max(40, int(first_sentence_target)),
        explicit_length=explicit_length,
        requested_count=requested_count,
        requested_unit=requested_unit,
    )


def voice_output_contract(policy: VoiceBrevityPolicy) -> str:
    if policy.explicit_length and policy.requested_count:
        unit = policy.requested_unit or "unités"
        length_line = (
            f"- PRIORITÉ FORMAT UTILISATEUR : il demande explicitement environ "
            f"{policy.requested_count} {unit}. Respecte cette longueur/structure ; "
            "la consigne explicite de l'utilisateur prime sur la brièveté vocale par défaut."
        )
        list_line = (
            "- Les retours à la ligne, numéros ou puces sont autorisés si la structure demandée les justifie."
        )
    elif policy.detailed:
        length_line = (
            f"- L'utilisateur demande du détail : reste néanmoins oral et structuré, maximum {policy.max_sentences} phrases "
            f"et environ {policy.max_chars} caractères."
        )
        list_line = "- Pas de liste à puces dans une réponse parlée courte ; préfère des phrases complètes."
    else:
        length_line = (
            f"- Réponse parlée par défaut : 2 à {policy.max_sentences} phrases courtes, environ {policy.max_chars} caractères maximum."
        )
        list_line = "- Pas de liste à puces dans une réponse parlée courte ; préfère des phrases complètes."

    fact_line = (
        "- Pour une explication factuelle, donne d'abord la définition essentielle puis un seul complément utile. "
        "Omet les détails incertains plutôt que de les improviser."
        if policy.factual_explanation and not policy.explicit_length
        else "- Réponds directement sans préambule inutile."
    )
    return (
        "VOICE OUTPUT CONTRACT v0.7.0.14\n"
        f"{length_line}\n"
        f"- Première phrase volontairement courte : vise au plus {policy.first_sentence_target} caractères et une seule idée.\n"
        f"{list_line}\n"
        "- Français naturel obligatoire : élisions correctes (m'aider, s'assurer, d'être), accords corrects, aucune tournure calquée mot à mot.\n"
        f"{fact_line}"
    )


def apply_voice_output_contract(messages: list[dict[str, str]], policy: VoiceBrevityPolicy) -> list[dict[str, str]]:
    result = [dict(message) for message in messages]
    contract = voice_output_contract(policy)
    for message in result:
        if message.get("role") == "system":
            message["content"] = f"{message.get('content', '').rstrip()}\n\n{contract}"
            return result
    result.insert(0, {"role": "system", "content": contract})
    return result


def trim_spoken_reply(text: str, policy: VoiceBrevityPolicy) -> tuple[str, bool]:
    """Trim only complete trailing sentences to the spoken budget."""
    raw = str(text or "").strip()
    clean = re.sub(r"\s+", " ", raw)
    sentences = list(split_spoken_sentences(clean))
    if not sentences:
        return raw if policy.explicit_length else clean, False

    # P0.6.2.3.4 — preserve line breaks / explicit structure when the model
    # already respected the user's requested length inside the expanded budget.
    if (
        policy.explicit_length
        and len(clean) <= policy.max_chars
        and len(sentences) <= policy.max_sentences
    ):
        return raw, False

    selected: list[str] = []
    for sentence in sentences:
        if len(selected) >= policy.max_sentences:
            break
        candidate = " ".join(selected + [sentence]).strip()
        # Always keep at least the first complete sentence, even if a model
        # ignored the requested size. Never cut it mid-sentence.
        if selected and len(candidate) > policy.max_chars:
            break
        selected.append(sentence)
    trimmed = " ".join(selected).strip() or sentences[0]
    return trimmed, trimmed != clean


def concise_voice_handoff(
    text: str,
    *,
    preserve_short: bool = True,
    max_chars: int | None = None,
    max_sentences: int | None = None,
    long_reply: str | None = None,
) -> tuple[str, bool]:
    """Return the short spoken handoff for a visual-first AURA response.

    Existing short replies (weather, confirmations, terse conversational turns)
    are preserved. Long visual answers become a deterministic acknowledgement
    instead of being re-summarized by another model.
    """
    from config.settings import settings

    clean = re.sub(r"\s+", " ", str(text or "").strip())
    if not clean:
        return "", False
    if not settings.VOICE_CONCISE_ENABLED:
        return clean, False
    char_limit = max(40, int(max_chars if max_chars is not None else settings.VOICE_CONCISE_MAX_CHARS))
    sentence_limit = max(1, int(max_sentences if max_sentences is not None else settings.VOICE_CONCISE_MAX_SENTENCES))
    sentences = list(split_spoken_sentences(clean))
    if preserve_short and len(clean) <= char_limit and len(sentences) <= sentence_limit:
        return clean, False
    fallback = str(long_reply if long_reply is not None else settings.VOICE_CONCISE_LONG_REPLY).strip()
    if not fallback:
        fallback = "Je t'affiche le détail à l'écran."
    return fallback, fallback != clean


_PRIVATE_CLOUD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:mot de passe|password|code pin|code secret|api[ _-]?key|clé api|cle api|token|secret)\b", re.IGNORECASE),
    re.compile(r"\b(?:note privée|note privee|mémoire privée|memoire privee|confidentiel|confidentielle)\b", re.IGNORECASE),
    re.compile(r"\b(?:numéro de carte|numero de carte|cvv|iban|bic)\b", re.IGNORECASE),
)


def cloud_voice_content_allowed(user_text: str, spoken_text: str) -> bool:
    """Conservative privacy gate for optional cloud TTS.

    Selecting a cloud TTS provider is an explicit cloud opt-in, but AURA still keeps
    obviously sensitive prompts local by default. This is intentionally a
    small fail-closed lexical gate, not a security classifier.
    """
    from config.settings import settings

    if not settings.CLOUD_TTS_PRIVATE_CONTENT_LOCAL_ONLY:
        return True
    combined = f"{user_text or ''}\n{spoken_text or ''}"
    return not any(pattern.search(combined) for pattern in _PRIVATE_CLOUD_PATTERNS)
