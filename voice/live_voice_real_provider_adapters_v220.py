
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class AdapterCapabilities:
    provider_name: str
    role: str
    supports_partial: bool
    supports_final: bool
    supports_cancel: bool
    supports_warmup: bool
    supports_precise_first_audio_callback: bool
    runtime_certified: bool = False
    live_audio_certified: bool = False


@dataclass
class _STTTurnCallbacks:
    on_partial: Callable[[str], Any]
    on_final: Callable[[str], Any]
    on_error: Callable[[str], Any]


class VoiceEngineSTTAdapter:
    """Thin adapter for the existing voice_engine STT facade.

    The wrapped provider object is injected. This module never imports,
    constructs, warms or calls the real provider by itself.

    R8 found no static streaming method on voice_engine, so this adapter is
    deliberately FINAL-TRANSCRIPT ONLY. It must not invent partial transcripts.
    """

    provider_id = "voice_engine"

    capabilities = AdapterCapabilities(
        provider_name="voice_engine",
        role="stt",
        supports_partial=False,
        supports_final=True,
        supports_cancel=True,
        supports_warmup=True,
        supports_precise_first_audio_callback=False,
    )

    def __init__(self, provider: Any) -> None:
        self._provider = provider
        self._turns: dict[str, _STTTurnCallbacks] = {}
        self._validate_provider()

    def _validate_provider(self) -> None:
        if not callable(getattr(self._provider, "transcribe", None)):
            raise TypeError("voice_engine provider must expose transcribe(audio)")
        if not (
            callable(getattr(self._provider, "cancel_listening", None))
            or callable(getattr(self._provider, "stop_listening", None))
        ):
            raise TypeError(
                "voice_engine provider must expose cancel_listening() "
                "or stop_listening()"
            )

    def start_turn(
        self,
        *,
        session_id: str,
        turn_id: str,
        on_partial: Callable[[str], Any],
        on_final: Callable[[str], Any],
        on_error: Callable[[str], Any],
    ) -> None:
        del session_id
        if turn_id in self._turns:
            raise RuntimeError(f"duplicate STT turn: {turn_id}")
        self._turns[turn_id] = _STTTurnCallbacks(
            on_partial=on_partial,
            on_final=on_final,
            on_error=on_error,
        )

    @staticmethod
    def _normalize_transcript(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in ("text", "transcript", "result"):
                candidate = value.get(key)
                if isinstance(candidate, str):
                    return candidate.strip()
        text = getattr(value, "text", None)
        if isinstance(text, str):
            return text.strip()
        return str(value).strip()

    def submit_audio(self, *, turn_id: str, audio: Any) -> bool:
        callbacks = self._turns.get(turn_id)
        if callbacks is None:
            return False

        try:
            raw = self._provider.transcribe(audio)
            text = self._normalize_transcript(raw)
            if not text:
                callbacks.on_error("empty_transcript")
                self._turns.pop(turn_id, None)
                return False
            callbacks.on_final(text)
            self._turns.pop(turn_id, None)
            return True
        except Exception as exc:
            callbacks.on_error(f"transcribe_error:{type(exc).__name__}")
            self._turns.pop(turn_id, None)
            return False

    def cancel(self, *, turn_id: str, reason: str) -> None:
        del reason
        self._turns.pop(turn_id, None)
        cancel = getattr(self._provider, "cancel_listening", None)
        if callable(cancel):
            cancel()
            return
        stop = getattr(self._provider, "stop_listening", None)
        if callable(stop):
            stop()

    def warmup(self) -> bool:
        warm = getattr(self._provider, "warmup", None)
        if not callable(warm):
            return False
        warm()
        return True


class TextToSpeechAdapter:
    """Thin adapter for the existing text_to_speech provider surface.

    RC9-R1 keeps the original direct-provider constructor backward compatible
    while allowing a provider_getter for dynamic provider freshness. This is
    required because VoiceEngine.reload_tts() may replace VoiceEngine.tts after
    the Live Voice shadow composition has already been constructed.
    """

    def __init__(
        self,
        provider: Any = None,
        *,
        provider_getter: Callable[[], Any] | None = None,
    ) -> None:
        if provider is not None and provider_getter is not None:
            raise TypeError("provide either provider or provider_getter, not both")
        if provider is None and provider_getter is None:
            raise TypeError("provider or provider_getter is required")
        self._provider = provider
        self._provider_getter = provider_getter
        self._validate_provider()

    def _current_provider(self) -> Any:
        provider = (
            self._provider_getter()
            if self._provider_getter is not None
            else self._provider
        )
        if provider is None:
            raise TypeError("text_to_speech provider is unavailable")
        return provider

    @staticmethod
    def _validate_provider_surface(provider: Any) -> None:
        if not callable(getattr(provider, "speak", None)):
            raise TypeError("text_to_speech provider must expose speak(text)")
        if not callable(getattr(provider, "stop", None)):
            raise TypeError("text_to_speech provider must expose stop()")

    def _validate_provider(self) -> None:
        self._validate_provider_surface(self._current_provider())

    def _validated_current_provider(self) -> Any:
        provider = self._current_provider()
        self._validate_provider_surface(provider)
        return provider

    def speak(
        self,
        *,
        session_id: str,
        turn_id: str,
        text: str,
        on_first_chunk: Callable[[], Any],
        on_playback_started: Callable[[], Any],
        on_completed: Callable[[], Any],
        on_error: Callable[[str], Any],
    ) -> None:
        del session_id, turn_id, on_first_chunk, on_playback_started

        spoken = str(text or "").strip()
        if not spoken:
            on_error("empty_tts_text")
            return

        try:
            provider = self._validated_current_provider()
            provider.speak(spoken)
        except Exception as exc:
            on_error(f"speak_error:{type(exc).__name__}")
            return

        on_completed()

    def cancel(self, *, turn_id: str, reason: str) -> None:
        del turn_id, reason
        self._validated_current_provider().stop()

    def warmup(self) -> bool:
        provider = self._validated_current_provider()
        warm = getattr(provider, "warmup", None)
        if not callable(warm):
            return False
        warm()
        return True
