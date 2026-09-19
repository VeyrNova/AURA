from __future__ import annotations

"""
AURA v2.2 - subordinate automatic barge-in bridge.

Product contract:
- Push-to-Talk remains permanently available.
- Automatic VAD/barge-in is an optional companion.
- This bridge owns no session state, no STT, no TTS and no microphone.
- It only translates one optional microphone-ingress speech-start event into
  the already-certified LiveVoiceProviderBindings.request_barge_in() surface.
"""

from dataclasses import dataclass
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class AutomaticBargeDecision:
    handled: bool
    reason: str
    sequence: int | None = None
    interrupted_turn_id: str | None = None


class LiveVoiceAutomaticBargeBridge:
    """Thin subordinate bridge into canonical provider bindings."""

    def __init__(self, *, bindings: Any, enabled: bool = False) -> None:
        if not callable(getattr(bindings, "request_barge_in", None)):
            raise TypeError("bindings must expose request_barge_in(reason=...)")
        if not hasattr(bindings, "session"):
            raise TypeError("bindings must expose its canonical session")
        self._bindings = bindings
        self._enabled = bool(enabled)
        self._lock = RLock()
        self._last_sequence: int | None = None

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def enable(self) -> None:
        with self._lock:
            self._enabled = True

    def disable(self) -> None:
        with self._lock:
            self._enabled = False

    @staticmethod
    def _state_name(session: Any) -> str:
        state = getattr(session, "state", None)
        value = getattr(state, "value", None)
        return str(value if value is not None else state).upper()

    def on_speech_started(self, event: Any) -> AutomaticBargeDecision:
        sequence_raw = getattr(event, "sequence", None)
        sequence = None if sequence_raw is None else int(sequence_raw)

        with self._lock:
            if not self._enabled:
                return AutomaticBargeDecision(
                    False,
                    "automatic_barge_disabled",
                    sequence,
                )

            if sequence is not None and sequence == self._last_sequence:
                return AutomaticBargeDecision(
                    False,
                    "duplicate_speech_start",
                    sequence,
                )

            self._last_sequence = sequence

        session = self._bindings.session
        if self._state_name(session) != "SPEAKING":
            return AutomaticBargeDecision(
                False,
                "session_not_speaking",
                sequence,
            )

        interrupted = self._bindings.request_barge_in(
            reason="user_speech"
        )

        turn_id = getattr(interrupted, "turn_id", None)
        if turn_id is None and isinstance(interrupted, str):
            turn_id = interrupted

        return AutomaticBargeDecision(
            True,
            "user_speech",
            sequence,
            None if turn_id is None else str(turn_id),
        )
