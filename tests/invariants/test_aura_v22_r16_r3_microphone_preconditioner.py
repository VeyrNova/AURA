
from __future__ import annotations
import ast, importlib.util, math, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "voice" / "live_voice_microphone_preconditioner_v220.py"

source = TARGET.read_text(encoding="utf-8")
tree = ast.parse(source, filename=str(TARGET))
forbidden = {"socket","subprocess","requests","httpx","urllib","sounddevice","pyaudio","winsound"}
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            assert alias.name.split(".")[0] not in forbidden
    elif isinstance(node, ast.ImportFrom) and node.module:
        assert node.module.split(".")[0] not in forbidden

spec = importlib.util.spec_from_file_location("aura_r16_r3_pre", str(TARGET))
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
pre = m.ProviderNeutralMicrophonePreconditioner()

sr = 16000
baseline = np.full(int(0.8*sr), 0.0001, dtype=np.float32)
t = np.arange(int(1.2*sr), dtype=np.float32) / sr
# Deliberately above the 0.005 eligibility boundary: float32 must not turn
# a boundary-value test into a false negative.
speech = (0.006*np.sin(2*math.pi*220*t)).astype(np.float32)
r = pre.process(np.concatenate([baseline,speech]), sample_rate=sr, known_leading_silence_seconds=0.8)
assert r.status == "APPLIED_GAIN_AND_TRIM"
assert 1.0 < r.applied_gain <= 12.0
assert r.trimmed_frames == int(0.8*sr)
assert 0.0 < r.output_peak <= 0.45 + 1e-6
assert r.clipping_ratio == 0.0

silence = np.zeros(sr, dtype=np.float32)
r2 = pre.process(silence, sample_rate=sr, known_leading_silence_seconds=0.8)
assert r2.status == "BYPASS_SIGNAL_NOT_ELIGIBLE"
assert r2.applied_gain == 1.0

rng = np.random.default_rng(220)
noise = rng.normal(0.0,0.003,int(1.8*sr)).astype(np.float32)
r3 = pre.process(noise, sample_rate=sr, known_leading_silence_seconds=0.8)
assert r3.status == "BYPASS_SIGNAL_NOT_ELIGIBLE"
assert r3.applied_gain == 1.0

print("[PASS] AURA v2.2 R16-R3 bounded microphone preconditioner invariant")
print("[PASS] provider-neutral / no device, network or process authority")
print("[PASS] gain bounded <= 12x, peak target <= 0.45")
print("[PASS] silence and poor-SNR input fail safe")
