from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
import threading
from typing import Iterable, Mapping, Sequence


VERSION = "0.7.0.15"


class MemoryAction(str, Enum):
    KEEP_RESIDENT = "keep-resident"
    TRIM_CACHES = "trim-caches"
    UNLOAD_VOICE_BRAIN = "unload-voice-brain"


@dataclass(frozen=True)
class MemoryBands:
    """AURA 0.7.0.15 RAM policy.

    The old 88% hard cut caused load/unload thrashing. 0.7.0.15 turns 88%
    into a warning band and only unloads the voice brain under critical
    pressure. Hysteresis prevents immediate reloading/unloading loops.
    """

    warning_percent: float = 88.0
    soft_percent: float = 91.0
    critical_percent: float = 94.0
    recovery_percent: float = 87.0
    critical_available_gib: float = 1.15
    reload_min_available_gib: float = 2.15


@dataclass(frozen=True)
class MemoryDecision:
    action: MemoryAction
    reason: str
    allow_voice_prewarm: bool
    pressure_latched: bool


class MemoryPressureStateMachine:
    """Small hysteretic state machine for Dual Brain RAM arbitration."""

    def __init__(self, bands: MemoryBands | None = None) -> None:
        self.bands = bands or MemoryBands()
        self._pressure_latched = False

    @property
    def pressure_latched(self) -> bool:
        return self._pressure_latched

    def evaluate(
        self,
        *,
        ram_percent: float,
        available_gib: float,
        voice_brain_loaded: bool,
        xtts_hot: bool,
        predicted_with_voice_percent: float | None = None,
        predicted_available_after_gib: float | None = None,
    ) -> MemoryDecision:
        b = self.bands

        critical = (
            ram_percent >= b.critical_percent
            or available_gib <= b.critical_available_gib
        )
        soft = ram_percent >= b.soft_percent
        warning = ram_percent >= b.warning_percent

        if critical:
            self._pressure_latched = True
            return MemoryDecision(
                MemoryAction.UNLOAD_VOICE_BRAIN if voice_brain_loaded else MemoryAction.TRIM_CACHES,
                f"critical-memory ram={ram_percent:.1f}% avail={available_gib:.2f}GiB",
                False,
                True,
            )

        # Once critical pressure happened, do not instantly reload the model.
        if self._pressure_latched:
            recovered = (
                ram_percent <= b.recovery_percent
                and available_gib >= b.reload_min_available_gib
            )
            if not recovered:
                return MemoryDecision(
                    MemoryAction.KEEP_RESIDENT if voice_brain_loaded else MemoryAction.TRIM_CACHES,
                    f"hysteresis-hold ram={ram_percent:.1f}% avail={available_gib:.2f}GiB",
                    False,
                    True,
                )
            self._pressure_latched = False

        # Prewarm is predictive: it may be blocked without forcing an already-hot
        # model to unload. This is the key change vs the previous 88% hard cut.
        predicted_bad = False
        if predicted_with_voice_percent is not None:
            predicted_bad |= predicted_with_voice_percent >= b.critical_percent
        if predicted_available_after_gib is not None:
            predicted_bad |= predicted_available_after_gib <= b.critical_available_gib

        if soft:
            return MemoryDecision(
                MemoryAction.KEEP_RESIDENT if voice_brain_loaded else MemoryAction.TRIM_CACHES,
                f"soft-pressure ram={ram_percent:.1f}% keep-hot={voice_brain_loaded}",
                False if not voice_brain_loaded else True,
                False,
            )

        if warning:
            return MemoryDecision(
                MemoryAction.KEEP_RESIDENT,
                f"warning-band ram={ram_percent:.1f}% no-thrash",
                voice_brain_loaded or not predicted_bad,
                False,
            )

        allow_prewarm = not predicted_bad
        return MemoryDecision(
            MemoryAction.KEEP_RESIDENT,
            "normal-memory",
            allow_prewarm,
            False,
        )


class PrewarmCancelled(RuntimeError):
    pass


class PrewarmCancellationToken:
    """Cooperative cancellation token with generation/epoch semantics.

    A background prewarm captures the current epoch. Any user activity bumps
    the epoch and sets the event. Work must call `checkpoint(epoch)` between
    expensive phases and before claiming success.
    """

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._epoch = 0

    def begin(self) -> int:
        with self._lock:
            self._event.clear()
            return self._epoch

    def cancel_for_user_activity(self) -> int:
        with self._lock:
            self._epoch += 1
            self._event.set()
            return self._epoch

    def cancelled(self, epoch: int) -> bool:
        with self._lock:
            stale = epoch != self._epoch
        return stale or self._event.is_set()

    def checkpoint(self, epoch: int) -> None:
        if self.cancelled(epoch):
            raise PrewarmCancelled("voice prewarm preempted by user activity")


class KnowledgeRoute(str, Enum):
    VOICE_BRAIN = "voice-brain"
    TEXT_BRAIN = "text-brain"
    INTERNET_TOOL = "internet-tool"


_TOOL_PATTERNS = (
    r"\bm[ée]t[ée]o\b",
    r"\btemp[ée]rature\b",
    r"\bpluie\b",
    r"\bvent\b",
    r"\bactualit[ée]s?\b",
    r"\baujourd['’]hui\b",
    r"\bmaintenant\b",
    r"\bheure\b",
    r"\bprix\b",
    r"\bcours\b",
)

_EXPLANATION_PATTERNS = (
    r"\bpourquoi\b",
    r"\bcomment (?:fonctionne|marche|se forme|s['’]explique)\b",
    r"\bexplique(?:-moi)?\b",
    r"\bquelle est la cause\b",
    r"\bqu['’]est[- ]ce que\b",
    r"\bd[ée]finis?\b",
    r"\bdiff[ée]rence entre\b",
)

_CONVERSATIONAL_PATTERNS = (
    r"\bbonjour\b",
    r"\bbonsoir\b",
    r"\bsalut\b",
    r"\bmerci\b",
    r"\bcomment vas[- ]tu\b",
    r"\bcomment allez[- ]vous\b",
    r"\bça va\b",
)


def route_voice_query(text: str, *, explicitly_factual: bool = False) -> KnowledgeRoute:
    """Fail-closed routing for spoken queries.

    Explanatory factual questions go to the larger text brain. Fresh external
    facts go to an internet tool. Casual dialogue stays on the fast 3B brain.
    """

    q = " ".join((text or "").lower().strip().split())
    if not q:
        return KnowledgeRoute.VOICE_BRAIN

    if any(re.search(p, q) for p in _TOOL_PATTERNS):
        return KnowledgeRoute.INTERNET_TOOL

    if any(re.search(p, q) for p in _EXPLANATION_PATTERNS):
        return KnowledgeRoute.TEXT_BRAIN

    if explicitly_factual:
        return KnowledgeRoute.TEXT_BRAIN

    if any(re.search(p, q) for p in _CONVERSATIONAL_PATTERNS):
        return KnowledgeRoute.VOICE_BRAIN

    # Short social/persona utterances stay local; interrogative content defaults
    # to the stronger brain rather than hallucinating through the fast model.
    if q.endswith("?") or q.startswith(("qui ", "que ", "quel ", "quelle ", "combien ", "où ", "quand ")):
        return KnowledgeRoute.TEXT_BRAIN

    return KnowledgeRoute.VOICE_BRAIN


@dataclass(frozen=True)
class VoicePromptBudget:
    max_chars: int = 1800
    max_recent_messages: int = 4
    max_memory_chars: int = 520
    max_identity_chars: int = 500


def _clean(value: str) -> str:
    return " ".join((value or "").split())


def _clip(value: str, limit: int) -> str:
    value = _clean(value)
    if len(value) <= limit:
        return value
    cut = value[: max(0, limit - 1)].rstrip()
    return cut + "…"


def build_voice_micro_prompt(
    *,
    identity: str,
    user_text: str,
    recent_messages: Sequence[Mapping[str, str]] = (),
    relevant_memory: str = "",
    language: str = "fr",
    budget: VoicePromptBudget | None = None,
) -> str:
    """Build a compact prompt intended for llama3.2:3b voice-fast.

    This deliberately excludes long capability manifests, verbose memory dumps,
    diagnostics and tool documentation. Those belong to the text brain.
    """

    b = budget or VoicePromptBudget()
    parts: list[str] = [
        f"AURA voice-fast v{VERSION}.",
        "Réponds naturellement, brièvement et complètement.",
        "N'invente jamais un fait incertain; demande le cerveau texte/outils si nécessaire.",
        f"Langue: {language}.",
        "Identité: " + _clip(identity, b.max_identity_chars),
    ]

    memory = _clip(relevant_memory, b.max_memory_chars)
    if memory:
        parts.append("Mémoire utile: " + memory)

    recent = list(recent_messages)[-b.max_recent_messages :]
    for msg in recent:
        role = _clean(str(msg.get("role", "")))[:12] or "context"
        content = _clip(str(msg.get("content", "")), 260)
        if content:
            parts.append(f"{role}: {content}")

    parts.append("user: " + _clip(user_text, 420))
    prompt = "\n".join(parts)
    return _clip(prompt, b.max_chars)


_TERMINAL_RE = re.compile(r"(?<=[.!?…])\s+")
_CLAUSE_RE = re.compile(r"(?<=[,;:])\s+")


def chunk_for_xtts_clauses(
    text: str,
    *,
    first_limit: int = 92,
    next_limit: int = 145,
    min_clause_chars: int = 28,
) -> list[str]:
    """Split speech earlier than sentence-only chunking.

    Prefers sentence boundaries, then safe clause boundaries. It intentionally
    keeps punctuation in the logical chunk; the 0.7.0.14.1 speech guard should
    strip only terminal punctuation from the exact XTTS render payload.
    """

    text = _clean(text)
    if not text:
        return []

    # Tokenize into punctuation-aware units while retaining punctuation.
    units: list[str] = []
    start = 0
    for m in re.finditer(r"[.!?…]+|[,;:]", text):
        end = m.end()
        unit = text[start:end].strip()
        if unit:
            units.append(unit)
        start = end
    tail = text[start:].strip()
    if tail:
        units.append(tail)

    if not units:
        return [text]

    out: list[str] = []
    current = ""
    limit = first_limit
    for unit in units:
        candidate = f"{current} {unit}".strip() if current else unit
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            out.append(current)
            limit = next_limit
            current = unit
        else:
            # Fallback for a single very long unit: split on words.
            words = unit.split()
            buf = ""
            for word in words:
                cand = f"{buf} {word}".strip() if buf else word
                if len(cand) > limit and buf:
                    out.append(buf)
                    limit = next_limit
                    buf = word
                else:
                    buf = cand
            current = buf

    if current:
        # Avoid an excessively tiny tail where possible.
        previous_is_terminal = bool(out and re.search(r"[.!?…]$", out[-1]))
        if (
            out
            and not previous_is_terminal
            and len(current) < min_clause_chars
            and len(out[-1]) + 1 + len(current) <= next_limit
        ):
            out[-1] = f"{out[-1]} {current}"
        else:
            out.append(current)
    return out


__all__ = [
    "VERSION",
    "MemoryAction",
    "MemoryBands",
    "MemoryDecision",
    "MemoryPressureStateMachine",
    "PrewarmCancelled",
    "PrewarmCancellationToken",
    "KnowledgeRoute",
    "route_voice_query",
    "VoicePromptBudget",
    "build_voice_micro_prompt",
    "chunk_for_xtts_clauses",
]
