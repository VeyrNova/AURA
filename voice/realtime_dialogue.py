"""Realtime dialogue helpers for AURA v0.7.0.14.

The UI may display raw LLM tokens immediately, but speech is released only at
complete sentence boundaries.  This keeps spoken output grammatical while
allowing synthesis/playback to overlap the remaining LLM generation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ai.knowledge_quality import deterministic_knowledge_fallback, find_knowledge_risks
from ai.speech_quality import deterministic_french_fallback, find_voice_quality_issues, split_spoken_sentences

_TERMINAL_RE = re.compile(r"[.!?…][\"»”')\]]*$")
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class RealtimeSentenceDecision:
    text: str
    allowed: bool
    reason: str


class RealtimeSentenceBuffer:
    """Incrementally extracts only complete sentences from streamed text."""

    def __init__(self):
        self._buffer = ""

    @property
    def pending(self) -> str:
        return self._buffer

    def feed(self, chunk: str) -> tuple[str, ...]:
        if not chunk:
            return ()
        self._buffer += str(chunk)

        complete: list[str] = []
        working = self._buffer
        # Match from the beginning only. A decimal such as 32.8 is not a
        # boundary because its dot is not followed by whitespace/end-of-text.
        pattern = re.compile(r"^\s*(.+?[.!?…])(?=\s|$)", re.DOTALL)
        while True:
            match = pattern.match(working)
            if match is None:
                break
            sentence = _SPACE_RE.sub(" ", match.group(1)).strip()
            if sentence:
                complete.append(sentence)
            working = working[match.end():]

        if complete:
            self._buffer = working.lstrip()
        return tuple(complete)

    def flush_tail(self) -> str:
        tail = _SPACE_RE.sub(" ", self._buffer).strip()
        self._buffer = ""
        return tail


def prepare_sentence_for_realtime_speech(
    sentence: str,
    *,
    user_text: str = "",
    factual_explanation: bool = False,
) -> RealtimeSentenceDecision:
    """Return a sentence that is safe enough for early speech.

    High-confidence French fixes may be applied deterministically.  A sentence
    that still needs an LLM grammar correction, or a factual sentence with an
    unresolved knowledge risk, is held until the normal final quality pipeline.
    """

    original = _SPACE_RE.sub(" ", (sentence or "").strip())
    if not original or not _TERMINAL_RE.search(original):
        return RealtimeSentenceDecision("", False, "incomplete")

    corrected = deterministic_french_fallback(original)
    if find_voice_quality_issues(corrected):
        return RealtimeSentenceDecision(corrected, False, "quality-hold")

    if factual_explanation:
        risks = find_knowledge_risks(user_text, corrected)
        if risks:
            grounded = deterministic_knowledge_fallback(corrected, user_text)
            if len(find_knowledge_risks(user_text, grounded)) < len(risks):
                corrected = grounded
            else:
                return RealtimeSentenceDecision(corrected, False, "knowledge-hold")

    return RealtimeSentenceDecision(corrected, True, "ready")


def remaining_final_sentences(final_text: str, spoken_sentences: tuple[str, ...]) -> tuple[str, ...]:
    """Return final sentences that have not already been spoken as a prefix."""

    final_sentences = list(split_spoken_sentences(final_text))
    spoken = [re.sub(r"\s+", " ", item).strip() for item in spoken_sentences if item.strip()]
    skip = 0
    for index, item in enumerate(spoken):
        if index >= len(final_sentences):
            break
        candidate = re.sub(r"\s+", " ", final_sentences[index]).strip()
        if candidate != item:
            break
        skip += 1
    return tuple(final_sentences[skip:])
