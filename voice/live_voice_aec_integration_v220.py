from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable

import numpy as np

from voice.live_voice_aec_processor_v220 import BoundedReferenceNLMSEchoCanceller
from voice.live_voice_playback_reference_v220 import PlaybackReferenceBuffer, PlaybackReferenceFrame


@dataclass(frozen=True, slots=True)
class AECIntegrationStatus:
    enabled: bool
    generation: int | None
    bound_backends: int
    processed_blocks: int
    fail_open_blocks: int
    reference_blocks: int
    last_reference_sequence: int
    last_error: str


def bind_playback_reference_to_voice_engine(
    voice_engine: Any,
    callback: Callable[..., Any],
) -> int:
    """Bind telemetry only to already-owned compatible TTS backends."""
    if voice_engine is None or not callable(callback):
        return 0

    bound = 0
    seen: set[int] = set()
    for attr in ("tts", "fallback_tts", "cloud_fallback_tts"):
        backend = getattr(voice_engine, attr, None)
        if backend is None or id(backend) in seen:
            continue
        seen.add(id(backend))
        setter = getattr(backend, "set_playback_reference_callback", None)
        if not callable(setter):
            continue
        setter(callback)
        bound += 1
    return bound


class LiveVoiceAECIntegrationBridge:
    """Subordinate far-end/AEC bridge for the AutoMic dispatch worker."""

    def __init__(
        self,
        *,
        reference_buffer: PlaybackReferenceBuffer,
        canceller: BoundedReferenceNLMSEchoCanceller,
        enabled: bool = False,
        target_sample_rate: int = 48000,
        max_reference_fifo_seconds: float = 2.0,
        post_reference_tail_ms: float = 400.0,
    ):
        self.reference_buffer = reference_buffer
        self.canceller = canceller
        self.enabled = bool(enabled)
        self.target_sample_rate = int(target_sample_rate)
        if self.target_sample_rate <= 0:
            raise ValueError("target_sample_rate must be positive")
        self.max_reference_fifo_samples = max(
            self.target_sample_rate // 4,
            int(round(self.target_sample_rate * float(max_reference_fifo_seconds))),
        )
        self.post_reference_tail_samples = max(
            0,
            int(round(self.target_sample_rate * float(post_reference_tail_ms) / 1000.0)),
        )
        self._lock = RLock()
        self._reference_fifo = np.zeros(0, dtype=np.float32)
        self._generation: int | None = None
        self._last_reference_sequence = 0
        self._tail_samples_remaining = 0
        self._processed_blocks = 0
        self._fail_open_blocks = 0
        self._reference_blocks = 0
        self._bound_backends = 0
        self._last_error = ""

    @staticmethod
    def _mono_float32(audio: Any) -> np.ndarray:
        arr = np.asarray(audio, dtype=np.float32)
        if arr.ndim == 2:
            arr = np.mean(arr, axis=1, dtype=np.float32)
        if arr.ndim != 1:
            raise ValueError("near-end audio must be mono or frames x channels")
        return np.ascontiguousarray(arr, dtype=np.float32)

    @staticmethod
    def _decode_frame(frame: PlaybackReferenceFrame) -> np.ndarray:
        dtype = str(frame.dtype or "").strip().lower()
        if dtype in ("int16", "<i2", ">i2", "=i2"):
            arr = np.frombuffer(frame.payload, dtype=np.int16).astype(np.float32)
            arr /= np.float32(32768.0)
        elif dtype in ("float32", "<f4", ">f4", "=f4"):
            arr = np.frombuffer(frame.payload, dtype=np.float32).astype(np.float32, copy=True)
        elif dtype in ("int32", "<i4", ">i4", "=i4"):
            arr = np.frombuffer(frame.payload, dtype=np.int32).astype(np.float32)
            arr /= np.float32(2147483648.0)
        else:
            raise ValueError(f"unsupported playback reference dtype: {frame.dtype!r}")

        channels = max(1, int(frame.channels))
        if channels > 1:
            usable = (arr.size // channels) * channels
            if usable <= 0:
                return np.zeros(0, dtype=np.float32)
            arr = arr[:usable].reshape(-1, channels).mean(axis=1, dtype=np.float32)
        return np.ascontiguousarray(arr, dtype=np.float32)

    @staticmethod
    def _resample_linear(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
        source_rate = int(source_rate)
        target_rate = int(target_rate)
        if audio.size == 0 or source_rate == target_rate:
            return np.ascontiguousarray(audio, dtype=np.float32)
        if source_rate <= 0 or target_rate <= 0:
            raise ValueError("sample rates must be positive")
        target_size = max(1, int(round(audio.size * target_rate / source_rate)))
        if audio.size == 1:
            return np.full(target_size, float(audio[0]), dtype=np.float32)
        x_old = np.linspace(0.0, 1.0, audio.size, endpoint=False, dtype=np.float64)
        x_new = np.linspace(0.0, 1.0, target_size, endpoint=False, dtype=np.float64)
        return np.interp(x_new, x_old, audio.astype(np.float64)).astype(np.float32)

    def set_bound_backends(self, count: int) -> None:
        with self._lock:
            self._bound_backends = max(0, int(count))

    def reset(self) -> None:
        with self._lock:
            self._reference_fifo = np.zeros(0, dtype=np.float32)
            self._generation = None
            self._last_reference_sequence = 0
            self._tail_samples_remaining = 0
            self._last_error = ""
        try:
            self.reference_buffer.clear()
        except Exception:
            pass
        self.canceller.reset()

    def _ingest_reference_locked(self) -> None:
        frames = self.reference_buffer.snapshot()
        fresh = [
            frame for frame in frames
            if int(frame.sequence) > int(self._last_reference_sequence)
        ]
        if not fresh:
            return

        for frame in fresh:
            if self._generation != int(frame.generation):
                self._generation = int(frame.generation)
                self._reference_fifo = np.zeros(0, dtype=np.float32)
                self._tail_samples_remaining = 0
                self.canceller.reset()

            decoded = self._decode_frame(frame)
            resampled = self._resample_linear(
                decoded,
                int(frame.sample_rate),
                self.target_sample_rate,
            )
            if resampled.size:
                self._reference_fifo = np.concatenate(
                    (self._reference_fifo, resampled.astype(np.float32, copy=False))
                )
                if self._reference_fifo.size > self.max_reference_fifo_samples:
                    self._reference_fifo = self._reference_fifo[
                        -self.max_reference_fifo_samples:
                    ].copy()
                # AURA_R23_R5_R2_R2_R1_TAIL_ARM
                self._tail_samples_remaining = self.post_reference_tail_samples
                self._reference_blocks += 1
            self._last_reference_sequence = max(
                self._last_reference_sequence,
                int(frame.sequence),
            )

    def process_near_end(self, audio: Any, sample_rate: float) -> Any:
        """Return AEC residual or original near-end on any unsafe condition."""
        if not self.enabled:
            return audio

        try:
            rate = int(round(float(sample_rate)))
            if rate != self.target_sample_rate:
                raise ValueError(
                    f"near-end rate {rate} does not match AEC target "
                    f"{self.target_sample_rate}"
                )

            near = self._mono_float32(audio)
            if near.size == 0:
                return audio

            with self._lock:
                self._ingest_reference_locked()

                # AURA_R23_R5_R2_R2_R1_TAIL_CONTINUATION
                tail_mode = False
                if self._reference_fifo.size >= near.size:
                    far = self._reference_fifo[:near.size].copy()
                    self._reference_fifo = self._reference_fifo[near.size:].copy()
                elif self._reference_fifo.size > 0:
                    available = self._reference_fifo.copy()
                    missing = int(near.size - available.size)
                    far = np.concatenate(
                        (available, np.zeros(missing, dtype=np.float32))
                    )
                    self._reference_fifo = np.zeros(0, dtype=np.float32)
                    self._tail_samples_remaining = max(
                        0,
                        int(self._tail_samples_remaining) - missing,
                    )
                    tail_mode = True
                elif self._tail_samples_remaining > 0:
                    far = np.zeros(near.size, dtype=np.float32)
                    self._tail_samples_remaining = max(
                        0,
                        int(self._tail_samples_remaining) - int(near.size),
                    )
                    tail_mode = True
                else:
                    self._fail_open_blocks += 1
                    return audio

            far_rms = float(np.sqrt(np.mean(np.square(far, dtype=np.float64))))
            if far_rms < 1e-5 and not tail_mode:
                with self._lock:
                    self._fail_open_blocks += 1
                return audio

            near_rms = float(np.sqrt(np.mean(np.square(near, dtype=np.float64))))
            adapt = False if tail_mode else not (
                near_rms > max(0.12, far_rms * 1.50)
            )

            result = self.canceller.process_block(near, far, adapt=adapt)
            residual = np.ascontiguousarray(result.audio, dtype=np.float32)
            if residual.shape != near.shape or not np.all(np.isfinite(residual)):
                raise ValueError("invalid AEC residual")

            with self._lock:
                self._processed_blocks += 1
                self._last_error = ""
            return residual

        except Exception as exc:
            with self._lock:
                self._fail_open_blocks += 1
                self._last_error = f"{type(exc).__name__}:{exc}"
            return audio

    def status(self) -> AECIntegrationStatus:
        with self._lock:
            return AECIntegrationStatus(
                enabled=self.enabled,
                generation=self._generation,
                bound_backends=self._bound_backends,
                processed_blocks=self._processed_blocks,
                fail_open_blocks=self._fail_open_blocks,
                reference_blocks=self._reference_blocks,
                last_reference_sequence=self._last_reference_sequence,
                last_error=self._last_error,
            )
