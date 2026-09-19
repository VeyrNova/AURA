
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Any
import numpy as np

@dataclass(frozen=True)
class MicrophonePreconditioningResult:
    audio: np.ndarray
    status: str
    applied_gain: float
    trimmed_frames: int
    raw_peak: float
    raw_speech_rms: float
    noise_rms: float
    snr_db: float | None
    output_peak: float
    output_speech_rms: float
    clipping_ratio: float

class ProviderNeutralMicrophonePreconditioner:
    def __init__(
        self,
        *,
        target_speech_rms: float = 0.040,
        max_gain: float = 12.0,
        peak_target: float = 0.45,
        clip_limit: float = 0.95,
        min_raw_peak: float = 0.005,
        min_speech_rms: float = 0.001,
        min_snr_db: float = 10.0,
    ) -> None:
        if not (0.0 < target_speech_rms < 1.0):
            raise ValueError("bad target_speech_rms")
        if not (1.0 <= max_gain <= 24.0):
            raise ValueError("bad max_gain")
        if not (0.0 < peak_target <= clip_limit <= 1.0):
            raise ValueError("bad peak/clip limits")
        self.target_speech_rms = float(target_speech_rms)
        self.max_gain = float(max_gain)
        self.peak_target = float(peak_target)
        self.clip_limit = float(clip_limit)
        self.min_raw_peak = float(min_raw_peak)
        self.min_speech_rms = float(min_speech_rms)
        self.min_snr_db = float(min_snr_db)

    @staticmethod
    def _mono(audio: Any) -> np.ndarray:
        a = np.asarray(audio, dtype=np.float32)
        if a.ndim == 0:
            a = a.reshape(1)
        elif a.ndim == 1:
            pass
        elif a.ndim == 2:
            a = np.mean(a, axis=1, dtype=np.float32)
        else:
            raise ValueError("audio must be mono or frames/channels")
        return np.ascontiguousarray(a.reshape(-1), dtype=np.float32)

    @staticmethod
    def _rms(a: np.ndarray) -> float:
        if not a.size:
            return 0.0
        return float(np.sqrt(np.mean(np.square(a, dtype=np.float64))))

    def process(
        self,
        audio: Any,
        *,
        sample_rate: int,
        known_leading_silence_seconds: float = 0.0,
    ) -> MicrophonePreconditioningResult:
        if int(sample_rate) <= 0:
            raise ValueError("sample_rate must be positive")
        if known_leading_silence_seconds < 0:
            raise ValueError("negative leading silence")

        src = self._mono(audio)
        if not src.size:
            return MicrophonePreconditioningResult(
                src.copy(),"BYPASS_EMPTY",1.0,0,0.0,0.0,0.0,None,0.0,0.0,0.0
            )

        baseline_frames = min(
            src.size,
            int(round(float(known_leading_silence_seconds) * int(sample_rate))),
        )
        baseline = src[:baseline_frames] if baseline_frames else src[:0]
        speech = src[baseline_frames:] if baseline_frames else src

        raw_peak = float(np.max(np.abs(src)))
        speech_rms = self._rms(speech)
        noise_rms = self._rms(baseline)
        snr_db = (
            20.0 * math.log10(max(speech_rms,1e-9)/max(noise_rms,1e-9))
            if baseline_frames else None
        )

        eligible = (
            speech.size > 0
            and raw_peak >= self.min_raw_peak
            and speech_rms >= self.min_speech_rms
            and (snr_db is None or snr_db >= self.min_snr_db)
        )

        if not eligible:
            out = src.copy()
            return MicrophonePreconditioningResult(
                out,"BYPASS_SIGNAL_NOT_ELIGIBLE",1.0,0,
                raw_peak,speech_rms,noise_rms,snr_db,
                raw_peak,speech_rms,
                float(np.mean(np.abs(out) >= self.clip_limit)),
            )

        gain = max(
            1.0,
            min(
                self.max_gain,
                self.target_speech_rms / max(speech_rms,1e-9),
                self.peak_target / max(raw_peak,1e-9),
            ),
        )
        trimmed = src[baseline_frames:] if baseline_frames else src
        out = np.clip(
            trimmed * gain,
            -self.clip_limit,
            self.clip_limit,
        ).astype(np.float32, copy=False)

        output_peak = float(np.max(np.abs(out))) if out.size else 0.0
        output_rms = self._rms(out)
        clipping_ratio = (
            float(np.mean(np.abs(out) >= self.clip_limit))
            if out.size else 0.0
        )

        if gain > 1.0 and baseline_frames:
            status = "APPLIED_GAIN_AND_TRIM"
        elif gain > 1.0:
            status = "APPLIED_GAIN"
        elif baseline_frames:
            status = "APPLIED_TRIM_ONLY"
        else:
            status = "PASS_THROUGH_ELIGIBLE"

        return MicrophonePreconditioningResult(
            np.ascontiguousarray(out,dtype=np.float32),
            status,float(gain),int(baseline_frames),
            raw_peak,speech_rms,noise_rms,snr_db,
            output_peak,output_rms,clipping_ratio,
        )
