"""
AURA v2.2 - compatibility bridge between the optional AutoMic runtime and
the existing production UI/VoiceEngine speaking lifecycle.

R18-R4-R15-R2-R2 legacy live-app compatibility bindings

Permanent constraints:
- No second LiveVoiceSession is created.
- Existing application speaking state remains authoritative.
- Existing VoiceEngine.stop_speaking() path remains cancellation authority.
- This adapter owns no STT, TTS, memory, UI or durable state.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable


@dataclass(frozen=True)
class LegacyBindingDecision:
    accepted: bool
    reason: str
    turn_id: str | None = None


@dataclass(frozen=True)
class LegacyVoiceState:
    value: str


class LegacyLiveSessionProxy:
    """Minimal session surface consumed by LiveVoiceAutomaticBargeBridge."""

    def __init__(self, state_reader: Callable[[], str]):
        if not callable(state_reader):
            raise TypeError("state_reader must be callable")
        self._state_reader = state_reader

    @property
    def state(self) -> LegacyVoiceState:
        try:
            value = str(self._state_reader() or "IDLE").strip().upper()
        except Exception:
            value = "IDLE"
        if value != "SPEAKING":
            value = "IDLE"
        return LegacyVoiceState(value=value)


class LegacyLiveVoiceBindings:
    """Compatibility surface consumed by LiveVoiceAutomaticBargeBridge."""

    def __init__(
        self,
        *,
        state_reader: Callable[[], str],
        stop_speaking: Callable[[], object],
    ):
        if not callable(stop_speaking):
            raise TypeError("stop_speaking must be callable")
        self.session = LegacyLiveSessionProxy(state_reader)
        self._stop_speaking = stop_speaking
        self._lock = RLock()
        self._sequence = 0

    def request_barge_in(self, *, reason: str = "user_speech") -> LegacyBindingDecision:
        if self.session.state.value != "SPEAKING":
            return LegacyBindingDecision(False, "session_not_speaking", None)

        try:
            self._stop_speaking()
        except Exception:
            return LegacyBindingDecision(False, "legacy_stop_failed", None)

        with self._lock:
            self._sequence += 1
            turn_id = f"legacy-live-{self._sequence}"

        return LegacyBindingDecision(True, "barge_in_accepted", turn_id)
