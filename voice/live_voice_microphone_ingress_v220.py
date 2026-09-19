from __future__ import annotations

"""
AURA v2.2 - subordinate optional live microphone ingress.

Product contract:
- Push-to-Talk remains a permanent AURA capability.
- This component is an OPTIONAL hands-free/VAD companion.
- It owns NO LiveVoiceSession, NO STT authority, NO TTS authority and NO durable state.
- It never imports sounddevice and never opens a physical audio device.
- Physical capture wiring is deliberately deferred to a later gate.
- It emits only speech-start, audio-chunk and speech-end callbacks.
"""

from collections import deque
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Deque, Optional

SpeechStartedCallback = Callable[["SpeechStartEvent"], Any]
AudioChunkCallback = Callable[["AudioChunkEvent"], Any]
SpeechEndedCallback = Callable[["SpeechEndEvent"], Any]


@dataclass(frozen=True)
class SpeechStartEvent:
    sequence: int
    at_ms: float
    probability: float


@dataclass(frozen=True)
class AudioChunkEvent:
    sequence: int
    at_ms: float
    probability: float
    audio: Any


@dataclass(frozen=True)
class SpeechEndEvent:
    sequence: int
    at_ms: float
    probability: float


class LiveVoiceMicrophoneIngress:
    """Callback-only subordinate optional microphone ingress."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        queue_capacity: int = 32,
        speech_start_threshold: float = 0.70,
        speech_end_threshold: float = 0.35,
        on_speech_started: Optional[SpeechStartedCallback] = None,
        on_audio_chunk: Optional[AudioChunkCallback] = None,
        on_speech_ended: Optional[SpeechEndedCallback] = None,
    ) -> None:
        capacity = int(queue_capacity)
        if capacity < 1:
            raise ValueError("queue_capacity must be >= 1")

        start_threshold = float(speech_start_threshold)
        end_threshold = float(speech_end_threshold)

        if not (0.0 <= end_threshold < start_threshold <= 1.0):
            raise ValueError(
                "thresholds require 0 <= speech_end_threshold "
                "< speech_start_threshold <= 1"
            )

        self._lock = RLock()
        self._enabled = bool(enabled)
        self._speech_active = False
        self._sequence = 0
        self._queue_capacity = capacity
        self._queue: Deque[AudioChunkEvent] = deque(maxlen=capacity)
        self._speech_start_threshold = start_threshold
        self._speech_end_threshold = end_threshold
        self._on_speech_started = on_speech_started
        self._on_audio_chunk = on_audio_chunk
        self._on_speech_ended = on_speech_ended

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @property
    def speech_active(self) -> bool:
        with self._lock:
            return self._speech_active

    @property
    def queue_capacity(self) -> int:
        return self._queue_capacity

    @property
    def queued_chunks(self) -> int:
        with self._lock:
            return len(self._queue)

    def enable(self) -> None:
        with self._lock:
            self._enabled = True

    def disable(self, *, clear_queue: bool = True) -> None:
        with self._lock:
            self._enabled = False
            self._speech_active = False
            if clear_queue:
                self._queue.clear()

    def reset(self) -> None:
        with self._lock:
            self._speech_active = False
            self._queue.clear()

    def snapshot_chunks(self) -> tuple[AudioChunkEvent, ...]:
        with self._lock:
            return tuple(self._queue)

    def push_audio(
        self,
        audio: Any,
        *,
        speech_probability: float,
        at_ms: float,
    ) -> bool:
        probability = float(speech_probability)
        timestamp = float(at_ms)

        if not (0.0 <= probability <= 1.0):
            raise ValueError("speech_probability must be between 0 and 1")

        start_event = None
        chunk_event = None
        end_event = None

        with self._lock:
            if not self._enabled:
                return False

            self._sequence += 1
            sequence = self._sequence

            if (
                not self._speech_active
                and probability >= self._speech_start_threshold
            ):
                self._speech_active = True
                start_event = SpeechStartEvent(
                    sequence=sequence,
                    at_ms=timestamp,
                    probability=probability,
                )

            chunk_event = AudioChunkEvent(
                sequence=sequence,
                at_ms=timestamp,
                probability=probability,
                audio=audio,
            )
            self._queue.append(chunk_event)

            if (
                self._speech_active
                and probability <= self._speech_end_threshold
            ):
                self._speech_active = False
                end_event = SpeechEndEvent(
                    sequence=sequence,
                    at_ms=timestamp,
                    probability=probability,
                )

        if start_event is not None and callable(self._on_speech_started):
            self._on_speech_started(start_event)

        if callable(self._on_audio_chunk):
            self._on_audio_chunk(chunk_event)

        if end_event is not None and callable(self._on_speech_ended):
            self._on_speech_ended(end_event)

        return True
