from __future__ import annotations

from pathlib import Path
import ast
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PIPER = ROOT / "voice" / "text_to_speech.py"
MODULE = ROOT / "voice" / "live_voice_playback_reference_v220.py"
VOICE_ENGINE = ROOT / "voice" / "voice_engine.py"
AUTOMIC = ROOT / "voice" / "live_voice_automatic_microphone_runtime_v220.py"
INGRESS = ROOT / "voice" / "live_voice_microphone_ingress_v220.py"
PTT = ROOT / "voice" / "microphone.py"

EXPECTED = {
    PIPER: "7d2aad6cf204a6674f47f165ffbe3950005c3cc5f83cbf9558e9e9862b907d05",
    MODULE: "91a908c43fa4b5090dbd6623948383a9ed0b3c420862b03ee034467167d7598c",
    VOICE_ENGINE: "f59310277feed54eb6cabfadb63c81d210179928681610b2f50e6c3dd5320469",
    AUTOMIC: "016d0c06c00eb66c2432eb3081ae2b9c6cb827eb198ed5204f215e10de05b63f",
    INGRESS: "81cb863f21e26a04330dce60d7ea027b625e2778b3c56bf23f6656d73e08dc17",
    PTT: "c4a3d811de7eee7b56599c509313316a6c3f3d845d36d1381054c075ff0ea27f",
}

def sha(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

for path, expected in EXPECTED.items():
    assert sha(path) == expected, (path, sha(path), expected)

src = PIPER.read_text(encoding="utf-8-sig")
tree = ast.parse(src)
classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
assert "PiperTTS" in classes
cls = classes["PiperTTS"]
methods = {
    n.name: n
    for n in cls.body
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
}

for name in (
    "set_playback_reference_callback",
    "_advance_playback_reference_generation",
    "_emit_playback_reference",
    "_ensure_stream",
    "_stream_text",
    "_stream_progressive_text",
    "begin_realtime_pipeline",
    "speak",
    "stop",
):
    assert name in methods, name

assert src.count("# AURA_R23_R3_PLAYBACK_REFERENCE_STATE") == 1
assert src.count("# AURA_R23_R3_PLAYBACK_REFERENCE_METHODS") == 1
assert src.count("# AURA_R23_R3_PLAYBACK_REFERENCE_SPEC") == 1
assert src.count("# AURA_R23_R3_PLAYBACK_REFERENCE_EMIT") == 2
assert src.count("# AURA_R23_R3_PLAYBACK_REFERENCE_BEGIN") == 1
assert src.count("# AURA_R23_R3_PLAYBACK_REFERENCE_SPEAK") == 1
assert src.count("# AURA_R23_R3_PLAYBACK_REFERENCE_STOP") == 1
assert src.count("self._emit_playback_reference(payload)") == 2
assert src.count("stream.write(payload)") == 2

from voice.live_voice_playback_reference_v220 import PlaybackReferenceBuffer
from voice.text_to_speech import PiperTTS

clock = lambda: 1.0
buf = PlaybackReferenceBuffer(max_seconds=0.050, max_chunks=3, max_bytes=2048, clock=clock)

payload = (b"\x01\x02" * 120)
frame = buf.push_pcm(
    payload,
    sample_rate=24000,
    channels=1,
    dtype="int16",
    generation=7,
)
assert frame is not None
assert frame.payload == payload
assert frame.sample_rate == 24000
assert frame.channels == 1
assert frame.dtype == "int16"
assert frame.generation == 7

piper = object.__new__(PiperTTS)
piper._playback_reference_callback = buf.push_pcm
piper._playback_reference_generation = 8
piper._playback_reference_last_spec = (24000, 1, "int16")
probe = b"\x10\x20" * 240
piper._emit_playback_reference(probe)
snap = buf.snapshot(generation=8)
assert len(snap) == 1
assert snap[0].payload == probe
assert snap[0].sample_rate == 24000
assert snap[0].channels == 1
assert snap[0].dtype == "int16"

piper._playback_reference_generation = 9
piper._emit_playback_reference(b"\x30\x40" * 120)
snap9 = buf.snapshot()
assert snap9 and all(x.generation == 9 for x in snap9)

for _ in range(8):
    buf.push_pcm(
        b"\x55\x66" * 240,
        sample_rate=24000,
        channels=1,
        dtype="int16",
        generation=9,
    )
st = buf.status()
assert st.frame_count <= 3
assert st.buffered_bytes <= 2048
assert st.buffered_seconds <= 0.0500001

def boom(*args, **kwargs):
    raise RuntimeError("probe")

piper._playback_reference_callback = boom
piper._emit_playback_reference(b"\x01\x00" * 20)

before = piper._playback_reference_generation
after = piper._advance_playback_reference_generation()
assert after == before + 1

print("[PASS] R23-R3 exact Piper PCM payload callback installed")
print("[PASS] R23-R3 sample-rate/channels/dtype/generation metadata preserved")
print("[PASS] R23-R3 playback reference buffer bounded by time/chunks/bytes")
print("[PASS] R23-R3 generation change invalidates stale far-end reference")
print("[PASS] R23-R3 callback failures are fail-open for playback")
print("[PASS] R23-R3 VoiceEngine/AutoMic/Ingress/PTT sources unchanged")
print("[PASS] R23-R3 no microphone/speaker/device opened by invariant")
