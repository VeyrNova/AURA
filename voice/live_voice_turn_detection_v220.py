
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from voice.live_voice_session_v220 import LiveVoiceSession, VoiceState


class TurnEndPhase(str, Enum):
    IDLE = "IDLE"
    SPEAKING = "SPEAKING"
    PENDING_SILENCE = "PENDING_SILENCE"
    COMMIT_READY = "COMMIT_READY"
    COMMITTED = "COMMITTED"


@dataclass(frozen=True)
class TurnEndConfig:
    min_speech_ms: int = 120
    silence_timeout_ms: int = 420

    def __post_init__(self) -> None:
        if int(self.min_speech_ms) < 1:
            raise ValueError("min_speech_ms must be >= 1")
        if int(self.silence_timeout_ms) < 1:
            raise ValueError("silence_timeout_ms must be >= 1")
        if int(self.silence_timeout_ms) > 500:
            raise ValueError(
                "silence_timeout_ms exceeds the v2.2 algorithmic target of 500 ms"
            )


@dataclass(frozen=True)
class TurnEndDecision:
    action: str
    reason: str
    turn_id: Optional[str]
    at_ms: int
    voiced_ms: int
    silence_ms: int
    false_end_recoveries: int


@dataclass(frozen=True)
class TurnEndEvidence:
    sequence: int
    event: str
    turn_id: Optional[str]
    at_ms: int
    phase: str
    detail: str = ""


class DeterministicTurnEndDetector:
    """Provider-neutral turn-end recommendation engine.

    All time values are supplied by the caller. The detector never sleeps,
    opens audio devices, samples microphones, calls a provider or owns the
    authoritative LiveVoiceSession state.
    """

    def __init__(self, *, config: Optional[TurnEndConfig] = None) -> None:
        self.config = config or TurnEndConfig()
        self.phase = TurnEndPhase.IDLE
        self.turn_id: Optional[str] = None

        self._last_at_ms: Optional[int] = None
        self._segment_started_ms: Optional[int] = None
        self._pending_since_ms: Optional[int] = None
        self._voiced_ms = 0
        self._false_end_recoveries = 0

        self._evidence: list[TurnEndEvidence] = []
        self._sequence = 0

    @property
    def evidence(self) -> tuple[TurnEndEvidence, ...]:
        return tuple(self._evidence)

    @property
    def voiced_ms(self) -> int:
        return int(self._voiced_ms)

    @property
    def false_end_recoveries(self) -> int:
        return int(self._false_end_recoveries)

    def _check_time(self, at_ms: int) -> int:
        at_ms = int(at_ms)
        if at_ms < 0:
            raise ValueError("at_ms must be >= 0")
        if self._last_at_ms is not None and at_ms < self._last_at_ms:
            raise ValueError(
                f"non-monotonic synthetic time: {at_ms} < {self._last_at_ms}"
            )
        self._last_at_ms = at_ms
        return at_ms

    def _require_turn(self, turn_id: str) -> None:
        if self.turn_id is None:
            raise RuntimeError("no active detector turn")
        if str(turn_id) != self.turn_id:
            raise RuntimeError(
                f"stale detector turn {turn_id}; active={self.turn_id}"
            )

    def _emit(
        self,
        event: str,
        *,
        at_ms: int,
        detail: str = "",
    ) -> None:
        self._sequence += 1
        self._evidence.append(
            TurnEndEvidence(
                sequence=self._sequence,
                event=str(event),
                turn_id=self.turn_id,
                at_ms=int(at_ms),
                phase=self.phase.value,
                detail=str(detail),
            )
        )

    def begin(self, turn_id: str, *, at_ms: int) -> None:
        at_ms = self._check_time(at_ms)
        if self.phase not in {TurnEndPhase.IDLE, TurnEndPhase.COMMITTED}:
            raise RuntimeError(f"detector already active in {self.phase.value}")
        self.turn_id = str(turn_id)
        self.phase = TurnEndPhase.SPEAKING
        self._segment_started_ms = at_ms
        self._pending_since_ms = None
        self._voiced_ms = 0
        self._false_end_recoveries = 0
        self._emit("speech_started", at_ms=at_ms)

    def speech_activity(self, turn_id: str, *, at_ms: int) -> TurnEndDecision:
        at_ms = self._check_time(at_ms)
        self._require_turn(turn_id)

        if self.phase is TurnEndPhase.PENDING_SILENCE:
            self._false_end_recoveries += 1
            self.phase = TurnEndPhase.SPEAKING
            self._pending_since_ms = None
            self._segment_started_ms = at_ms
            self._emit(
                "false_end_recovered",
                at_ms=at_ms,
                detail="speech resumed before silence threshold",
            )
        elif self.phase is not TurnEndPhase.SPEAKING:
            return self._decision(
                "REJECT",
                "activity_not_allowed_in_phase",
                at_ms,
            )

        self._emit("speech_activity", at_ms=at_ms)
        return self._decision("HOLD", "speech_active", at_ms)

    def speech_stopped(self, turn_id: str, *, at_ms: int) -> TurnEndDecision:
        at_ms = self._check_time(at_ms)
        self._require_turn(turn_id)

        if self.phase is not TurnEndPhase.SPEAKING:
            return self._decision(
                "REJECT",
                "speech_stop_not_allowed_in_phase",
                at_ms,
            )

        if self._segment_started_ms is None:
            raise RuntimeError("missing speech segment start")

        segment_ms = max(0, at_ms - self._segment_started_ms)
        self._voiced_ms += segment_ms
        self._segment_started_ms = None
        self._pending_since_ms = at_ms
        self.phase = TurnEndPhase.PENDING_SILENCE
        self._emit(
            "speech_ended_candidate",
            at_ms=at_ms,
            detail=f"segment_ms={segment_ms}",
        )

        if self._voiced_ms < self.config.min_speech_ms:
            return self._decision(
                "HOLD",
                "minimum_speech_guard",
                at_ms,
            )
        return self._decision(
            "HOLD",
            "waiting_for_silence_threshold",
            at_ms,
        )

    def evaluate(self, turn_id: str, *, at_ms: int) -> TurnEndDecision:
        at_ms = self._check_time(at_ms)
        self._require_turn(turn_id)

        if self.phase is TurnEndPhase.COMMIT_READY:
            return self._decision("COMMIT", "turn_end_ready", at_ms)

        if self.phase is not TurnEndPhase.PENDING_SILENCE:
            return self._decision(
                "HOLD",
                "no_pending_turn_end",
                at_ms,
            )

        assert self._pending_since_ms is not None
        silence_ms = max(0, at_ms - self._pending_since_ms)

        if self._voiced_ms < self.config.min_speech_ms:
            return self._decision(
                "HOLD",
                "minimum_speech_guard",
                at_ms,
                silence_ms=silence_ms,
            )

        if silence_ms < self.config.silence_timeout_ms:
            return self._decision(
                "HOLD",
                "silence_threshold_not_reached",
                at_ms,
                silence_ms=silence_ms,
            )

        self.phase = TurnEndPhase.COMMIT_READY
        self._emit(
            "turn_end_ready",
            at_ms=at_ms,
            detail=f"silence_ms={silence_ms}",
        )
        return self._decision(
            "COMMIT",
            "turn_end_ready",
            at_ms,
            silence_ms=silence_ms,
        )

    def mark_committed(self, turn_id: str, *, at_ms: int) -> None:
        at_ms = self._check_time(at_ms)
        self._require_turn(turn_id)
        if self.phase is not TurnEndPhase.COMMIT_READY:
            raise RuntimeError("turn end is not ready to commit")
        self.phase = TurnEndPhase.COMMITTED
        self._emit("speech_ended", at_ms=at_ms)

    def reset(self) -> None:
        self.phase = TurnEndPhase.IDLE
        self.turn_id = None
        self._last_at_ms = None
        self._segment_started_ms = None
        self._pending_since_ms = None
        self._voiced_ms = 0
        self._false_end_recoveries = 0

    def _decision(
        self,
        action: str,
        reason: str,
        at_ms: int,
        *,
        silence_ms: Optional[int] = None,
    ) -> TurnEndDecision:
        if silence_ms is None:
            if self._pending_since_ms is None:
                silence_ms = 0
            else:
                silence_ms = max(0, int(at_ms) - self._pending_since_ms)
        return TurnEndDecision(
            action=str(action),
            reason=str(reason),
            turn_id=self.turn_id,
            at_ms=int(at_ms),
            voiced_ms=int(self._voiced_ms),
            silence_ms=int(silence_ms),
            false_end_recoveries=int(self._false_end_recoveries),
        )


FinalTurnCommit = Callable[[str, str], bool]


class LiveVoiceTurnEndGate:
    """Subordinate detector/gate for synthetic VAD evidence.

    The detector only recommends a turn end. The final transcript is committed
    through the supplied canonical finalizer, which must ultimately pass through
    LiveVoiceSession. This gate never writes session state directly.
    """

    def __init__(
        self,
        *,
        session: LiveVoiceSession,
        final_turn_commit: FinalTurnCommit,
        config: Optional[TurnEndConfig] = None,
    ) -> None:
        if not isinstance(session, LiveVoiceSession):
            raise TypeError("session must be LiveVoiceSession")
        if not callable(final_turn_commit):
            raise TypeError("final_turn_commit must be callable")
        self.session = session
        self.detector = DeterministicTurnEndDetector(config=config)
        self._final_turn_commit = final_turn_commit

    def begin_user_turn(self, *, at_ms: int) -> str:
        if self.session.state is not VoiceState.LISTENING:
            raise RuntimeError("session must be LISTENING")
        turn_id = self.session.speech_started()
        self.detector.begin(turn_id, at_ms=at_ms)
        return turn_id

    def speech_activity(self, turn_id: str, *, at_ms: int) -> TurnEndDecision:
        return self.detector.speech_activity(turn_id, at_ms=at_ms)

    def speech_stopped(self, turn_id: str, *, at_ms: int) -> TurnEndDecision:
        return self.detector.speech_stopped(turn_id, at_ms=at_ms)

    def poll(self, turn_id: str, *, at_ms: int) -> TurnEndDecision:
        return self.detector.evaluate(turn_id, at_ms=at_ms)

    def commit_if_ready(
        self,
        turn_id: str,
        *,
        final_text: str,
        at_ms: int,
    ) -> TurnEndDecision:
        decision = self.detector.evaluate(turn_id, at_ms=at_ms)
        if decision.action != "COMMIT":
            return decision

        active = self.session.active_turn
        if (
            active is None
            or active.turn_id != turn_id
            or self.session.state is not VoiceState.TRANSCRIBING
        ):
            return TurnEndDecision(
                action="REJECT",
                reason="session_rejected_turn_end",
                turn_id=turn_id,
                at_ms=int(at_ms),
                voiced_ms=decision.voiced_ms,
                silence_ms=decision.silence_ms,
                false_end_recoveries=decision.false_end_recoveries,
            )

        accepted = bool(self._final_turn_commit(turn_id, str(final_text)))
        if not accepted:
            return TurnEndDecision(
                action="REJECT",
                reason="canonical_finalizer_rejected",
                turn_id=turn_id,
                at_ms=int(at_ms),
                voiced_ms=decision.voiced_ms,
                silence_ms=decision.silence_ms,
                false_end_recoveries=decision.false_end_recoveries,
            )

        self.detector.mark_committed(turn_id, at_ms=at_ms)
        return TurnEndDecision(
            action="COMMIT",
            reason="canonical_turn_committed",
            turn_id=turn_id,
            at_ms=int(at_ms),
            voiced_ms=decision.voiced_ms,
            silence_ms=decision.silence_ms,
            false_end_recoveries=decision.false_end_recoveries,
        )
