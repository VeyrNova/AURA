
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.live_voice_session_v220 import (
    CancellationToken,
    InvalidVoiceTransition,
    LiveVoiceSession,
    StaleVoiceTurn,
    VoiceState,
)

class FakeClock:
    def __init__(self):
        self.value = 1_000_000
    def __call__(self):
        self.value += 1_000
        return self.value

events = []
clock = FakeClock()
session = LiveVoiceSession(
    session_id="TEST-VOICE-R3",
    clock_ns=clock,
    event_sink=events.append,
    max_event_history=128,
)

assert session.state is VoiceState.STOPPED
assert session.active_turn is None
assert session.events == ()

session.start()
assert session.state is VoiceState.LISTENING
assert session.is_running is True

turn1 = session.speech_started()
assert turn1 == "TEST-VOICE-R3:turn:1"
assert session.state is VoiceState.TRANSCRIBING
assert session.active_turn is not None
assert session.active_turn.turn_id == turn1

session.stt_partial("bon", turn_id=turn1)
session.stt_partial("bonjour", turn_id=turn1)
final = session.stt_final("Bonjour Aura", turn_id=turn1)
assert final == "Bonjour Aura"
assert session.active_turn.final_user_transcript == "Bonjour Aura"
assert session.active_turn.committed is False

committed = session.commit_turn(turn_id=turn1)
assert committed == "Bonjour Aura"
assert session.state is VoiceState.THINKING
assert session.active_turn.committed is True

session.llm_first_token(turn_id=turn1)
session.begin_speaking(turn_id=turn1)
assert session.state is VoiceState.SPEAKING
session.tts_first_chunk(turn_id=turn1)
session.playback_started(turn_id=turn1)

# Barge-in must cancel the old turn and immediately return to LISTENING.
token1 = session.active_turn.cancellation
interrupted = session.request_barge_in(reason="user_speech")
assert interrupted == turn1
assert token1.cancelled is True
assert token1.reason == "user_speech"
assert session.active_turn is None
assert session.state is VoiceState.LISTENING

# New user speech after barge-in receives a NEW turn id.
turn2 = session.speech_started()
assert turn2 == "TEST-VOICE-R3:turn:2"
assert turn2 != turn1
session.stt_final("Nouvelle question", turn_id=turn2)
session.commit_turn(turn_id=turn2)
session.begin_speaking(turn_id=turn2)
session.response_completed(turn_id=turn2)
assert session.active_turn is None
assert session.state is VoiceState.LISTENING

# Recovery path cancels active turn without creating a duplicate turn.
turn3 = session.speech_started()
session.stt_partial("test", turn_id=turn3)
token3 = session.active_turn.cancellation
session.recover(reason="stt_timeout", resume_listening=True)
assert token3.cancelled is True
assert token3.reason == "stt_timeout"
assert session.active_turn is None
assert session.state is VoiceState.LISTENING

# Stale turn ids are rejected.
turn4 = session.speech_started()
try:
    session.stt_partial("stale", turn_id=turn3)
except StaleVoiceTurn:
    pass
else:
    raise AssertionError("stale turn was not rejected")

session.stt_final("dernier tour", turn_id=turn4)
session.commit_turn(turn_id=turn4)
session.begin_speaking(turn_id=turn4)
session.response_completed(turn_id=turn4)

# Illegal transition is fail-closed.
try:
    session.begin_speaking()
except (StaleVoiceTurn, InvalidVoiceTransition):
    pass
else:
    raise AssertionError("illegal begin_speaking unexpectedly accepted")

# Every event sequence must be strictly monotonic.
seqs = [e.sequence for e in session.events]
assert seqs == sorted(seqs)
assert len(seqs) == len(set(seqs))
assert all(e.session_id == "TEST-VOICE-R3" for e in session.events)

# Key audit events must exist.
names = [e.event for e in session.events]
for required in (
    "session_started",
    "state_changed",
    "speech_started",
    "stt_partial",
    "stt_final",
    "turn_committed",
    "llm_first_token",
    "tts_first_chunk",
    "playback_started",
    "barge_in_detected",
    "playback_cancelled",
    "turn_cancelled",
    "recovery_started",
    "recovery_completed",
):
    assert required in names, required

# Partial STT is explicitly ephemeral.
partial_events = [e for e in session.events if e.event == "stt_partial"]
assert partial_events
assert all(e.payload.get("ephemeral") is True for e in partial_events)

# Committed transcript explicitly requires canonical text ingress.
commit_events = [e for e in session.events if e.event == "turn_committed"]
assert commit_events
assert all(e.payload.get("canonical_text_ingress_required") is True for e in commit_events)

session.stop()
assert session.state is VoiceState.STOPPED
assert session.is_running is False
assert session.active_turn is None

# No provider I/O surface belongs to the R3 authority.
# Inspect executable Python structure instead of raw source text so safety
# documentation such as "opens no microphone" cannot create a false failure.
import ast

module_path = ROOT / "voice" / "live_voice_session_v220.py"
source_text = module_path.read_text(encoding="utf-8", errors="ignore")
tree = ast.parse(source_text, filename=str(module_path))

forbidden_import_roots = {
    "sounddevice",
    "pyaudio",
    "requests",
    "httpx",
    "whisper",
    "xtts",
    "elevenlabs",
    "subprocess",
}
forbidden_runtime_identifiers = {
    "microphone",
    "sounddevice",
    "pyaudio",
    "requests",
    "httpx",
    "whisper",
    "xtts",
    "elevenlabs",
    "subprocess",
}

import_roots = set()
runtime_identifiers = set()

for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            import_roots.add(alias.name.split(".", 1)[0].casefold())
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            import_roots.add(node.module.split(".", 1)[0].casefold())
    elif isinstance(node, ast.Name):
        runtime_identifiers.add(node.id.casefold())
    elif isinstance(node, ast.Attribute):
        runtime_identifiers.add(node.attr.casefold())

assert not (import_roots & forbidden_import_roots), (
    "forbidden provider/I-O import(s): "
    + repr(sorted(import_roots & forbidden_import_roots))
)
assert not (runtime_identifiers & forbidden_runtime_identifiers), (
    "forbidden provider/I-O runtime identifier(s): "
    + repr(sorted(runtime_identifiers & forbidden_runtime_identifiers))
)

print("[PASS] AURA v2.2 R3 LiveVoiceSession deterministic invariant")
print("[PASS] single session authority owns state/turn/cancellation")
print("[PASS] legal state transitions enforced fail-closed")
print("[PASS] partial STT is ephemeral; final transcript requires canonical text ingress")
print("[PASS] one active response turn; stale turn ids rejected")
print("[PASS] barge-in cancels playback/turn state and returns to LISTENING")
print("[PASS] recovery cancels active turn without duplicate turn")
print("[PASS] monotonic evidence sequence emitted")
print("[PASS] R3 authority has no provider/I-O imports or runtime identifiers (AST verified)")
