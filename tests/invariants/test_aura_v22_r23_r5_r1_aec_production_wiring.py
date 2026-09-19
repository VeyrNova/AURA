from __future__ import annotations

from pathlib import Path
import hashlib
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAIN = ROOT / "ui" / "main_window.py"
AUTOMIC = ROOT / "voice" / "live_voice_automatic_microphone_runtime_v220.py"
VOICE_ENGINE = ROOT / "voice" / "voice_engine.py"
PIPER = ROOT / "voice" / "text_to_speech.py"
BRIDGE = ROOT / "voice" / "live_voice_aec_integration_v220.py"
PLAYBACK_REF = ROOT / "voice" / "live_voice_playback_reference_v220.py"
AEC = ROOT / "voice" / "live_voice_aec_processor_v220.py"

EXPECTED = {
    MAIN: "d7c5ec869d369f4f079eb472850045f7fed941c76f7a882e85acd1c24125f4c3",
    AUTOMIC: "016d0c06c00eb66c2432eb3081ae2b9c6cb827eb198ed5204f215e10de05b63f",
    VOICE_ENGINE: "f59310277feed54eb6cabfadb63c81d210179928681610b2f50e6c3dd5320469",
    PIPER: "7d2aad6cf204a6674f47f165ffbe3950005c3cc5f83cbf9558e9e9862b907d05",
    BRIDGE: "b75dd7c7eab92862b1602e9a14bb7e015b16c29cc6aec2b072a2e6c064b9a798",
    PLAYBACK_REF: "91a908c43fa4b5090dbd6623948383a9ed0b3c420862b03ee034467167d7598c",
    AEC: "3a9b4374f01c6ecffa42257193156332777e581b1355db357e266d61b529e6d3",
}

def sha(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

for path, expected in EXPECTED.items():
    assert sha(path) == expected, (path, sha(path), expected)

main_src = MAIN.read_text(encoding="utf-8-sig")
assert main_src.count("# AURA_R23_R5_R1_AEC_SETUP") == 1
assert main_src.count("# AURA_R23_R5_R1_AEC_START_REBIND") == 1
assert main_src.count("# AURA_R23_R5_R1_AEC_STOP_RESET") == 1
assert 'runtime._process_audio_frame = _r23_process_audio_frame' in main_src
assert 'controller.cancel("ptt_priority")' in main_src
assert "AutoMic v2.2 integration present but disabled by default" in main_src

auto_src = AUTOMIC.read_text(encoding="utf-8-sig")
on_audio_start = auto_src.index("def _on_audio_frame")
on_audio_tail = auto_src[on_audio_start:on_audio_start + 2200]
assert "self.vad.process" not in on_audio_tail
assert "self.ingress.push_audio" not in on_audio_tail
assert "put_nowait" in on_audio_tail

from voice.live_voice_playback_reference_v220 import PlaybackReferenceBuffer
from voice.live_voice_aec_processor_v220 import AECConfig, BoundedReferenceNLMSEchoCanceller
from voice.live_voice_aec_integration_v220 import (
    LiveVoiceAECIntegrationBridge,
    bind_playback_reference_to_voice_engine,
)

class CompatibleBackend:
    def __init__(self):
        self.callback = None
    def set_playback_reference_callback(self, callback):
        self.callback = callback

class OtherBackend:
    pass

class DummyVoiceEngine:
    def __init__(self):
        self.tts = OtherBackend()
        self.fallback_tts = CompatibleBackend()
        self.cloud_fallback_tts = None

dummy = DummyVoiceEngine()
buf = PlaybackReferenceBuffer(max_seconds=1.0, max_chunks=64, max_bytes=1024 * 1024)
count = bind_playback_reference_to_voice_engine(dummy, buf.push_pcm)
assert count == 1
assert callable(dummy.fallback_tts.callback)

aec = BoundedReferenceNLMSEchoCanceller(
    AECConfig(
        sample_rate=48000,
        filter_length_samples=64,
        max_delay_ms=100.0,
        adaptation_rate=0.55,
        max_block_samples=2048,
    )
)
bridge = LiveVoiceAECIntegrationBridge(
    reference_buffer=buf,
    canceller=aec,
    enabled=False,
    target_sample_rate=48000,
)

near = np.linspace(-0.1, 0.1, 960, dtype=np.float32)
out = bridge.process_near_end(near, 48000)
assert out is near or np.array_equal(out, near)

bridge.enabled = True
out = bridge.process_near_end(near.copy(), 48000)
assert np.array_equal(out, near)

rng = np.random.default_rng(2351)
processed = 0
for _ in range(20):
    far24 = (0.12 * rng.standard_normal(480)).astype(np.float32)
    pcm = np.clip(far24 * 32767.0, -32768, 32767).astype(np.int16).tobytes()
    dummy.fallback_tts.callback(
        pcm,
        sample_rate=24000,
        channels=1,
        dtype="int16",
        generation=11,
    )
    far48 = np.interp(
        np.linspace(0.0, 1.0, 960, endpoint=False),
        np.linspace(0.0, 1.0, 480, endpoint=False),
        far24.astype(np.float64),
    ).astype(np.float32)
    mic = (0.72 * far48).astype(np.float32)
    result = bridge.process_near_end(mic, 48000)
    assert result.shape == mic.shape
    assert np.all(np.isfinite(result))
    if not np.array_equal(result, mic):
        processed += 1

status = bridge.status()
assert processed >= 10, (processed, status)
assert status.reference_blocks >= 10
assert status.processed_blocks >= 10

probe16 = np.ones(320, dtype=np.float32) * 0.02
out16 = bridge.process_near_end(probe16.copy(), 16000)
assert np.array_equal(out16, probe16)

bridge.reset()
reset_status = bridge.status()
assert reset_status.generation is None
assert reset_status.last_reference_sequence == 0

bridge_src = BRIDGE.read_text(encoding="utf-8")
for forbidden in (
    "sounddevice",
    "LiveVoiceSession",
    "LiveVoiceProviderBindings",
    "PiperTTS(",
    "XTTSTTS(",
    "start_listening(",
    "transcribe(",
):
    assert forbidden not in bridge_src, forbidden

print("[PASS] R23-R5-R1 existing-backend capability binding only")
print("[PASS] R23-R5-R1 AEC bridge default OFF and fail-open")
print("[PASS] R23-R5-R1 far-end 24k -> near-end 48k resampling path")
print("[PASS] R23-R5-R1 enabled bridge processes bounded 48k blocks")
print("[PASS] R23-R5-R1 wrong-rate input fails open without changing ingress contract")
print("[PASS] R23-R5-R1 native AutoMic callback source unchanged")
print("[PASS] R23-R5-R1 PTT/default-OFF source contracts retained")
print("[PASS] R23-R5-R1 no device/session/provider/TTS authority in bridge")
