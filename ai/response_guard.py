"""Deterministic response-finalization helpers for AURA voice turns.

The local LLM can occasionally stop exactly at its num_predict budget.  This
module never invents facts; it only detects obviously unfinished surface forms,
merges a short continuation, or trims an unpronounceable dangling fragment.
"""
from __future__ import annotations

import re

_TERMINAL_RE = re.compile(r"[.!?…](?:[\"'»”’\])}]*)$")
_SENTENCE_BOUNDARY_RE = re.compile(r"[.!?…](?:[\"'»”’\])}]*)\s+")
_DANGLING_WORDS = frozenset({
    "a", "à", "afin", "avec", "car", "ce", "ces", "cet", "cette", "comme",
    "dans", "de", "des", "donc", "du", "en", "et", "la", "le", "les", "leur",
    "mais", "ou", "par", "parce", "pour", "puis", "que", "qui", "sans", "si",
    "son", "sa", "ses", "sur", "un", "une", "vers", "dont", "lorsque", "quand",
})


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def has_unclosed_delimiter(text: str) -> bool:
    """Conservative delimiter check for obvious truncation such as ``(...``."""
    text = text or ""
    pairs = (("(", ")"), ("[", "]"), ("{", "}"))
    return any(text.count(opener) > text.count(closer) for opener, closer in pairs)


def looks_incomplete(text: str) -> bool:
    """Return True only for strong surface evidence of an unfinished answer."""
    value = _clean(text)
    if not value:
        return True
    if has_unclosed_delimiter(value):
        return True
    if value.endswith((",", ";", ":", "(", "[", "{", "/", "-", "–", "—")):
        return True
    if _TERMINAL_RE.search(value):
        return False
    # Without terminal punctuation, only flag an ending that is grammatically
    # very unlikely to be intentional.  The token-budget gate adds another
    # protection against false positives.
    words = re.findall(r"[A-Za-zÀ-ÿŒœ'-]+", value)
    return bool(words and words[-1].casefold() in _DANGLING_WORDS)


def hit_generation_ceiling(output_tokens: int, num_predict: int, *, margin: int = 4, done_reason: str = "") -> bool:
    reason = (done_reason or "").strip().casefold()
    if reason in {"length", "max_tokens", "limit"}:
        return True
    try:
        return int(output_tokens) >= max(1, int(num_predict) - max(0, int(margin)))
    except (TypeError, ValueError):
        return False


def needs_voice_completion(
    text: str,
    *,
    output_tokens: int,
    num_predict: int,
    margin: int = 4,
    done_reason: str = "",
) -> bool:
    if not hit_generation_ceiling(output_tokens, num_predict, margin=margin, done_reason=done_reason):
        return False
    value = _clean(text)
    # P0.6.2.3.3 — an explicit provider MAX_TOKENS/length stop plus missing
    # terminal punctuation is itself strong truncation evidence. This catches
    # fragments such as "Le premier chapitre présente Mon" which the older
    # dangling-word heuristic could not identify.
    if value and not _TERMINAL_RE.search(value):
        return True
    return looks_incomplete(value)


def complete_sentence_prefix(text: str) -> tuple[str, str]:
    """Split streaming text into complete-sentence prefix + held tail."""
    value = text or ""
    last = 0
    for match in _SENTENCE_BOUNDARY_RE.finditer(value):
        last = match.end()
    if last <= 0:
        return "", value
    return value[:last], value[last:]


def merge_continuation(original: str, continuation: str) -> str:
    """Append a continuation while removing a short repeated word overlap."""
    original = _clean(original)
    continuation = _clean(continuation)
    if not continuation:
        return original
    if not original:
        return continuation

    left = original.split()
    right = continuation.split()
    overlap = 0
    max_overlap = min(12, len(left), len(right))
    for size in range(max_overlap, 0, -1):
        a = " ".join(left[-size:]).casefold().strip(" ,.;:!?…")
        b = " ".join(right[:size]).casefold().strip(" ,.;:!?…")
        if a and a == b:
            overlap = size
            break
    suffix = " ".join(right[overlap:]).strip()
    if not suffix:
        return original
    if original.endswith(("(", "[", "{", "/", "-", "–", "—")):
        return f"{original}{suffix}"
    return f"{original} {suffix}".strip()


def trim_incomplete_tail(text: str) -> str:
    """Drop only a dangling final fragment; keep all complete sentences."""
    value = _clean(text)
    if not value or not looks_incomplete(value):
        return value
    # Find the last terminal sentence boundary anywhere in the response.
    matches = list(re.finditer(r"[.!?…](?:[\"'»”’\])}]*)", value))
    if matches:
        return value[: matches[-1].end()].strip()
    return ""



def finalize_voice_reply(
    text: str,
    *,
    output_tokens: int,
    num_predict: int,
    margin: int = 4,
    done_reason: str = "",
    continuation: str = "",
) -> tuple[str, bool]:
    """Finalize one voice reply without touching network or UI state.

    Returns ``(final_text, guard_triggered)``.  A caller may first use
    ``needs_voice_completion`` to decide whether to ask the local LLM for the
    short continuation, then pass that continuation here.
    """
    value = _clean(text)
    triggered = needs_voice_completion(
        value,
        output_tokens=output_tokens,
        num_predict=num_predict,
        margin=margin,
        done_reason=done_reason,
    )
    if not triggered:
        return value, False
    if continuation:
        value = merge_continuation(value, continuation)
    if looks_incomplete(value):
        trimmed = trim_incomplete_tail(value)
        value = trimmed or "Je n'ai pas réussi à terminer cette réponse proprement."
    return value, True

def continuation_messages(messages: list[dict[str, str]], partial_reply: str) -> list[dict[str, str]]:
    """Build an ephemeral local-only continuation request.

    The instruction is never persisted in conversation history.
    """
    return [
        *messages,
        {"role": "assistant", "content": partial_reply},
        {
            "role": "user",
            "content": (
                "Termine uniquement la phrase inachevée juste au-dessus. "
                "Réponds seulement avec la suite immédiate nécessaire, sans répéter le début, "
                "sans ajouter de nouveau sujet, puis termine par une ponctuation finale."
            ),
        },
    ]
