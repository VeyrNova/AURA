
from __future__ import annotations

from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.live_voice_session_v220 import LiveVoiceSession, VoiceState
from voice.live_voice_streaming_v220 import LiveVoiceStreamingPipeline


class CountingCanonicalStream:
    def __init__(self):
        self.calls = []
        self.yields = 0

    def __call__(self, text, session_id, turn_id, cancellation):
        self.calls.append(
            {
                "text": text,
                "session_id": session_id,
                "turn_id": turn_id,
                "cancelled_at_open": cancellation.cancelled,
            }
        )

        chunks = ["Ré", "ponse ", "streamée ", "AURA"]
        def generator():
            for chunk in chunks:
                if cancellation.cancelled:
                    return
                self.yields += 1
                yield chunk
        return generator()


events = []
canonical = CountingCanonicalStream()
session = LiveVoiceSession(
    session_id="TEST-R5",
    event_sink=events.append,
)
pipe = LiveVoiceStreamingPipeline(
    session=session,
    canonical_streaming_ingress=canonical,
    stt_capacity=2,
    llm_capacity=2,
    tts_capacity=1,
)

session.start()
assert session.state is VoiceState.LISTENING

# ------------------------------------------------------------------
# STT bounded backpressure: third partial is rejected, never silently dropped.
# ------------------------------------------------------------------
turn1 = pipe.begin_user_turn()
assert session.state is VoiceState.TRANSCRIBING

a = pipe.push_stt_partial(turn1, "un")
b = pipe.push_stt_partial(turn1, "deux")
c = pipe.push_stt_partial(turn1, "trois")
assert a.accepted and b.accepted
assert c.accepted is False
assert c.reason == "stt_backpressure"
assert len(pipe.stt_queue) == 2
assert pipe.stt_queue.high_watermark == 2
assert pipe.stt_queue.rejected_puts == 1

first_partial = pipe.consume_stt_partial(turn1)
assert first_partial is not None and first_partial.text == "un"
assert len(pipe.stt_queue) == 1

d = pipe.push_stt_partial(turn1, "trois")
assert d.accepted is True
assert len(pipe.stt_queue) == 2

# Final transcript opens canonical streaming ingress exactly once.
final = pipe.commit_stt_final(turn1, "Question streaming")
assert final.accepted is True
assert final.reason == "canonical_stream_opened"
assert session.state is VoiceState.THINKING
assert len(canonical.calls) == 1
assert canonical.calls[0]["text"] == "Question streaming"
assert canonical.calls[0]["turn_id"] == turn1
assert canonical.calls[0]["cancelled_at_open"] is False

# ------------------------------------------------------------------
# LLM bounded queue: when full, upstream generator is NOT advanced.
# ------------------------------------------------------------------
p1 = pipe.pump_llm_once(turn1)
p2 = pipe.pump_llm_once(turn1)
assert p1.accepted and p2.accepted
assert len(pipe.llm_queue) == 2
assert canonical.yields == 2

p3 = pipe.pump_llm_once(turn1)
assert p3.accepted is False
assert p3.reason == "llm_backpressure"
assert canonical.yields == 2, "upstream advanced despite llm backpressure"

# ------------------------------------------------------------------
# TTS downstream backpressure: do not pop LLM head if TTS queue is full.
# ------------------------------------------------------------------
x1 = pipe.promote_llm_to_tts(turn1)
assert x1.accepted is True
assert session.state is VoiceState.SPEAKING
assert len(pipe.llm_queue) == 1
assert len(pipe.tts_queue) == 1

llm_before = pipe.llm_queue.snapshot()
x2 = pipe.promote_llm_to_tts(turn1)
assert x2.accepted is False
assert x2.reason == "tts_backpressure"
assert pipe.llm_queue.snapshot() == llm_before
assert len(pipe.tts_queue) == 1

tts1 = pipe.consume_tts_chunk(turn1)
assert tts1 is not None
assert tts1.text == "Ré"
assert pipe.mark_playback_started(turn1).accepted is True
assert len(pipe.tts_queue) == 0

x3 = pipe.promote_llm_to_tts(turn1)
assert x3.accepted is True
tts2 = pipe.consume_tts_chunk(turn1)
assert tts2 is not None
assert tts2.text == "ponse "

# Upstream can now continue because queue space exists.
p3b = pipe.pump_llm_once(turn1)
assert p3b.accepted is True
assert canonical.yields == 3

# ------------------------------------------------------------------
# Build pending streamed work, then barge in.
# All turn buffers/iterator state must be cleared and stale pump rejected.
# ------------------------------------------------------------------
assert pipe.promote_llm_to_tts(turn1).accepted is True
assert len(pipe.tts_queue) == 1

# One more LLM chunk can be pulled while TTS is full.
p4 = pipe.pump_llm_once(turn1)
assert p4.accepted is True
assert canonical.yields == 4
assert len(pipe.llm_queue) >= 1

token1 = session.active_turn.cancellation
barge = pipe.request_barge_in(reason="user_speech")
assert barge.accepted is True
assert barge.turn_id == turn1
assert token1.cancelled is True
assert session.state is VoiceState.LISTENING
assert session.active_turn is None
assert len(pipe.stt_queue) == 0
assert len(pipe.llm_queue) == 0
assert len(pipe.tts_queue) == 0

stale_pump = pipe.pump_llm_once(turn1)
assert stale_pump.accepted is False
assert stale_pump.reason == "stale_llm_turn"
assert canonical.yields == 4

# ------------------------------------------------------------------
# New turn after cancellation must be independent and complete normally.
# ------------------------------------------------------------------
turn2 = pipe.begin_user_turn()
assert turn2 != turn1
pipe.push_stt_partial(turn2, "nouveau")
pipe.consume_stt_partial(turn2)
opened2 = pipe.commit_stt_final(turn2, "Nouvelle question")
assert opened2.accepted is True
assert len(canonical.calls) == 2

# Pump/promote/consume until EOF and drained.
seen_text = []
while True:
    pumped = pipe.pump_llm_once(turn2)
    if pumped.reason == "llm_backpressure":
        promoted = pipe.promote_llm_to_tts(turn2)
        assert promoted.accepted is True
        item = pipe.consume_tts_chunk(turn2)
        assert item is not None
        seen_text.append(item.text)
        continue
    if pumped.reason == "llm_stream_eof":
        break
    assert pumped.accepted is True

    # Keep downstream moving to avoid intentional backpressure deadlock.
    if len(pipe.llm_queue):
        if len(pipe.tts_queue) == 0:
            promoted = pipe.promote_llm_to_tts(turn2)
            assert promoted.accepted is True
        if len(pipe.tts_queue):
            item = pipe.consume_tts_chunk(turn2)
            assert item is not None
            seen_text.append(item.text)

# Drain leftovers.
while len(pipe.llm_queue):
    if len(pipe.tts_queue) == 0:
        promoted = pipe.promote_llm_to_tts(turn2)
        assert promoted.accepted is True
    item = pipe.consume_tts_chunk(turn2)
    assert item is not None
    seen_text.append(item.text)

while len(pipe.tts_queue):
    item = pipe.consume_tts_chunk(turn2)
    assert item is not None
    seen_text.append(item.text)

assert pipe.mark_playback_started(turn2).accepted is True
done = pipe.complete_if_drained(turn2)
assert done.accepted is True
assert done.reason == "streaming_turn_completed"
assert session.state is VoiceState.LISTENING
assert session.active_turn is None
assert "".join(seen_text) == "Réponse streamée AURA"

# Canonical ingress called exactly once per committed user turn.
assert len(canonical.calls) == 2

# ------------------------------------------------------------------
# Underlying authority evidence remains monotonic and includes barge-in.
# ------------------------------------------------------------------
seqs = [e.sequence for e in session.events]
assert seqs == sorted(seqs)
assert len(seqs) == len(set(seqs))

event_names = [e.event for e in session.events]
for required in (
    "stt_partial",
    "stt_final",
    "turn_committed",
    "llm_first_token",
    "tts_first_chunk",
    "playback_started",
    "barge_in_detected",
    "playback_cancelled",
    "turn_cancelled",
):
    assert required in event_names, required

# ------------------------------------------------------------------
# Static guard: R5 may own bounded queues/iterators only, not a second
# voice state machine, provider I/O stack or session authority.
# ------------------------------------------------------------------
module_path = ROOT / "voice" / "live_voice_streaming_v220.py"
source = module_path.read_text(encoding="utf-8", errors="ignore")
tree = ast.parse(source, filename=str(module_path))

forbidden_import_roots = {
    "sounddevice",
    "pyaudio",
    "requests",
    "httpx",
    "whisper",
    "xtts",
    "elevenlabs",
    "subprocess",
    "socket",
}
imports = set()
class_names = set()
self_assignments = set()

for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.add(alias.name.split(".", 1)[0].casefold())
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            imports.add(node.module.split(".", 1)[0].casefold())
    elif isinstance(node, ast.ClassDef):
        class_names.add(node.name)
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                self_assignments.add(target.attr)

assert not (imports & forbidden_import_roots), sorted(imports & forbidden_import_roots)
assert "LiveVoiceSession" not in class_names
for forbidden_attr in (
    "state",
    "_state",
    "_active_turn",
    "_turn_counter",
    "_sequence",
    "cancellation",
):
    assert forbidden_attr not in self_assignments, forbidden_attr

session.stop()
assert session.state is VoiceState.STOPPED

print("[PASS] AURA v2.2 R5 bounded streaming/backpressure invariant")
print("[PASS] STT queue is bounded and rejects overflow explicitly")
print("[PASS] LLM queue backpressure does not advance upstream generator")
print("[PASS] TTS queue backpressure does not pop upstream LLM data")
print("[PASS] canonical streaming ingress opens exactly once per committed turn")
print("[PASS] barge-in cancels turn and clears STT/LLM/TTS buffers")
print("[PASS] stale streamed work cannot resume after interruption")
print("[PASS] new post-barge-in turn is independent and completes normally")
print("[PASS] one LiveVoiceSession authority remains intact")
print("[PASS] no real microphone/audio/network/model/provider I/O")
