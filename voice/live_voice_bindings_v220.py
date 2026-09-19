
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from voice.live_voice_session_v220 import (
    InvalidVoiceTransition,
    LiveVoiceSession,
    LiveVoiceError,
    StaleVoiceTurn,
)


@runtime_checkable
class SpeechToTextProvider(Protocol):
    """Provider-neutral STT callback surface.

    Implementations may be local or remote in later gates. R4 binds only the
    callback contract; it does not select, open or own any real audio device.
    """

    provider_id: str

    def start_turn(
        self,
        *,
        session_id: str,
        turn_id: str,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        ...

    def cancel(self, *, turn_id: str, reason: str) -> None:
        ...


@runtime_checkable
class TextToSpeechProvider(Protocol):
    """Provider-neutral TTS/playback callback surface."""

    provider_id: str

    def speak(
        self,
        *,
        session_id: str,
        turn_id: str,
        text: str,
        on_first_chunk: Callable[[], None],
        on_playback_started: Callable[[], None],
        on_completed: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        ...

    def cancel(self, *, turn_id: str, reason: str) -> None:
        ...


CanonicalTextIngress = Callable[
    [str, str, str, Any],
    str,
]


@dataclass(frozen=True)
class BindingDecision:
    accepted: bool
    reason: str
    turn_id: Optional[str] = None


class LiveVoiceProviderBindings:
    """Provider-neutral bridge into the single LiveVoiceSession authority.

    This class deliberately owns NO session state, NO turn counter, NO
    cancellation truth and NO provider lifecycle authority. All authoritative
    voice state remains in LiveVoiceSession.

    R4 is synchronous/deterministic by design. Later streaming gates may supply
    async providers behind the same callback contract without creating a
    competing state machine.
    """

    def __init__(
        self,
        *,
        session: LiveVoiceSession,
        stt: SpeechToTextProvider,
        tts: TextToSpeechProvider,
        canonical_text_ingress: CanonicalTextIngress,
    ) -> None:
        if not isinstance(session, LiveVoiceSession):
            raise TypeError("session must be LiveVoiceSession")
        if not callable(canonical_text_ingress):
            raise TypeError("canonical_text_ingress must be callable")
        self.session = session
        self.stt = stt
        self.tts = tts
        self._canonical_text_ingress = canonical_text_ingress

    def begin_user_turn(self) -> str:
        turn_id = self.session.speech_started()

        self.stt.start_turn(
            session_id=self.session.session_id,
            turn_id=turn_id,
            on_partial=lambda text: self.on_stt_partial(turn_id, text),
            on_final=lambda text: self.on_stt_final(turn_id, text),
            on_error=lambda reason: self.on_stt_error(turn_id, reason),
        )
        return turn_id

    def on_stt_partial(self, turn_id: str, text: str) -> BindingDecision:
        try:
            self.session.stt_partial(text, turn_id=turn_id)
            return BindingDecision(True, "stt_partial_accepted", turn_id)
        except (StaleVoiceTurn, InvalidVoiceTransition):
            return BindingDecision(False, "stale_or_invalid_stt_partial", turn_id)

    def on_stt_final(self, turn_id: str, text: str) -> BindingDecision:
        try:
            final_text = self.session.stt_final(text, turn_id=turn_id)
            committed_text = self.session.commit_turn(turn_id=turn_id)
            turn = self.session.active_turn
            if turn is None or turn.turn_id != turn_id:
                return BindingDecision(False, "turn_missing_after_commit", turn_id)

            response_text = self._canonical_text_ingress(
                committed_text,
                self.session.session_id,
                turn_id,
                turn.cancellation,
            )
            if turn.cancellation.cancelled:
                return BindingDecision(False, "turn_cancelled_during_ingress", turn_id)

            response_text = str(response_text or "").strip()
            if not response_text:
                self.session.recover(
                    reason="empty_canonical_response",
                    resume_listening=True,
                )
                return BindingDecision(False, "empty_canonical_response", turn_id)

            self.session.llm_first_token(turn_id=turn_id)
            self.session.begin_speaking(turn_id=turn_id)

            self.tts.speak(
                session_id=self.session.session_id,
                turn_id=turn_id,
                text=response_text,
                on_first_chunk=lambda: self.on_tts_first_chunk(turn_id),
                on_playback_started=lambda: self.on_playback_started(turn_id),
                on_completed=lambda: self.on_tts_completed(turn_id),
                on_error=lambda reason: self.on_tts_error(turn_id, reason),
            )
            return BindingDecision(True, "turn_committed_to_canonical_ingress", turn_id)

        except (StaleVoiceTurn, InvalidVoiceTransition):
            return BindingDecision(False, "stale_or_duplicate_stt_final", turn_id)
        except Exception as exc:
            try:
                self.session.recover(
                    reason=f"canonical_ingress_error:{type(exc).__name__}",
                    resume_listening=True,
                )
            except Exception:
                pass
            return BindingDecision(False, "canonical_ingress_error", turn_id)

    def on_stt_error(self, turn_id: str, reason: str) -> BindingDecision:
        active = self.session.active_turn
        if active is None or active.turn_id != turn_id:
            return BindingDecision(False, "stale_stt_error", turn_id)
        try:
            self.stt.cancel(turn_id=turn_id, reason=str(reason))
        except Exception:
            pass
        try:
            self.session.recover(
                reason=f"stt_provider_error:{reason}",
                resume_listening=True,
            )
            return BindingDecision(True, "stt_error_recovered", turn_id)
        except (StaleVoiceTurn, InvalidVoiceTransition, LiveVoiceError):
            return BindingDecision(False, "stt_error_recovery_rejected", turn_id)

    def on_tts_first_chunk(self, turn_id: str) -> BindingDecision:
        try:
            self.session.tts_first_chunk(turn_id=turn_id)
            return BindingDecision(True, "tts_first_chunk_accepted", turn_id)
        except (StaleVoiceTurn, InvalidVoiceTransition):
            return BindingDecision(False, "stale_tts_first_chunk", turn_id)

    def on_playback_started(self, turn_id: str) -> BindingDecision:
        try:
            self.session.playback_started(turn_id=turn_id)
            return BindingDecision(True, "playback_started_accepted", turn_id)
        except (StaleVoiceTurn, InvalidVoiceTransition):
            return BindingDecision(False, "stale_playback_started", turn_id)

    def on_tts_completed(self, turn_id: str) -> BindingDecision:
        try:
            self.session.response_completed(turn_id=turn_id)
            return BindingDecision(True, "tts_completed_accepted", turn_id)
        except (StaleVoiceTurn, InvalidVoiceTransition):
            return BindingDecision(False, "stale_tts_completed", turn_id)

    def on_tts_error(self, turn_id: str, reason: str) -> BindingDecision:
        active = self.session.active_turn
        if active is None or active.turn_id != turn_id:
            return BindingDecision(False, "stale_tts_error", turn_id)
        try:
            self.tts.cancel(turn_id=turn_id, reason=str(reason))
        except Exception:
            pass
        try:
            self.session.recover(
                reason=f"tts_provider_error:{reason}",
                resume_listening=True,
            )
            return BindingDecision(True, "tts_error_recovered", turn_id)
        except (StaleVoiceTurn, InvalidVoiceTransition, LiveVoiceError):
            return BindingDecision(False, "tts_error_recovery_rejected", turn_id)

    def request_barge_in(self, *, reason: str = "user_speech") -> BindingDecision:
        active = self.session.active_turn
        if active is None:
            return BindingDecision(False, "no_active_turn_for_barge_in", None)

        turn_id = active.turn_id
        try:
            interrupted = self.session.request_barge_in(reason=reason)
        except (StaleVoiceTurn, InvalidVoiceTransition):
            return BindingDecision(False, "barge_in_rejected", turn_id)

        # Provider cancellation is subordinate to session authority: session state
        # is already interrupted before cancellation is sent to the provider.
        try:
            self.tts.cancel(turn_id=interrupted, reason=reason)
        except Exception:
            # Provider cancellation failures must not resurrect the cancelled turn.
            pass

        return BindingDecision(True, "barge_in_accepted", interrupted)

    def stop(self, *, reason: str = "session_stop") -> None:
        active = self.session.active_turn
        if active is not None:
            turn_id = active.turn_id
            try:
                self.stt.cancel(turn_id=turn_id, reason=reason)
            except Exception:
                pass
            try:
                self.tts.cancel(turn_id=turn_id, reason=reason)
            except Exception:
                pass
        self.session.stop(reason=reason)
