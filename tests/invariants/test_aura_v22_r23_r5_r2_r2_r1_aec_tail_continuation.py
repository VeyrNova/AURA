from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import hashlib
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BRIDGE = ROOT / "voice" / "live_voice_aec_integration_v220.py"
XTTS = ROOT / "voice" / "xtts_tts.py"
AUTOMIC = ROOT / "voice" / "live_voice_automatic_microphone_runtime_v220.py"
PLAYBACK_REF = ROOT / "voice" / "live_voice_playback_reference_v220.py"

def sha(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

assert sha(BRIDGE) == "3f6b65e845da1d4de0334f65ca14de0cd3d7294cc6593aeef709e0307f3a2b4d"
assert sha(XTTS) == "d256a0704d9db6e2c3ec0ef3b124830bbe88978ecaf609ff459df18792671afb"
assert sha(AUTOMIC) == "016d0c06c00eb66c2432eb3081ae2b9c6cb827eb198ed5204f215e10de05b63f"
assert sha(PLAYBACK_REF) == "91a908c43fa4b5090dbd6623948383a9ed0b3c420862b03ee034467167d7598c"

from voice.live_voice_playback_reference_v220 import PlaybackReferenceBuffer
from voice.live_voice_aec_integration_v220 import LiveVoiceAECIntegrationBridge

class FakeCanceller:
    def __init__(self):
        self.calls = []
        self.reset_calls = 0
    def reset(self):
        self.reset_calls += 1
    def process_block(self, near, far, adapt=True):
        self.calls.append({
            "far": np.asarray(far, dtype=np.float32).copy(),
            "adapt": bool(adapt),
        })
        return SimpleNamespace(audio=np.asarray(near, dtype=np.float32) * np.float32(0.5))

buf = PlaybackReferenceBuffer(max_seconds=1.0, max_chunks=16, max_bytes=1024 * 1024)
fake = FakeCanceller()
bridge = LiveVoiceAECIntegrationBridge(
    reference_buffer=buf,
    canceller=fake,
    enabled=True,
    target_sample_rate=48000,
    post_reference_tail_ms=40.0,
)

near = np.ones(960, dtype=np.float32) * 0.08

# No reference ever seen: unchanged fail-open.
out0 = bridge.process_near_end(near.copy(), 48000)
assert np.array_equal(out0, near)
assert bridge.status().fail_open_blocks == 1

# One real 20ms far-end block.
far = np.ones(960, dtype=np.float32) * 0.05
buf.push_pcm(far.tobytes(), sample_rate=48000, channels=1, dtype="float32", generation=7)
out1 = bridge.process_near_end(near.copy(), 48000)
assert not np.array_equal(out1, near)
assert fake.calls[-1]["adapt"] is True

# Then two 20ms zero-reference tail blocks must still process with adaptation frozen.
before = bridge.status()
out2 = bridge.process_near_end(near.copy(), 48000)
after = bridge.status()
assert not np.array_equal(out2, near)
assert after.processed_blocks == before.processed_blocks + 1
assert after.fail_open_blocks == before.fail_open_blocks
assert fake.calls[-1]["adapt"] is False
assert np.max(np.abs(fake.calls[-1]["far"])) == 0.0

out3 = bridge.process_near_end(near.copy(), 48000)
assert not np.array_equal(out3, near)

# Tail expired: fail-open resumes.
before = bridge.status()
out4 = bridge.process_near_end(near.copy(), 48000)
after = bridge.status()
assert np.array_equal(out4, near)
assert after.fail_open_blocks == before.fail_open_blocks + 1

bridge.reset()
out5 = bridge.process_near_end(near.copy(), 48000)
assert np.array_equal(out5, near)

src = BRIDGE.read_text(encoding="utf-8")
assert "AURA_R23_R5_R2_R2_R1_TAIL_CONTINUATION" in src
assert "post_reference_tail_ms: float = 400.0" in src
assert "adapt = False if tail_mode" in src

print("[PASS] no-reference-ever remains fail-open")
print("[PASS] real far-end block processes normally")
print("[PASS] bounded post-reference tail continues AEC")
print("[PASS] tail continuation freezes adaptation")
print("[PASS] fail-open resumes after tail expires")
print("[PASS] reset clears tail continuation")
