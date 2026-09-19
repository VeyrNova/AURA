from __future__ import annotations

from dataclasses import dataclass
import math
from threading import RLock
from typing import Iterable

import numpy as np


@dataclass(frozen=True, slots=True)
class AECConfig:
    sample_rate: int = 16000
    filter_length_samples: int = 192
    max_delay_ms: float = 250.0
    adaptation_rate: float = 0.45
    epsilon: float = 1e-6
    min_reference_rms: float = 1e-5
    max_block_samples: int = 4096


@dataclass(frozen=True, slots=True)
class AECMetrics:
    bulk_delay_samples: int
    reference_rms: float
    microphone_rms: float
    residual_rms: float
    erle_db: float | None
    adaptation_enabled: bool


@dataclass(frozen=True, slots=True)
class AECResult:
    audio: np.ndarray
    echo_estimate: np.ndarray
    metrics: AECMetrics


class BoundedReferenceNLMSEchoCanceller:
    """Local, provider-neutral, bounded NLMS echo-cancellation core.

    It owns no device, microphone callback, TTS, conversation/session state,
    memory, or durable authority. Bulk delay estimation is explicit and
    adaptation can be frozen during double-talk.
    """

    def __init__(self, config: AECConfig | None = None):
        self.config = config or AECConfig()
        if int(self.config.sample_rate) <= 0:
            raise ValueError("sample_rate must be positive")
        if int(self.config.filter_length_samples) <= 0:
            raise ValueError("filter_length_samples must be positive")
        if not (0.0 < float(self.config.adaptation_rate) <= 2.0):
            raise ValueError("adaptation_rate must be in (0, 2]")
        self._lock = RLock()
        self._weights = np.zeros(
            int(self.config.filter_length_samples),
            dtype=np.float32,
        )
        self._history = np.zeros_like(self._weights)
        self._bulk_delay_samples = 0
        self._delay_line = np.zeros(0, dtype=np.float32)

    @staticmethod
    def _mono_float32(audio: object) -> np.ndarray:
        arr = np.asarray(audio, dtype=np.float32)
        if arr.ndim == 2:
            arr = np.mean(arr, axis=1, dtype=np.float32)
        if arr.ndim != 1:
            raise ValueError("audio must be mono or frames x channels")
        return np.ascontiguousarray(arr, dtype=np.float32)

    @staticmethod
    def _rms(audio: np.ndarray) -> float:
        if audio.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))

    @property
    def bulk_delay_samples(self) -> int:
        with self._lock:
            return int(self._bulk_delay_samples)

    def reset(self) -> None:
        with self._lock:
            self._weights.fill(0.0)
            self._history.fill(0.0)
            self._bulk_delay_samples = 0
            self._delay_line = np.zeros(0, dtype=np.float32)

    def set_bulk_delay_samples(self, delay_samples: int) -> int:
        value = max(0, int(delay_samples))
        limit = int(
            round(float(self.config.sample_rate) * float(self.config.max_delay_ms) / 1000.0)
        )
        if value > limit:
            raise ValueError(f"bulk delay {value} exceeds configured limit {limit}")
        with self._lock:
            self._bulk_delay_samples = value
            self._delay_line = np.zeros(value, dtype=np.float32)
        return value

    def estimate_bulk_delay_samples(
        self,
        reference: object,
        microphone: object,
    ) -> int:
        """Estimate non-negative speaker->microphone bulk delay.

        Uses bounded normalized cross-correlation over the configured delay range.
        Intended for control-worker calibration windows, never a native audio callback.
        """
        ref = self._mono_float32(reference)
        mic = self._mono_float32(microphone)
        n = min(ref.size, mic.size)
        if n < 64:
            raise ValueError("delay estimation window too small")
        ref = ref[:n]
        mic = mic[:n]

        max_delay = min(
            n - 32,
            int(round(self.config.sample_rate * self.config.max_delay_ms / 1000.0)),
        )
        if max_delay < 0:
            return 0

        ref_energy_prefix = np.concatenate(
            ([0.0], np.cumsum(np.square(ref, dtype=np.float64)))
        )
        mic_energy_prefix = np.concatenate(
            ([0.0], np.cumsum(np.square(mic, dtype=np.float64)))
        )

        best_delay = 0
        best_score = -1.0
        min_overlap = max(64, min(n, int(self.config.sample_rate * 0.15)))

        for delay in range(max_delay + 1):
            overlap = n - delay
            if overlap < min_overlap:
                break
            x = ref[:overlap]
            y = mic[delay:delay + overlap]

            ex = float(ref_energy_prefix[overlap] - ref_energy_prefix[0])
            ey = float(mic_energy_prefix[delay + overlap] - mic_energy_prefix[delay])
            denom = math.sqrt(max(ex * ey, 0.0)) + float(self.config.epsilon)
            score = abs(float(np.dot(x.astype(np.float64), y.astype(np.float64)))) / denom
            if score > best_score:
                best_score = score
                best_delay = delay

        return self.set_bulk_delay_samples(best_delay)

    def _aligned_reference_locked(self, reference: np.ndarray) -> np.ndarray:
        delay = int(self._bulk_delay_samples)
        if delay <= 0:
            return reference.copy()

        combined = np.concatenate((self._delay_line, reference))
        aligned = combined[: reference.size].astype(np.float32, copy=False)
        self._delay_line = combined[reference.size: reference.size + delay].astype(
            np.float32,
            copy=True,
        )
        if self._delay_line.size != delay:
            padded = np.zeros(delay, dtype=np.float32)
            padded[: self._delay_line.size] = self._delay_line
            self._delay_line = padded
        return np.ascontiguousarray(aligned, dtype=np.float32)

    def process_block(
        self,
        microphone: object,
        reference: object,
        *,
        adapt: bool = True,
    ) -> AECResult:
        mic = self._mono_float32(microphone)
        ref = self._mono_float32(reference)
        if mic.size != ref.size:
            raise ValueError("microphone and reference blocks must have equal length")
        if mic.size > int(self.config.max_block_samples):
            raise ValueError("block exceeds configured bound")
        if mic.size == 0:
            metrics = AECMetrics(
                bulk_delay_samples=self.bulk_delay_samples,
                reference_rms=0.0,
                microphone_rms=0.0,
                residual_rms=0.0,
                erle_db=None,
                adaptation_enabled=bool(adapt),
            )
            return AECResult(
                audio=np.zeros(0, dtype=np.float32),
                echo_estimate=np.zeros(0, dtype=np.float32),
                metrics=metrics,
            )

        residual = np.empty_like(mic)
        estimate = np.empty_like(mic)

        with self._lock:
            aligned = self._aligned_reference_locked(ref)
            weights = self._weights
            hist = self._history
            mu = float(self.config.adaptation_rate)
            eps = float(self.config.epsilon)

            reference_rms = self._rms(aligned)
            adaptation_enabled = bool(adapt) and (
                reference_rms >= float(self.config.min_reference_rms)
            )

            for i in range(mic.size):
                if hist.size > 1:
                    hist[1:] = hist[:-1]
                hist[0] = aligned[i]

                y = float(np.dot(weights, hist))
                e = float(mic[i]) - y
                estimate[i] = y
                residual[i] = e

                if adaptation_enabled:
                    power = float(np.dot(hist, hist)) + eps
                    weights += np.float32(mu * e / power) * hist

            self._weights = weights
            self._history = hist
            delay = int(self._bulk_delay_samples)

        mic_rms = self._rms(mic)
        residual_rms = self._rms(residual)
        erle = None
        if mic_rms > 0.0 and residual_rms > 0.0:
            erle = 20.0 * math.log10(mic_rms / residual_rms)

        return AECResult(
            audio=np.ascontiguousarray(residual, dtype=np.float32),
            echo_estimate=np.ascontiguousarray(estimate, dtype=np.float32),
            metrics=AECMetrics(
                bulk_delay_samples=delay,
                reference_rms=reference_rms,
                microphone_rms=mic_rms,
                residual_rms=residual_rms,
                erle_db=erle,
                adaptation_enabled=adaptation_enabled,
            ),
        )
