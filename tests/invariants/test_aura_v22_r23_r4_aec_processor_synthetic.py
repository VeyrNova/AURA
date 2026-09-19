from __future__ import annotations

from pathlib import Path
import hashlib
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AEC = ROOT / "voice" / "live_voice_aec_processor_v220.py"
PIPER = ROOT / "voice" / "text_to_speech.py"
PLAYBACK_REF = ROOT / "voice" / "live_voice_playback_reference_v220.py"
AUTOMIC = ROOT / "voice" / "live_voice_automatic_microphone_runtime_v220.py"
VOICE_ENGINE = ROOT / "voice" / "voice_engine.py"

EXPECTED = {
    AEC: "3a9b4374f01c6ecffa42257193156332777e581b1355db357e266d61b529e6d3",
    PIPER: "7d2aad6cf204a6674f47f165ffbe3950005c3cc5f83cbf9558e9e9862b907d05",
    PLAYBACK_REF: "91a908c43fa4b5090dbd6623948383a9ed0b3c420862b03ee034467167d7598c",
    AUTOMIC: "016d0c06c00eb66c2432eb3081ae2b9c6cb827eb198ed5204f215e10de05b63f",
    VOICE_ENGINE: "f59310277feed54eb6cabfadb63c81d210179928681610b2f50e6c3dd5320469",
}

def sha(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

for path, expected in EXPECTED.items():
    assert sha(path) == expected, (path, sha(path), expected)

from voice.live_voice_aec_processor_v220 import AECConfig, BoundedReferenceNLMSEchoCanceller

sr = 8000
cfg = AECConfig(
    sample_rate=sr,
    filter_length_samples=48,
    max_delay_ms=60.0,
    adaptation_rate=0.65,
    max_block_samples=256,
)

rng = np.random.default_rng(22023)
n = sr * 4
raw = rng.standard_normal(n).astype(np.float32)
reference = np.convolve(raw, np.array([0.18, 0.24, 0.18], dtype=np.float32), mode="same").astype(np.float32)
reference *= np.float32(0.18 / max(1e-6, np.std(reference)))

delay = 120
aligned = np.concatenate((np.zeros(delay, dtype=np.float32), reference[:-delay]))
room = np.array([0.76, 0.28, -0.12, 0.06], dtype=np.float32)
echo = np.convolve(aligned, room, mode="full")[:n].astype(np.float32)
microphone = echo.copy()

aec = BoundedReferenceNLMSEchoCanceller(cfg)
estimated = aec.estimate_bulk_delay_samples(reference[: sr * 2], microphone[: sr * 2])
assert abs(estimated - delay) <= 2, (estimated, delay)

outputs = []
for start in range(0, n, 160):
    stop = min(n, start + 160)
    result = aec.process_block(
        microphone[start:stop],
        reference[start:stop],
        adapt=True,
    )
    outputs.append(result.audio)
residual = np.concatenate(outputs)

tail = slice(sr * 3, sr * 4)
echo_rms = float(np.sqrt(np.mean(np.square(microphone[tail], dtype=np.float64))))
res_rms = float(np.sqrt(np.mean(np.square(residual[tail], dtype=np.float64))))
erle_db = 20.0 * np.log10(max(echo_rms, 1e-12) / max(res_rms, 1e-12))
assert erle_db >= 18.0, erle_db

# Double-talk preservation with adaptation frozen: learned echo path should be
# removed while a new near-end user signal remains.
n2 = sr * 2
raw2 = rng.standard_normal(n2).astype(np.float32)
reference2 = np.convolve(raw2, np.array([0.18, 0.24, 0.18], dtype=np.float32), mode="same").astype(np.float32)
reference2 *= np.float32(0.18 / max(1e-6, np.std(reference2)))
aligned2 = np.concatenate((np.zeros(delay, dtype=np.float32), reference2[:-delay]))
echo2 = np.convolve(aligned2, room, mode="full")[:n2].astype(np.float32)
t = np.arange(n2, dtype=np.float32) / np.float32(sr)
near_user = (
    0.10 * np.sin(2.0 * np.pi * 233.0 * t)
    + 0.055 * np.sin(2.0 * np.pi * 377.0 * t)
).astype(np.float32)
mic2 = echo2 + near_user

outs2 = []
for start in range(0, n2, 160):
    stop = min(n2, start + 160)
    result = aec.process_block(
        mic2[start:stop],
        reference2[start:stop],
        adapt=False,
    )
    outs2.append(result.audio)
res2 = np.concatenate(outs2)

warm = slice(sr // 2, n2)
err = res2[warm] - near_user[warm]
signal_rms = float(np.sqrt(np.mean(np.square(near_user[warm], dtype=np.float64))))
error_rms = float(np.sqrt(np.mean(np.square(err, dtype=np.float64))))
preserve_snr_db = 20.0 * np.log10(max(signal_rms, 1e-12) / max(error_rms, 1e-12))
assert preserve_snr_db >= 14.0, preserve_snr_db

# With zero far-end reference and adaptation frozen, near-end must pass through.
# Reset first: this invariant isolates zero-reference behavior from the legitimate
# residual far-end delay/history tail of the previous synthetic double-talk window.
aec.reset()
near_only = (0.08 * np.sin(2.0 * np.pi * 311.0 * np.arange(160, dtype=np.float32) / sr)).astype(np.float32)
pass_result = aec.process_block(
    near_only,
    np.zeros_like(near_only),
    adapt=False,
)
assert np.allclose(pass_result.audio, near_only, atol=2e-4)

# Bounded block contract.
try:
    aec.process_block(
        np.zeros(cfg.max_block_samples + 1, dtype=np.float32),
        np.zeros(cfg.max_block_samples + 1, dtype=np.float32),
    )
    raise AssertionError("oversize block was not rejected")
except ValueError:
    pass

# Ownership/static boundary.
src = AEC.read_text(encoding="utf-8")
for forbidden in (
    "sounddevice",
    "LiveVoiceSession",
    "LiveVoiceProviderBindings",
    "request_barge_in",
    "transcribe(",
    "speak(",
):
    assert forbidden not in src, forbidden

print(f"[PASS] R23-R4 bulk delay estimated within tolerance: {estimated} samples")
print(f"[PASS] R23-R4 synthetic echo attenuation ERLE={erle_db:.2f} dB")
print(f"[PASS] R23-R4 frozen-adaptation double-talk preservation SNR={preserve_snr_db:.2f} dB")
print("[PASS] R23-R4 zero-reference near-end pass-through")
print("[PASS] R23-R4 bounded block contract")
print("[PASS] R23-R4 no device/session/provider/TTS/microphone authority")
