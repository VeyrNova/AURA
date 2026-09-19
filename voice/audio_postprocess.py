"""Small PCM WAV finishing helpers for AURA speech.

No DSP dependency is required: XTTS/Piper output is normally 16-bit PCM WAV.
The finisher removes a late isolated tail after a silence gap, applies a very
short fade at the true end, then adds a tiny silent safety pad. This prevents
speaker/driver clicks without altering the body of the utterance.
"""
from __future__ import annotations

import array
import logging
import math
import sys
import wave
from pathlib import Path

logger = logging.getLogger("aura.voice.audio")


def _frame_peaks(samples: array.array, channels: int) -> list[int]:
    channels = max(1, int(channels))
    if channels == 1:
        return [abs(int(v)) for v in samples]
    return [
        max(abs(int(samples[i + c])) for c in range(channels))
        for i in range(0, len(samples) - channels + 1, channels)
    ]


def polish_wav_tail(
    wav_path: Path | str,
    *,
    fade_ms: float = 32.0,
    safety_silence_ms: float = 36.0,
    silence_gap_ms: float = 42.0,
    scan_tail_ms: float = 500.0,
    silence_threshold: int = 120,
) -> bool:
    """Finish the tail of a 16-bit PCM WAV in-place.

    Returns True when the file was rewritten. Unsupported WAV encodings are
    left untouched so speech never fails merely because polishing is skipped.
    """
    path = Path(wav_path)
    try:
        with wave.open(str(path), "rb") as src:
            params = src.getparams()
            frames = src.readframes(params.nframes)
    except Exception:
        logger.debug("Audio tail polish skipped: unreadable WAV %s", path, exc_info=True)
        return False

    if params.sampwidth != 2 or params.nchannels < 1 or params.framerate <= 0 or not frames:
        return False

    samples = array.array("h")
    samples.frombytes(frames)
    if sys.byteorder != "little":
        samples.byteswap()
    channels = int(params.nchannels)
    peaks = _frame_peaks(samples, channels)
    frame_count = len(peaks)
    if frame_count < 8:
        return False

    rate = int(params.framerate)
    gap_frames = max(1, int(rate * float(silence_gap_ms) / 1000.0))
    scan_frames = max(gap_frames, int(rate * float(scan_tail_ms) / 1000.0))
    search_start = max(0, frame_count - scan_frames)

    # If XTTS emits a tiny pop/grunt *after* a genuine silence gap, cut at the
    # start of that gap. Ordinary trailing silence is trimmed by the same rule.
    cut_frame = frame_count
    run = 0
    for idx in range(frame_count - 1, search_start - 1, -1):
        if peaks[idx] <= int(silence_threshold):
            run += 1
            if run >= gap_frames:
                gap_start = idx
                audible_after = any(p > int(silence_threshold) for p in peaks[idx + gap_frames :])
                trailing_silence = (idx + gap_frames) >= frame_count - 2
                if audible_after or trailing_silence or frame_count - gap_start > gap_frames:
                    cut_frame = gap_start
                    break
        else:
            run = 0

    # Avoid pathological over-trimming. Keep at least the first 120 ms.
    min_frames = min(frame_count, max(1, int(rate * 0.12)))
    cut_frame = max(min_frames, min(cut_frame, frame_count))

    fade_frames = min(cut_frame, max(1, int(rate * float(fade_ms) / 1000.0)))
    start_fade = cut_frame - fade_frames
    for frame_idx in range(start_fade, cut_frame):
        # Equal-power-ish cosine taper, ending at zero.
        pos = (frame_idx - start_fade + 1) / float(fade_frames)
        gain = max(0.0, 0.5 * (1.0 + math.cos(math.pi * pos)))
        base = frame_idx * channels
        for c in range(channels):
            samples[base + c] = int(samples[base + c] * gain)

    kept = samples[: cut_frame * channels]
    silence_frames = max(0, int(rate * float(safety_silence_ms) / 1000.0))
    if silence_frames:
        kept.extend([0] * (silence_frames * channels))

    if sys.byteorder != "little":
        kept.byteswap()
    try:
        with wave.open(str(path), "wb") as dst:
            dst.setparams(params)
            dst.writeframes(kept.tobytes())
        logger.debug(
            "Audio tail polished path=%s frames=%d->%d fade=%.0fms pad=%.0fms",
            path.name, frame_count, cut_frame + silence_frames, fade_ms, safety_silence_ms,
        )
        return True
    except Exception:
        logger.debug("Audio tail polish write failed: %s", path, exc_info=True)
        return False
