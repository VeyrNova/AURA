from __future__ import annotations

from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

XTTS = ROOT / "voice" / "xtts_tts.py"
MAIN = ROOT / "ui" / "main_window.py"
VOICE_ENGINE = ROOT / "voice" / "voice_engine.py"
AUTOMIC = ROOT / "voice" / "live_voice_automatic_microphone_runtime_v220.py"
PLAYBACK_REF = ROOT / "voice" / "live_voice_playback_reference_v220.py"
AEC_BRIDGE = ROOT / "voice" / "live_voice_aec_integration_v220.py"

EXPECTED = {
    XTTS: "d256a0704d9db6e2c3ec0ef3b124830bbe88978ecaf609ff459df18792671afb",
    MAIN: "d7c5ec869d369f4f079eb472850045f7fed941c76f7a882e85acd1c24125f4c3",
    VOICE_ENGINE: "f59310277feed54eb6cabfadb63c81d210179928681610b2f50e6c3dd5320469",
    AUTOMIC: "016d0c06c00eb66c2432eb3081ae2b9c6cb827eb198ed5204f215e10de05b63f",
    PLAYBACK_REF: "91a908c43fa4b5090dbd6623948383a9ed0b3c420862b03ee034467167d7598c",
    AEC_BRIDGE: "b75dd7c7eab92862b1602e9a14bb7e015b16c29cc6aec2b072a2e6c064b9a798",
}

def sha(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

for path, expected in EXPECTED.items():
    assert sha(path) == expected, (path, sha(path), expected)

src = XTTS.read_text(encoding="utf-8-sig")
for marker in ('# AURA_R23_R5_R2_R1_XTTS_REFERENCE_API', '# AURA_R23_R5_R2_R1_XTTS_SPEAK_GENERATION', '# AURA_R23_R5_R2_R1_XTTS_REALTIME_GENERATION', '# AURA_R23_R5_R2_R1_XTTS_STOP_GENERATION', '# AURA_R23_R5_R2_R1_XTTS_PROGRESSIVE_EMIT', '# AURA_R23_R5_R2_R1_XTTS_NATIVE_EMIT', '# AURA_R23_R5_R2_R1_XTTS_PERSISTENT_BIND', '# AURA_R23_R5_R2_R1_XTTS_PERSISTENT_EMIT'):
    assert src.count(marker) == 1, (marker, src.count(marker))

assert "stream.write(payload)" in src
assert "stream.write(item)" in src
assert "stream.write(self._silence)" in src
assert "_aura_ref_cb(payload" in src
assert "_aura_ref_cb(self._silence" not in src

from voice.live_voice_playback_reference_v220 import PlaybackReferenceBuffer
from voice.live_voice_aec_integration_v220 import bind_playback_reference_to_voice_engine
from voice.xtts_tts import XTTSTTS

xtts = object.__new__(XTTSTTS)
xtts._playback_reference_callback = None
xtts._playback_reference_generation = 0

buf = PlaybackReferenceBuffer(max_seconds=1.0, max_chunks=16, max_bytes=1024 * 1024)
assert xtts.set_playback_reference_callback(buf.push_pcm) is True
assert xtts._advance_playback_reference_generation() == 1

payload = (b"\x00\x00\x01\x00") * 128
assert xtts._emit_playback_reference(payload, sample_rate=24000, channels=1, dtype="int16") is True
frames = buf.snapshot()
assert len(frames) == 1, frames
frame = frames[0]
assert frame.payload == payload
assert frame.sample_rate == 24000
assert frame.channels == 1
assert str(frame.dtype).lower() == "int16"
assert frame.generation == 1
assert frame.at_monotonic > 0.0

def broken(*args, **kwargs):
    raise RuntimeError("synthetic callback failure")

xtts.set_playback_reference_callback(broken)
assert xtts._emit_playback_reference(payload, sample_rate=24000, channels=1, dtype="int16") is False

class DummyVoiceEngine:
    def __init__(self, backend):
        self.tts = backend
        self.fallback_tts = None
        self.cloud_fallback_tts = None

xtts2 = object.__new__(XTTSTTS)
xtts2._playback_reference_callback = None
xtts2._playback_reference_generation = 0
buf2 = PlaybackReferenceBuffer(max_seconds=1.0, max_chunks=16, max_bytes=1024 * 1024)
bound = bind_playback_reference_to_voice_engine(DummyVoiceEngine(xtts2), buf2.push_pcm)
assert bound == 1, bound
assert callable(getattr(xtts2, "_playback_reference_callback", None))

for forbidden in ("LiveVoiceSession(", "LiveVoiceProviderBindings(", "start_listening("):
    assert forbidden not in src, forbidden

print("[PASS] XTTS callback API accepts existing PlaybackReferenceBuffer")
print("[PASS] Exact payload metadata/generation captured")
print("[PASS] Callback exceptions fail open")
print("[PASS] Existing R5 capability binding recognizes XTTS")
print("[PASS] Persistent idle silence is not emitted as reference")
print("[PASS] No new session/provider/microphone authority")
