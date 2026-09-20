
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import monotonic_ns
from typing import Any, Callable, Optional
from uuid import uuid4


class VoiceState(str, Enum):
    STOPPED = "STOPPED"
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    INTERRUPTING = "INTERRUPTING"
    RECOVERING = "RECOVERING"
    ERROR = "ERROR"


LEGAL_TRANSITIONS: dict[VoiceState, frozenset[VoiceState]] = {
    VoiceState.STOPPED: frozenset({VoiceState.IDLE}),
    VoiceState.IDLE: frozenset({VoiceState.LISTENING, VoiceState.STOPPED}),
    VoiceState.LISTENING: frozenset({
        VoiceState.TRANSCRIBING,
        VoiceState.RECOVERING,
        VoiceState.STOPPED,
    }),
    VoiceState.TRANSCRIBING: frozenset({
        VoiceState.LISTENING,
        VoiceState.THINKING,
        VoiceState.RECOVERING,
        VoiceState.STOPPED,
    }),
    VoiceState.THINKING: frozenset({
        VoiceState.SPEAKING,
        VoiceState.RECOVERING,
        VoiceState.STOPPED,
    }),
    VoiceState.SPEAKING: frozenset({
        VoiceState.LISTENING,
        VoiceState.INTERRUPTING,
        VoiceState.RECOVERING,
        VoiceState.STOPPED,
    }),
    VoiceState.INTERRUPTING: frozenset({
        VoiceState.LISTENING,
        VoiceState.STOPPED,
    }),
    VoiceState.RECOVERING: frozenset({
        VoiceState.LISTENING,
        VoiceState.IDLE,
        VoiceState.STOPPED,
    }),
    VoiceState.ERROR: frozenset({VoiceState.STOPPED}),
}


class LiveVoiceError(RuntimeError):
    pass


class InvalidVoiceTransition(LiveVoiceError):
    pass


class StaleVoiceTurn(LiveVoiceError):
    pass


@dataclass
class CancellationToken:
    turn_id: str
    cancelled: bool = False
    reason: Optional[str] = None

    def cancel(self, reason: str) -> None:
        if not self.cancelled:
            self.cancelled = True
            self.reason = str(reason)


@dataclass(frozen=True)
class VoiceEvent:
    sequence: int
    event: str
    state: str
    monotonic_ns: int
    session_id: str
    turn_id: Optional[str] = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceTurn:
    turn_id: str
    cancellation: CancellationToken
    final_user_transcript: Optional[str] = None
    committed: bool = False
    response_started: bool = False
    playback_started: bool = False
    cancelled: bool = False


class LiveVoiceSession:
    """Deterministic v2.2 live-voice session authority.

    R3 intentionally owns *state only*. It opens no microphone, plays no audio,
    loads no model and performs no network or provider I/O.

    Provider adapters in later gates must call this authority rather than own
    competing session/turn state.
    """

    def __init__(
        self,
        *,
        session_id: Optional[str] = None,
        clock_ns: Optional[Callable[[], int]] = None,
        event_sink: Optional[Callable[[VoiceEvent], None]] = None,
        max_event_history: int = 512,
    ) -> None:
        if int(max_event_history) < 32:
            raise ValueError("max_event_history must be >= 32")

        self.session_id = session_id or f"voice-{uuid4().hex}"
        self.state = VoiceState.STOPPED
        self._clock_ns = clock_ns or monotonic_ns
        self._event_sink = event_sink
        self._max_event_history = int(max_event_history)
        self._events: list[VoiceEvent] = []
        self._sequence = 0
        self._turn_counter = 0
        self._active_turn: Optional[VoiceTurn] = None
        self._lock = RLock()

    @property
    def active_turn(self) -> Optional[VoiceTurn]:
        return self._active_turn

    @property
    def events(self) -> tuple[VoiceEvent, ...]:
        return tuple(self._events)

    @property
    def is_running(self) -> bool:
        return self.state is not VoiceState.STOPPED

    def _next_turn_id(self) -> str:
        self._turn_counter += 1
        return f"{self.session_id}:turn:{self._turn_counter}"

    def _emit(
        self,
        event: str,
        *,
        turn_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> VoiceEvent:
        self._sequence += 1
        item = VoiceEvent(
            sequence=self._sequence,
            event=str(event),
            state=self.state.value,
            monotonic_ns=int(self._clock_ns()),
            session_id=self.session_id,
            turn_id=turn_id,
            payload=dict(payload or {}),
        )
        self._events.append(item)
        if len(self._events) > self._max_event_history:
            del self._events[: len(self._events) - self._max_event_history]
        if self._event_sink is not None:
            self._event_sink(item)
        return item

    def _transition(
        self,
        target: VoiceState,
        *,
        turn_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        if target is self.state:
            return
        allowed = LEGAL_TRANSITIONS.get(self.state, frozenset())
        if target not in allowed:
            raise InvalidVoiceTransition(
                f"illegal voice transition {self.state.value} -> {target.value}"
            )
        previous = self.state
        self.state = target
        self._emit(
            "state_changed",
            turn_id=turn_id,
            payload={
                "from": previous.value,
                "to": target.value,
                "reason": reason,
            },
        )

    def _require_turn(self, turn_id: Optional[str] = None) -> VoiceTurn:
        turn = self._active_turn
        if turn is None:
            raise StaleVoiceTurn("no active voice turn")
        if turn_id is not None and turn.turn_id != turn_id:
            raise StaleVoiceTurn(
                f"stale turn {turn_id}; active turn is {turn.turn_id}"
            )
        return turn

    def start(self) -> None:
        with self._lock:
            if self.state is not VoiceState.STOPPED:
                return
            self._emit("session_started")
            self._transition(VoiceState.IDLE, reason="session_start")
            self._transition(VoiceState.LISTENING, reason="ready")

    def stop(self, *, reason: str = "session_stop") -> None:
        with self._lock:
            if self.state is VoiceState.STOPPED:
                return
            if self._active_turn is not None:
                self._active_turn.cancellation.cancel(reason)
                self._active_turn.cancelled = True
                self._emit(
                    "turn_cancelled",
                    turn_id=self._active_turn.turn_id,
                    payload={"reason": reason},
                )
                self._active_turn = None
            self._transition(VoiceState.STOPPED, reason=reason)
            self._emit("session_stopped", payload={"reason": reason})

    def speech_started(self) -> str:
        with self._lock:
            if self.state is VoiceState.SPEAKING:
                return self.request_barge_in(reason="user_speech")
            if self.state is not VoiceState.LISTENING:
                raise InvalidVoiceTransition(
                    f"speech_started requires LISTENING, got {self.state.value}"
                )
            if self._active_turn is not None:
                raise LiveVoiceError("cannot start a second active turn")
            turn_id = self._next_turn_id()
            turn = VoiceTurn(
                turn_id=turn_id,
                cancellation=CancellationToken(turn_id=turn_id),
            )
            self._active_turn = turn
            self._emit("speech_started", turn_id=turn_id)
            self._transition(
                VoiceState.TRANSCRIBING,
                turn_id=turn_id,
                reason="speech_started",
            )
            return turn_id

    def stt_partial(self, text: str, *, turn_id: Optional[str] = None) -> None:
        with self._lock:
            turn = self._require_turn(turn_id)
            if self.state is not VoiceState.TRANSCRIBING:
                raise InvalidVoiceTransition("stt_partial requires TRANSCRIBING")
            self._emit(
                "stt_partial",
                turn_id=turn.turn_id,
                payload={"text": str(text), "ephemeral": True},
            )

    def stt_final(self, text: str, *, turn_id: Optional[str] = None) -> str:
        with self._lock:
            turn = self._require_turn(turn_id)
            if self.state is not VoiceState.TRANSCRIBING:
                raise InvalidVoiceTransition("stt_final requires TRANSCRIBING")
            final_text = str(text).strip()
            if not final_text:
                raise ValueError("final transcript must not be empty")
            turn.final_user_transcript = final_text
            self._emit(
                "stt_final",
                turn_id=turn.turn_id,
                payload={"text": final_text},
            )
            return final_text

    def commit_turn(self, *, turn_id: Optional[str] = None) -> str:
        with self._lock:
            turn = self._require_turn(turn_id)
            if self.state is not VoiceState.TRANSCRIBING:
                raise InvalidVoiceTransition("commit_turn requires TRANSCRIBING")
            if not turn.final_user_transcript:
                raise LiveVoiceError("cannot commit a turn without final transcript")
            turn.committed = True
            self._emit(
                "turn_committed",
                turn_id=turn.turn_id,
                payload={
                    "text": turn.final_user_transcript,
                    "canonical_text_ingress_required": True,
                },
            )
            self._transition(
                VoiceState.THINKING,
                turn_id=turn.turn_id,
                reason="turn_committed",
            )
            return turn.final_user_transcript

    def llm_first_token(self, *, turn_id: Optional[str] = None) -> None:
        with self._lock:
            turn = self._require_turn(turn_id)
            if self.state is not VoiceState.THINKING:
                raise InvalidVoiceTransition("llm_first_token requires THINKING")
            self._emit("llm_first_token", turn_id=turn.turn_id)

    def begin_speaking(self, *, turn_id: Optional[str] = None) -> None:
        with self._lock:
            turn = self._require_turn(turn_id)
            if self.state is not VoiceState.THINKING:
                raise InvalidVoiceTransition("begin_speaking requires THINKING")
            if turn.cancellation.cancelled:
                raise StaleVoiceTurn("cancelled turn cannot begin speaking")
            turn.response_started = True
            self._transition(
                VoiceState.SPEAKING,
                turn_id=turn.turn_id,
                reason="response_ready",
            )

    def tts_first_chunk(self, *, turn_id: Optional[str] = None) -> None:
        with self._lock:
            turn = self._require_turn(turn_id)
            if self.state is not VoiceState.SPEAKING:
                raise InvalidVoiceTransition("tts_first_chunk requires SPEAKING")
            self._emit("tts_first_chunk", turn_id=turn.turn_id)

    def playback_started(self, *, turn_id: Optional[str] = None) -> None:
        with self._lock:
            turn = self._require_turn(turn_id)
            if self.state is not VoiceState.SPEAKING:
                raise InvalidVoiceTransition("playback_started requires SPEAKING")
            turn.playback_started = True
            self._emit("playback_started", turn_id=turn.turn_id)

    def response_completed(self, *, turn_id: Optional[str] = None) -> None:
        with self._lock:
            turn = self._require_turn(turn_id)
            if self.state is not VoiceState.SPEAKING:
                raise InvalidVoiceTransition("response_completed requires SPEAKING")
            completed_turn = turn.turn_id
            self._emit("response_completed", turn_id=completed_turn)
            self._active_turn = None
            self._transition(
                VoiceState.LISTENING,
                turn_id=completed_turn,
                reason="response_completed",
            )

    def request_barge_in(self, *, reason: str = "user_speech") -> str:
        with self._lock:
            turn = self._require_turn()
            if self.state is not VoiceState.SPEAKING:
                raise InvalidVoiceTransition("barge-in requires SPEAKING")
            self._emit(
                "barge_in_detected",
                turn_id=turn.turn_id,
                payload={"reason": reason},
            )
            turn.cancellation.cancel(reason)
            turn.cancelled = True
            self._transition(
                VoiceState.INTERRUPTING,
                turn_id=turn.turn_id,
                reason=reason,
            )
            self._emit(
                "playback_cancelled",
                turn_id=turn.turn_id,
                payload={"reason": reason},
            )
            self._emit(
                "turn_cancelled",
                turn_id=turn.turn_id,
                payload={"reason": reason},
            )
            interrupted = turn.turn_id
            self._active_turn = None
            self._transition(
                VoiceState.LISTENING,
                turn_id=interrupted,
                reason="barge_in_complete",
            )
            return interrupted

    def recover(
        self,
        *,
        reason: str,
        resume_listening: bool = True,
    ) -> None:
        with self._lock:
            if self.state in {VoiceState.STOPPED, VoiceState.ERROR}:
                raise InvalidVoiceTransition(
                    f"cannot recover from {self.state.value}"
                )
            turn_id = self._active_turn.turn_id if self._active_turn else None
            self._transition(
                VoiceState.RECOVERING,
                turn_id=turn_id,
                reason=reason,
            )
            self._emit(
                "recovery_started",
                turn_id=turn_id,
                payload={"reason": reason},
            )
            if self._active_turn is not None:
                self._active_turn.cancellation.cancel(reason)
                self._active_turn.cancelled = True
                self._emit(
                    "turn_cancelled",
                    turn_id=self._active_turn.turn_id,
                    payload={"reason": reason},
                )
                self._active_turn = None
            target = VoiceState.LISTENING if resume_listening else VoiceState.IDLE
            self._transition(target, reason="recovery_complete")
            self._emit(
                "recovery_completed",
                payload={"reason": reason, "target": target.value},
            )

    def fail(self, *, reason: str) -> None:
        with self._lock:
            if self._active_turn is not None:
                self._active_turn.cancellation.cancel(reason)
                self._active_turn.cancelled = True
                self._emit(
                    "turn_cancelled",
                    turn_id=self._active_turn.turn_id,
                    payload={"reason": reason},
                )
                self._active_turn = None

            if self.state is VoiceState.STOPPED:
                self._emit("voice_error", payload={"reason": reason})
                return

            # ERROR is deliberately fail-closed. If no direct contract edge exists,
            # stop the session instead of inventing an uncontracted transition.
            self._emit("voice_error", payload={"reason": reason})
            self._transition(VoiceState.STOPPED, reason="fatal_error")
