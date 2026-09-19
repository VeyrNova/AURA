from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import RLock
import time
from typing import Callable, Iterable


_DTYPE_BYTES = {
    "int8": 1,
    "uint8": 1,
    "int16": 2,
    "uint16": 2,
    "int32": 4,
    "uint32": 4,
    "float32": 4,
    "float64": 8,
}


@dataclass(frozen=True, slots=True)
class PlaybackReferenceFrame:
    sequence: int
    generation: int
    at_monotonic: float
    sample_rate: int
    channels: int
    dtype: str
    payload: bytes
    frame_count: int
    duration_seconds: float


@dataclass(frozen=True, slots=True)
class PlaybackReferenceStatus:
    generation: int | None
    frame_count: int
    buffered_bytes: int
    buffered_seconds: float
    sequence: int


class PlaybackReferenceBuffer:
    """Bounded, thread-safe far-end PCM telemetry for future AEC consumers.

    This class owns no device, TTS lifecycle, conversation/session authority,
    microphone lifecycle, memory, or durable state.
    """

    def __init__(
        self,
        *,
        max_seconds: float = 5.0,
        max_chunks: int = 256,
        max_bytes: int = 2 * 1024 * 1024,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.max_seconds = max(0.05, float(max_seconds))
        self.max_chunks = max(1, int(max_chunks))
        self.max_bytes = max(1024, int(max_bytes))
        self._clock = clock
        self._lock = RLock()
        self._frames: deque[PlaybackReferenceFrame] = deque()
        self._generation: int | None = None
        self._bytes = 0
        self._seconds = 0.0
        self._sequence = 0

    @staticmethod
    def _normalize_dtype(dtype: object) -> str:
        value = str(dtype or "").strip().lower()
        if value.startswith("<") or value.startswith(">") or value.startswith("="):
            value = value[1:]
        return value

    @staticmethod
    def _to_bytes(payload: object) -> bytes:
        if isinstance(payload, bytes):
            return payload
        if isinstance(payload, bytearray):
            return bytes(payload)
        if isinstance(payload, memoryview):
            return payload.tobytes()
        try:
            return memoryview(payload).tobytes()
        except Exception as exc:
            raise TypeError("playback reference payload is not bytes-compatible") from exc

    def _clear_locked(self) -> None:
        self._frames.clear()
        self._bytes = 0
        self._seconds = 0.0

    def clear(self) -> None:
        with self._lock:
            self._clear_locked()

    def invalidate(self) -> int:
        """Invalidate buffered reference without owning the producer generation."""
        with self._lock:
            next_generation = 0 if self._generation is None else int(self._generation) + 1
            self._generation = next_generation
            self._clear_locked()
            return next_generation

    def push_pcm(
        self,
        payload: object,
        *,
        sample_rate: int,
        channels: int,
        dtype: object,
        generation: int,
        at_monotonic: float | None = None,
    ) -> PlaybackReferenceFrame | None:
        raw = self._to_bytes(payload)
        if not raw:
            return None

        rate = int(sample_rate)
        chans = int(channels)
        dtype_name = self._normalize_dtype(dtype)
        if rate <= 0 or chans <= 0:
            raise ValueError("sample_rate and channels must be positive")

        bytes_per_sample = _DTYPE_BYTES.get(dtype_name)
        if bytes_per_sample is None:
            raise ValueError(f"unsupported playback reference dtype: {dtype_name!r}")

        bytes_per_frame = chans * bytes_per_sample
        frame_count = len(raw) // bytes_per_frame
        if frame_count <= 0:
            return None

        duration = float(frame_count) / float(rate)
        timestamp = float(self._clock() if at_monotonic is None else at_monotonic)
        generation = int(generation)

        with self._lock:
            if self._generation != generation:
                self._generation = generation
                self._clear_locked()

            self._sequence += 1
            frame = PlaybackReferenceFrame(
                sequence=self._sequence,
                generation=generation,
                at_monotonic=timestamp,
                sample_rate=rate,
                channels=chans,
                dtype=dtype_name,
                payload=raw,
                frame_count=frame_count,
                duration_seconds=duration,
            )
            self._frames.append(frame)
            self._bytes += len(raw)
            self._seconds += duration

            while self._frames and (
                len(self._frames) > self.max_chunks
                or self._bytes > self.max_bytes
                or self._seconds > self.max_seconds
            ):
                old = self._frames.popleft()
                self._bytes -= len(old.payload)
                self._seconds -= old.duration_seconds

            if self._seconds < 0.0:
                self._seconds = 0.0

            return frame

    __call__ = push_pcm

    def snapshot(
        self,
        *,
        generation: int | None = None,
        since_monotonic: float | None = None,
    ) -> tuple[PlaybackReferenceFrame, ...]:
        with self._lock:
            items: Iterable[PlaybackReferenceFrame] = tuple(self._frames)

        if generation is not None:
            generation = int(generation)
            items = tuple(x for x in items if x.generation == generation)
        if since_monotonic is not None:
            threshold = float(since_monotonic)
            items = tuple(x for x in items if x.at_monotonic >= threshold)
        return tuple(items)

    def status(self) -> PlaybackReferenceStatus:
        with self._lock:
            return PlaybackReferenceStatus(
                generation=self._generation,
                frame_count=len(self._frames),
                buffered_bytes=self._bytes,
                buffered_seconds=max(0.0, self._seconds),
                sequence=self._sequence,
            )
