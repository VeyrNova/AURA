from __future__ import annotations

# AURA v2.2 R18-R4-R22-R1 - subordinate continuous voice turn controller.
#
# This module owns only an ephemeral utterance PCM buffer and the injected
# deterministic turn-end detector. It owns NO conversation/session, STT, TTS,
# memory, provider, microphone-device, UI or durable authority.
#
# Production wiring is intentionally NOT part of R22-R1.

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable

import numpy as np


@dataclass(frozen=True)
class ContinuousTurnStatus:
    active: bool
    pending_silence: bool
    turn_id: str | None
    buffered_chunks: int
    finalized_turns: int
    cancelled_turns: int


class ContinuousVoiceTurnController:
    def __init__(
        self,
        *,
        detector: Any,
        is_ready: Callable[[Any], bool],
        on_finalized_audio: Callable[[Any], None] | None = None,
        source_sample_rate: int = 48000,
        target_sample_rate: int = 16000,
        audio_transform: Callable[[Any, int], Any] | None = None,
    ):
        if detector is None:
            raise TypeError("detector is required")
        if not callable(is_ready):
            raise TypeError("is_ready(decision) is required")
        self.detector = detector
        self._is_ready = is_ready
        self._on_finalized_audio = on_finalized_audio
        self.source_sample_rate = int(source_sample_rate)
        self.target_sample_rate = int(target_sample_rate)
        if self.source_sample_rate <= 0 or self.target_sample_rate <= 0:
            raise ValueError("sample rates must be positive")
        self.audio_transform = audio_transform
        self._lock = RLock()
        self._counter = 0
        self._turn_id = None
        self._chunks = []
        self._speech_open = False
        self._pending_silence = False
        self._finalized_turns = 0
        self._cancelled_turns = 0

    def status(self) -> ContinuousTurnStatus:
        with self._lock:
            return ContinuousTurnStatus(
                active=self._turn_id is not None,
                pending_silence=bool(self._pending_silence),
                turn_id=self._turn_id,
                buffered_chunks=len(self._chunks),
                finalized_turns=self._finalized_turns,
                cancelled_turns=self._cancelled_turns,
            )

    @staticmethod
    def _ms(event: Any) -> int:
        return int(round(float(getattr(event, "at_ms"))))

    @staticmethod
    def _audio(event: Any):
        return getattr(event, "audio")

    def on_speech_started(self, event: Any) -> None:
        at_ms = self._ms(event)
        with self._lock:
            if self._turn_id is not None and self._pending_silence:
                self.detector.speech_activity(self._turn_id, at_ms=at_ms)
                self._pending_silence = False
                self._speech_open = True
                return

            if self._turn_id is not None:
                self._cancel_locked(count=True)

            self._counter += 1
            self._turn_id = f"AUTO-CONT-{self._counter:08d}"
            self._chunks = []
            self._speech_open = True
            self._pending_silence = False
            self.detector.begin(self._turn_id, at_ms=at_ms)

    def on_audio_chunk(self, event: Any) -> bool:
        at_ms = self._ms(event)
        callback = None
        finalized = None

        with self._lock:
            if self._turn_id is None:
                return False

            if self._speech_open:
                arr = np.asarray(self._audio(event), dtype=np.float32)
                if arr.ndim > 1:
                    arr = arr.reshape(-1)
                self._chunks.append(arr.copy())
                return False

            if not self._pending_silence:
                return False

            decision = self.detector.evaluate(self._turn_id, at_ms=at_ms)
            if not bool(self._is_ready(decision)):
                return False

            finalized = self._finalize_locked()
            callback = self._on_finalized_audio

        if finalized is not None and callable(callback):
            callback(finalized)
        return finalized is not None

    def on_speech_ended(self, event: Any) -> None:
        at_ms = self._ms(event)
        with self._lock:
            if self._turn_id is None or not self._speech_open:
                return
            self.detector.speech_stopped(self._turn_id, at_ms=at_ms)
            self._speech_open = False
            self._pending_silence = True

    def cancel(self, reason: str = "cancelled") -> None:
        del reason
        with self._lock:
            if self._turn_id is not None or self._chunks:
                self._cancel_locked(count=True)

    def reset(self) -> None:
        with self._lock:
            self._cancel_locked(count=False)
            self._finalized_turns = 0
            self._cancelled_turns = 0

    def _cancel_locked(self, *, count: bool) -> None:
        if count:
            self._cancelled_turns += 1
        reset = getattr(self.detector, "reset", None)
        if callable(reset):
            reset()
        self._turn_id = None
        self._chunks = []
        self._speech_open = False
        self._pending_silence = False

    def _resample(self, audio: np.ndarray) -> np.ndarray:
        if self.source_sample_rate == self.target_sample_rate or audio.size < 2:
            return audio.astype(np.float32, copy=False)
        out_n = max(
            1,
            int(round(audio.size * self.target_sample_rate / self.source_sample_rate)),
        )
        old_x = np.linspace(0.0, 1.0, num=audio.size, endpoint=False)
        new_x = np.linspace(0.0, 1.0, num=out_n, endpoint=False)
        return np.interp(new_x, old_x, audio).astype(np.float32)

    def _finalize_locked(self):
        if self._turn_id is None:
            return None

        if self._chunks:
            audio = np.concatenate(self._chunks).astype(np.float32, copy=False)
        else:
            audio = np.empty((0,), dtype=np.float32)

        audio = self._resample(audio)

        if callable(self.audio_transform) and audio.size:
            transformed = self.audio_transform(audio, self.target_sample_rate)
            if transformed is not None:
                audio = np.asarray(transformed, dtype=np.float32).reshape(-1)

        reset = getattr(self.detector, "reset", None)
        if callable(reset):
            reset()

        self._finalized_turns += 1
        self._turn_id = None
        self._chunks = []
        self._speech_open = False
        self._pending_silence = False

        if audio.size == 0:
            return None
        return audio
