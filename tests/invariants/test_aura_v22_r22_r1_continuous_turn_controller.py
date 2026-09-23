from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import inspect
import ast
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.live_voice_continuous_turn_controller_v220 import ContinuousVoiceTurnController
import voice.live_voice_turn_detection_v220 as td

READY_FIELD = 'action'
READY_VALUE = 'COMMIT'


def make_detector():
    Detector = td.DeterministicTurnEndDetector
    try:
        return Detector()
    except TypeError:
        pass

    sig = inspect.signature(Detector)
    config_cls = None
    for name, obj in vars(td).items():
        if not inspect.isclass(obj):
            continue
        try:
            params = inspect.signature(obj).parameters
        except Exception:
            continue
        if "silence_timeout_ms" in params and "min_speech_ms" in params:
            config_cls = obj
            break
    assert config_cls is not None, sig
    cfg = config_cls(silence_timeout_ms=420, min_speech_ms=120)
    if "config" in sig.parameters:
        return Detector(config=cfg)
    return Detector(cfg)


def is_ready(decision):
    return getattr(decision, READY_FIELD, None) == READY_VALUE


@dataclass
class Start:
    at_ms: float
    sequence: int = 1


@dataclass
class Chunk:
    at_ms: float
    audio: object
    probability: float = 1.0
    sequence: int = 1


@dataclass
class End:
    at_ms: float
    sequence: int = 1


# 1) 419 ms must hold; 420 ms must finalize exactly once.
out = []
c = ContinuousVoiceTurnController(
    detector=make_detector(),
    is_ready=is_ready,
    on_finalized_audio=out.append,
    source_sample_rate=16000,
    target_sample_rate=16000,
)
c.on_speech_started(Start(0))
for t in (20, 60, 100, 140, 180):
    c.on_audio_chunk(Chunk(t, np.ones(640, dtype=np.float32) * 0.02))
c.on_speech_ended(End(200))
assert c.on_audio_chunk(Chunk(619, np.zeros(320, dtype=np.float32))) is False
assert len(out) == 0
assert c.on_audio_chunk(Chunk(620, np.zeros(320, dtype=np.float32))) is True
assert len(out) == 1
assert out[0].dtype == np.float32
assert out[0].size == 3200

# No duplicate finalization after completion.
for t in (640, 700, 1000):
    assert c.on_audio_chunk(Chunk(t, np.zeros(320, dtype=np.float32))) is False
assert len(out) == 1

# 2) False-end recovery stays on the same ephemeral utterance.
out2 = []
c2 = ContinuousVoiceTurnController(
    detector=make_detector(),
    is_ready=is_ready,
    on_finalized_audio=out2.append,
    source_sample_rate=16000,
    target_sample_rate=16000,
)
c2.on_speech_started(Start(0, 1))
c2.on_audio_chunk(Chunk(80, np.ones(800, dtype=np.float32) * 0.02))
c2.on_speech_ended(End(200, 2))
turn_before = c2.status().turn_id
c2.on_audio_chunk(Chunk(400, np.zeros(320, dtype=np.float32)))
c2.on_speech_started(Start(410, 3))
assert c2.status().turn_id == turn_before
c2.on_audio_chunk(Chunk(500, np.ones(800, dtype=np.float32) * 0.03))
c2.on_speech_ended(End(600, 4))
assert c2.on_audio_chunk(Chunk(1020, np.zeros(320, dtype=np.float32))) is True
assert len(out2) == 1
assert out2[0].size == 1600

# 3) PTT-style cancel makes pending continuous audio stale.
out3 = []
c3 = ContinuousVoiceTurnController(
    detector=make_detector(),
    is_ready=is_ready,
    on_finalized_audio=out3.append,
    source_sample_rate=16000,
    target_sample_rate=16000,
)
c3.on_speech_started(Start(0))
c3.on_audio_chunk(Chunk(100, np.ones(1600, dtype=np.float32) * 0.02))
c3.on_speech_ended(End(200))
c3.cancel("ptt_priority")
assert c3.status().active is False
assert c3.on_audio_chunk(Chunk(1000, np.zeros(320, dtype=np.float32))) is False
assert out3 == []

# 4) AutoMic 48k -> existing STT/PTT 16k normalization.
out4 = []
c4 = ContinuousVoiceTurnController(
    detector=make_detector(),
    is_ready=is_ready,
    on_finalized_audio=out4.append,
    source_sample_rate=48000,
    target_sample_rate=16000,
)
c4.on_speech_started(Start(0))
c4.on_audio_chunk(Chunk(100, np.ones(4800, dtype=np.float32) * 0.02))
c4.on_audio_chunk(Chunk(180, np.ones(4800, dtype=np.float32) * 0.02))
c4.on_speech_ended(End(200))
assert c4.on_audio_chunk(Chunk(620, np.zeros(960, dtype=np.float32))) is True
assert len(out4) == 1
assert 3190 <= out4[0].size <= 3210, out4[0].size

# 5) Static ownership boundary.
target = ROOT / "voice" / "live_voice_continuous_turn_controller_v220.py"
source = target.read_text(encoding="utf-8-sig")
tree = ast.parse(source)
imports = []
calls = []
for n in ast.walk(tree):
    if isinstance(n, ast.Import):
        imports.extend(a.name for a in n.names)
    elif isinstance(n, ast.ImportFrom):
        imports.append(n.module or "")
    elif isinstance(n, ast.Call):
        f = n.func
        if isinstance(f, ast.Name):
            calls.append(f.id)
        elif isinstance(f, ast.Attribute):
            calls.append(f.attr)

bad_import_tokens = (
    "sounddevice",
    "live_voice_session_v220",
    "live_voice_bindings_v220",
    "memory",
    "tts",
)
assert not any(any(tok in item.lower() for tok in bad_import_tokens) for item in imports), imports
assert "request_barge_in" not in calls
assert "transcribe" not in calls

print("[PASS] R22-R1 exact 419/420ms endpoint behavior")
print("[PASS] R22-R1 finalized audio exactly once")
print("[PASS] R22-R1 false-end recovery preserves same ephemeral turn")
print("[PASS] R22-R1 PTT-style cancel rejects stale pending audio")
print("[PASS] R22-R1 48k->16k resampling")
print("[PASS] R22-R1 owns no session/provider/STT/TTS/memory/microphone authority")
