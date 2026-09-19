
from __future__ import annotations

from dataclasses import dataclass
from inspect import signature
from typing import Any, Callable


@dataclass(frozen=True)
class FirstAudioAdapterCapabilities:
    provider_name: str = "text_to_speech"
    role: str = "tts"
    public_first_audio_callback: bool = True
    maps_first_audio_to_playback_started: bool = True
    maps_first_audio_to_first_chunk: bool = False
    runtime_certified: bool = False
    real_audio_certified: bool = False


class InstrumentedTextToSpeechAdapter:
    provider_id = "text_to_speech:r11-first-audio"
    capabilities = FirstAudioAdapterCapabilities()

    def __init__(self, provider: Any) -> None:
        self._provider = provider
        self._validate_provider()

    def _validate_provider(self) -> None:
        speak = getattr(self._provider, "speak", None)
        stop = getattr(self._provider, "stop", None)
        if not callable(speak):
            raise TypeError("provider must expose speak(text, on_first_audio=None)")
        if not callable(stop):
            raise TypeError("provider must expose stop()")
        try:
            params = signature(speak).parameters
        except Exception as exc:
            raise TypeError("provider speak() signature is not inspectable") from exc
        if "on_first_audio" not in params:
            raise TypeError("provider speak() must expose optional on_first_audio callback")

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
        del session_id, turn_id, on_first_chunk
        spoken = str(text or "").strip()
        if not spoken:
            on_error("empty_tts_text")
            return

        fired = False

        def first_audio_once(*_provider_args, **_provider_kwargs) -> None:
            nonlocal fired
            if fired:
                return
            fired = True
            try:
                on_playback_started()
            except Exception:
                return

        try:
            self._provider.speak(spoken, on_first_audio=first_audio_once)
        except Exception as exc:
            on_error(f"speak_error:{type(exc).__name__}")
            return

        on_completed()

    def cancel(self, *, turn_id: str, reason: str) -> None:
        del turn_id, reason
        self._provider.stop()

    def warmup(self) -> bool:
        warm = getattr(self._provider, "warmup", None)
        if not callable(warm):
            return False
        warm()
        return True
