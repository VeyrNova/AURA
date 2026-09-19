from __future__ import annotations

import inspect
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import voice.microphone as mic
import voice.xtts_tts as xtts

candidate_classes = [
    obj for obj in vars(mic).values()
    if isinstance(obj, type) and hasattr(obj, "choose_input_device")
]
assert candidate_classes, "microphone choose_input_device authority missing"

# Behavioral stale-index test instead of brittle source-variable matching.
# Requested index 999 no longer exists; Windows/default index 1 must win.
authority = candidate_classes[0]
fake_devices = [
    {
        "name": "AURA v0867 test microphone 0",
        "max_input_channels": 1,
        "default_samplerate": 44100,
    },
    {
        "name": "AURA v0867 test microphone 1",
        "max_input_channels": 2,
        "default_samplerate": 48000,
    },
]
selected = authority.choose_input_device(fake_devices, 1, 999)
assert selected is not None, "stale requested index produced no fallback"
assert getattr(selected, "index", None) == 1, selected

filter_type = getattr(mic, "_AURAV0867StaleMicWarningDedupFilter")
f = filter_type()
filter_type._seen.clear()

r1 = logging.LogRecord(
    "aura.voice.microphone",
    logging.WARNING,
    __file__,
    1,
    "P0.8.5.4.7.4 requested microphone index stale index=%r; fallback=%r",
    (999, 2),
    None,
)
r2 = logging.LogRecord(
    "aura.voice.microphone",
    logging.WARNING,
    __file__,
    2,
    "P0.8.5.4.7.4 requested microphone index stale index=%r; fallback=%r",
    (999, 2),
    None,
)
r3 = logging.LogRecord(
    "aura.voice.microphone",
    logging.WARNING,
    __file__,
    3,
    "another microphone warning",
    (),
    None,
)
assert f.filter(r1) is True
assert f.filter(r2) is False
assert f.filter(r3) is True

assert hasattr(xtts, "_AURA_V0867_ORIGINAL_XTTS_WARMUP")
saved_original = xtts._AURA_V0867_ORIGINAL_XTTS_WARMUP
calls = []

class DummyXTTS(xtts.XTTSTTS):
    _aura_v0867_warmup_ready = False

    @classmethod
    def shared_model_loaded(cls):
        return True

try:
    xtts._AURA_V0867_ORIGINAL_XTTS_WARMUP = lambda self: calls.append("warm")
    obj = DummyXTTS.__new__(DummyXTTS)
    obj.warmup()
    obj.warmup()
    assert calls == ["warm"], calls
finally:
    xtts._AURA_V0867_ORIGINAL_XTTS_WARMUP = saved_original

print("[PASS] v0.8.6.7 runtime/performance invariant")
raise SystemExit(0)
