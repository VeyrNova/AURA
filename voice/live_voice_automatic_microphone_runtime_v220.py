from __future__ import annotations

"""
AURA v2.2 - optional production automatic microphone runtime.

Permanent product contract:
- Push-to-Talk remains available and has microphone priority.
- Automatic microphone/VAD mode is optional and disabled by default.
- This module owns no LiveVoiceSession, STT, TTS, memory or durable authority.
- It composes the already-certified subordinate microphone adapter, microphone
  ingress and automatic barge bridge.

R18-R4-R15-R1 hardening:
- The native microphone/PortAudio callback MUST NOT execute VAD, ingress,
  canonical barge logic or PiperTTS.stop() synchronously.
- The callback copies one frame and enqueues it into a bounded queue only.
- A dedicated Python control worker performs VAD -> ingress -> bridge outside
  the native audio callback thread.
"""

from dataclasses import dataclass
import math
from queue import Empty, Full, Queue
import statistics
import time
from threading import Event, RLock, Thread, current_thread
from typing import Any, Callable, Optional

from voice.live_voice_auto_barge_bridge_v220 import LiveVoiceAutomaticBargeBridge
from voice.live_voice_continuous_microphone_adapter_v220 import (
    LiveVoiceContinuousMicrophoneAdapter,
)
from voice.live_voice_microphone_ingress_v220 import LiveVoiceMicrophoneIngress


# R18-R4-R15-R2-R1 AutoMic configured-device alignment
def resolve_configured_automatic_microphone_device(explicit_device: Any = None):
    """Use explicit AutoMic routing, otherwise inherit AURA's configured PTT device."""
    if explicit_device is not None and str(explicit_device).strip() != "":
        return explicit_device

    try:
        from config.settings import settings
        from voice.microphone import MicrophoneRecorder

        recorder = MicrophoneRecorder(
            sample_rate=int(getattr(settings, "MIC_SAMPLE_RATE", 16000)),
            channels=int(getattr(settings, "MIC_CHANNELS", 1)),
            max_seconds=float(getattr(settings, "MIC_MAX_SECONDS", 30.0)),
            min_seconds=float(getattr(settings, "MIC_MIN_SECONDS", 0.15)),
            requested_device=str(getattr(settings, "MIC_DEVICE", "") or "").strip(),
        )
        info = recorder.resolve_input_device()
        if info is not None:
            return int(info.index)
    except Exception:
        # Preserve prior fallback: sounddevice chooses its default input.
        pass

    return explicit_device


def sounddevice_input_stream_factory(**kwargs):
    """Production physical stream factory, imported lazily."""
    import sounddevice as sd
    return sd.InputStream(**kwargs)


@dataclass(frozen=True)
class EnergyVADStatus:
    calibrated: bool
    calibration_samples: int
    calibration_target: int
    threshold_rms: Optional[float]
    speech_active: bool
    last_rms: float


class ProductionEnergyVAD:
    """Calibrated low-gain-friendly energy VAD with onset/release hysteresis."""

    def __init__(
        self,
        *,
        calibration_blocks: int = 125,
        onset_blocks: int = 3,
        release_blocks: int = 4,
    ) -> None:
        if int(calibration_blocks) < 10:
            raise ValueError("calibration_blocks must be >= 10")
        if int(onset_blocks) < 1:
            raise ValueError("onset_blocks must be >= 1")
        if int(release_blocks) < 1:
            raise ValueError("release_blocks must be >= 1")

        self._calibration_target = int(calibration_blocks)
        self._onset_blocks = int(onset_blocks)
        self._release_blocks = int(release_blocks)
        self._lock = RLock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._calibration = []
            self._threshold = None
            self._speech_active = False
            self._above = 0
            self._below = 0
            self._last_rms = 0.0

    @staticmethod
    def _rms(audio: Any) -> float:
        try:
            import numpy as np
            arr = np.asarray(audio, dtype=np.float32)
            if arr.size == 0:
                return 0.0
            if arr.ndim > 1:
                arr = arr.mean(axis=1)
            value = float(
                np.sqrt(
                    np.mean(
                        np.square(arr),
                        dtype=np.float64,
                    )
                )
            )
        except Exception:
            try:
                values = [float(x) for x in audio]
            except Exception:
                return 0.0
            if not values:
                return 0.0
            value = math.sqrt(
                sum(x * x for x in values) / len(values)
            )

        if not math.isfinite(value):
            return 0.0
        return max(0.0, value)

    @staticmethod
    def _threshold_from(samples: list[float]) -> float:
        ordered = sorted(float(x) for x in samples)
        median = float(statistics.median(ordered))
        idx = min(
            len(ordered) - 1,
            max(0, int(round(0.95 * (len(ordered) - 1)))),
        )
        p95 = float(ordered[idx])
        mad = float(
            statistics.median(
                [abs(x - median) for x in ordered]
            )
        )

        return max(
            p95 * 2.20,
            median + max(6.0 * mad, 0.00012),
            median * 3.0,
            0.00018,
        )

    @property
    def calibrated(self) -> bool:
        with self._lock:
            return self._threshold is not None

    @property
    def threshold_rms(self) -> Optional[float]:
        with self._lock:
            return self._threshold

    @property
    def speech_active(self) -> bool:
        with self._lock:
            return self._speech_active

    def status(self) -> EnergyVADStatus:
        with self._lock:
            return EnergyVADStatus(
                calibrated=self._threshold is not None,
                calibration_samples=len(self._calibration),
                calibration_target=self._calibration_target,
                threshold_rms=self._threshold,
                speech_active=self._speech_active,
                last_rms=self._last_rms,
            )

    def process(self, audio: Any) -> Optional[float]:
        """Return None during calibration, else probability 0.95 or 0.10."""
        rms = self._rms(audio)

        with self._lock:
            self._last_rms = rms

            if self._threshold is None:
                self._calibration.append(rms)
                if len(self._calibration) < self._calibration_target:
                    return None

                self._threshold = self._threshold_from(
                    self._calibration
                )
                self._above = 0
                self._below = 0
                self._speech_active = False
                return 0.10

            threshold = self._threshold

            if rms >= threshold:
                self._above += 1
                self._below = 0
            else:
                self._below += 1
                self._above = 0

            if (
                not self._speech_active
                and self._above >= self._onset_blocks
            ):
                self._speech_active = True

            if (
                self._speech_active
                and self._below >= self._release_blocks
            ):
                self._speech_active = False

            return 0.95 if self._speech_active else 0.10


@dataclass(frozen=True)
class AutomaticMicrophoneRuntimeStatus:
    enabled: bool
    calibrated: bool
    threshold_rms: Optional[float]
    speech_active: bool
    capture_running: bool
    paused_for_ptt: bool


@dataclass(frozen=True)
class AutomaticMicrophoneDispatchStatus:
    worker_alive: bool
    queue_size: int
    queue_capacity: int
    paused: bool
    dropped_frames: int
    processed_frames: int
    worker_error: Optional[str]


class LiveVoiceAutomaticMicrophoneRuntime:
    """
    Subordinate composition:
      physical stream
        -> bounded callback queue
        -> control worker
        -> ProductionEnergyVAD
        -> microphone ingress
        -> automatic barge bridge
        -> existing provider bindings/session.

    Native audio callbacks never execute the canonical barge/TTS stop path.
    """

    DISPATCH_QUEUE_CAPACITY = 32
    DISPATCH_THREAD_NAME = "AURA-LiveVoice-AutoMic-Dispatch"

    def __init__(
        self,
        *,
        bindings: Any,
        device: Any = None,
        sample_rate: int = 48_000,
        channels: int = 1,
        blocksize: int = 960,
        stream_factory: Optional[Callable[..., Any]] = None,
        enabled: bool = False,
        calibration_blocks: int = 125,
        clock_ms: Optional[Callable[[], float]] = None,
    ) -> None:
        self._lock = RLock()
        self._process_lock = RLock()
        self._enabled = bool(enabled)
        self._clock_ms = (
            clock_ms
            if callable(clock_ms)
            else lambda: time.perf_counter() * 1000.0
        )

        self._dispatch_queue: Queue = Queue(
            maxsize=self.DISPATCH_QUEUE_CAPACITY
        )
        self._dispatch_stop = Event()
        self._dispatch_paused = Event()
        self._dispatch_thread: Optional[Thread] = None
        self._dispatch_sentinel = object()
        self._dispatch_epoch = 0
        self._dropped_frames = 0
        self._processed_frames = 0
        self._worker_error: Optional[str] = None

        self.vad = ProductionEnergyVAD(
            calibration_blocks=calibration_blocks,
        )
        self.bridge = LiveVoiceAutomaticBargeBridge(
            bindings=bindings,
            enabled=enabled,
        )
        self.ingress = LiveVoiceMicrophoneIngress(
            enabled=enabled,
            queue_capacity=32,
            speech_start_threshold=0.70,
            speech_end_threshold=0.35,
            on_speech_started=self.bridge.on_speech_started,
        )
        resolved_device = resolve_configured_automatic_microphone_device(device)
        self.capture = LiveVoiceContinuousMicrophoneAdapter(
            on_audio_frame=self._on_audio_frame,
            stream_factory=(
                stream_factory
                if callable(stream_factory)
                else sounddevice_input_stream_factory
            ),
            device=resolved_device,
            sample_rate=sample_rate,
            channels=channels,
            blocksize=blocksize,
            dtype="float32",
            enabled=enabled,
        )

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    @property
    def dispatch_thread_name(self) -> str:
        return self.DISPATCH_THREAD_NAME

    def dispatch_status(self) -> AutomaticMicrophoneDispatchStatus:
        with self._lock:
            thread = self._dispatch_thread
            return AutomaticMicrophoneDispatchStatus(
                worker_alive=bool(thread and thread.is_alive()),
                queue_size=int(self._dispatch_queue.qsize()),
                queue_capacity=int(self._dispatch_queue.maxsize),
                paused=self._dispatch_paused.is_set(),
                dropped_frames=int(self._dropped_frames),
                processed_frames=int(self._processed_frames),
                worker_error=self._worker_error,
            )

    def _copy_audio_for_dispatch(self, audio: Any) -> Any:
        copier = getattr(audio, "copy", None)
        if callable(copier):
            return copier()

        if isinstance(audio, tuple):
            return tuple(audio)

        if isinstance(audio, list):
            return list(audio)

        try:
            return tuple(audio)
        except Exception:
            return audio

    def _clear_dispatch_queue(self) -> None:
        while True:
            try:
                self._dispatch_queue.get_nowait()
            except Empty:
                return

    def _ensure_dispatch_worker(self) -> None:
        with self._lock:
            thread = self._dispatch_thread
            if thread is not None and thread.is_alive():
                return

            self._dispatch_stop.clear()
            self._worker_error = None
            thread = Thread(
                target=self._dispatch_loop,
                name=self.DISPATCH_THREAD_NAME,
                daemon=True,
            )
            self._dispatch_thread = thread
            thread.start()

    def _stop_dispatch_worker(self) -> None:
        with self._lock:
            thread = self._dispatch_thread
            self._dispatch_stop.set()

        try:
            self._dispatch_queue.put_nowait(self._dispatch_sentinel)
        except Full:
            try:
                self._dispatch_queue.get_nowait()
            except Empty:
                pass
            try:
                self._dispatch_queue.put_nowait(self._dispatch_sentinel)
            except Full:
                pass

        if (
            thread is not None
            and thread.is_alive()
            and thread is not current_thread()
        ):
            thread.join(timeout=1.0)

        with self._lock:
            if self._dispatch_thread is thread:
                self._dispatch_thread = None

        self._clear_dispatch_queue()

    def _dispatch_loop(self) -> None:
        try:
            while not self._dispatch_stop.is_set():
                try:
                    item = self._dispatch_queue.get(timeout=0.05)
                except Empty:
                    continue

                if item is self._dispatch_sentinel:
                    return

                try:
                    epoch, audio, sample_rate = item
                except Exception:
                    continue

                with self._lock:
                    enabled = self._enabled
                    current_epoch = self._dispatch_epoch

                if (
                    not enabled
                    or self._dispatch_paused.is_set()
                    or epoch != current_epoch
                ):
                    continue

                with self._process_lock:
                    with self._lock:
                        enabled = self._enabled
                        current_epoch = self._dispatch_epoch

                    if (
                        not enabled
                        or self._dispatch_paused.is_set()
                        or epoch != current_epoch
                    ):
                        continue

                    self._process_audio_frame(
                        audio,
                        sample_rate,
                    )

                    with self._lock:
                        self._processed_frames += 1

        except Exception as exc:
            with self._lock:
                self._worker_error = (
                    f"{type(exc).__name__}:{exc}"
                )
            self._dispatch_stop.set()

    def _process_audio_frame(
        self,
        audio: Any,
        sample_rate: float,
    ) -> None:
        del sample_rate

        if not self.enabled:
            return

        probability = self.vad.process(audio)
        if probability is None:
            return

        self.ingress.push_audio(
            audio,
            speech_probability=probability,
            at_ms=float(self._clock_ms()),
        )

    def enable(self) -> None:
        with self._lock:
            self._enabled = True
        self.bridge.enable()
        self.ingress.enable()
        self.capture.enable()

    def disable(self) -> None:
        with self._lock:
            self._enabled = False
            self._dispatch_epoch += 1

        self._dispatch_paused.set()

        self.capture.disable()
        self._stop_dispatch_worker()
        self.ingress.disable()
        self.bridge.disable()

        self._dispatch_paused.clear()

    def start(self) -> bool:
        if not self.enabled:
            return False

        self._ensure_dispatch_worker()

        try:
            started = self.capture.start()
        except Exception:
            self._stop_dispatch_worker()
            raise

        if not started:
            self._stop_dispatch_worker()
            return False

        return True

    def stop(self) -> None:
        self.capture.stop()
        self._stop_dispatch_worker()

    def reset_calibration(self) -> None:
        with self._lock:
            self._dispatch_epoch += 1
        self._clear_dispatch_queue()
        self.vad.reset()
        self.ingress.reset()

    def pause_for_ptt(self) -> bool:
        """Permanent PTT receives microphone priority."""
        self._dispatch_paused.set()

        with self._lock:
            self._dispatch_epoch += 1

        was_running = self.capture.pause_for_ptt()

        # Wait for any already-running control dispatch to complete before
        # handing the device to PTT, then discard every stale queued frame.
        with self._process_lock:
            self._clear_dispatch_queue()

        return was_running

    def resume_after_ptt(self) -> bool:
        resumed = self.capture.resume_after_ptt()
        self._dispatch_paused.clear()
        return resumed

    def status(self) -> AutomaticMicrophoneRuntimeStatus:
        vad = self.vad.status()
        capture = self.capture.status()
        return AutomaticMicrophoneRuntimeStatus(
            enabled=self.enabled,
            calibrated=vad.calibrated,
            threshold_rms=vad.threshold_rms,
            speech_active=vad.speech_active,
            capture_running=capture.running,
            paused_for_ptt=capture.paused_for_ptt,
        )

    def _on_audio_frame(self, audio: Any, sample_rate: float) -> None:
        """
        Native callback boundary.

        Never run VAD / ingress / barge / TTS cancellation here.
        Copy one frame and enqueue it without blocking.
        """
        if not self.enabled or self._dispatch_paused.is_set():
            return

        copied = self._copy_audio_for_dispatch(audio)

        with self._lock:
            epoch = self._dispatch_epoch

        item = (epoch, copied, float(sample_rate))

        try:
            self._dispatch_queue.put_nowait(item)
            return
        except Full:
            pass

        # Bounded real-time behavior: drop the oldest queued frame rather
        # than block PortAudio. This favors freshest speech onset evidence.
        try:
            self._dispatch_queue.get_nowait()
        except Empty:
            pass

        with self._lock:
            self._dropped_frames += 1

        try:
            self._dispatch_queue.put_nowait(item)
        except Full:
            with self._lock:
                self._dropped_frames += 1
