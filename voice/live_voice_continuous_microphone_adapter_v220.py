from __future__ import annotations

"""
AURA v2.2 - optional continuous microphone capture adapter.

Contract:
- Push-to-Talk remains permanent.
- Continuous capture is optional and disabled by default.
- This adapter owns no LiveVoiceSession, STT, TTS, memory or barge authority.
- It only owns a physical input stream when explicitly started.
- It can yield microphone ownership to PTT with pause_for_ptt(), then resume.
- Captured frames are delivered to a supplied callback.
"""

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Optional


AudioFrameCallback = Callable[[Any, float], Any]


@dataclass(frozen=True)
class ContinuousMicStatus:
    enabled: bool
    running: bool
    paused_for_ptt: bool
    stream_open: bool
    device: Any
    sample_rate: int
    channels: int


class LiveVoiceContinuousMicrophoneAdapter:
    """Subordinate physical-capture adapter with explicit PTT handoff."""

    def __init__(
        self,
        *,
        on_audio_frame: AudioFrameCallback,
        stream_factory: Callable[..., Any],
        device: Any = None,
        sample_rate: int = 48_000,
        channels: int = 1,
        blocksize: int = 960,
        dtype: str = "float32",
        enabled: bool = False,
    ) -> None:
        if not callable(on_audio_frame):
            raise TypeError("on_audio_frame must be callable")
        if not callable(stream_factory):
            raise TypeError("stream_factory must be callable")

        self._on_audio_frame = on_audio_frame
        self._stream_factory = stream_factory
        self._device = device
        self._sample_rate = int(sample_rate)
        self._channels = int(channels)
        self._blocksize = int(blocksize)
        self._dtype = str(dtype)
        self._enabled = bool(enabled)
        self._running = False
        self._paused_for_ptt = False
        self._stream = None
        self._lock = RLock()

        if self._sample_rate <= 0:
            raise ValueError("sample_rate must be > 0")
        if self._channels <= 0:
            raise ValueError("channels must be > 0")
        if self._blocksize <= 0:
            raise ValueError("blocksize must be > 0")

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def paused_for_ptt(self) -> bool:
        with self._lock:
            return self._paused_for_ptt

    def enable(self) -> None:
        with self._lock:
            self._enabled = True

    def disable(self) -> None:
        self.stop()
        with self._lock:
            self._enabled = False
            self._paused_for_ptt = False

    def status(self) -> ContinuousMicStatus:
        with self._lock:
            return ContinuousMicStatus(
                enabled=self._enabled,
                running=self._running,
                paused_for_ptt=self._paused_for_ptt,
                stream_open=self._stream is not None,
                device=self._device,
                sample_rate=self._sample_rate,
                channels=self._channels,
            )

    def _callback(self, indata, frames, time_info, status) -> None:
        del frames, time_info, status

        with self._lock:
            if not self._enabled or not self._running or self._paused_for_ptt:
                return
            callback = self._on_audio_frame
            sample_rate = self._sample_rate

        # Never hold the adapter lock while calling downstream code.
        callback(indata, float(sample_rate))

    def start(self) -> bool:
        with self._lock:
            if not self._enabled:
                return False
            if self._paused_for_ptt:
                return False
            if self._running:
                return True

            stream = self._stream_factory(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype=self._dtype,
                blocksize=self._blocksize,
                device=self._device,
                callback=self._callback,
            )

            self._stream = stream

        try:
            stream.start()
        except Exception:
            with self._lock:
                self._stream = None
            try:
                stream.close()
            except Exception:
                pass
            raise

        with self._lock:
            self._running = True

        return True

    def stop(self) -> None:
        with self._lock:
            stream = self._stream
            self._stream = None
            self._running = False

        if stream is None:
            return

        try:
            stream.stop()
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def pause_for_ptt(self) -> bool:
        """Yield physical microphone ownership to the permanent PTT path."""
        with self._lock:
            was_running = self._running
            self._paused_for_ptt = True

        if was_running:
            self.stop()

        return was_running

    def resume_after_ptt(self) -> bool:
        """Release PTT priority and resume optional continuous capture if enabled."""
        with self._lock:
            self._paused_for_ptt = False
            should_resume = self._enabled and not self._running

        if should_resume:
            return self.start()

        return False
