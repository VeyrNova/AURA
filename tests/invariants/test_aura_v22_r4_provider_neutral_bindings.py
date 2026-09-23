
from __future__ import annotations

from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.live_voice_session_v220 import LiveVoiceSession, VoiceState
from voice.live_voice_bindings_v220 import LiveVoiceProviderBindings


class FakeSTT:
    provider_id = "fake-stt"

    def __init__(self):
        self.turns = {}
        self.cancelled = []

    def start_turn(
        self,
        *,
        session_id,
        turn_id,
        on_partial,
        on_final,
        on_error,
    ):
        self.turns[turn_id] = {
            "session_id": session_id,
            "on_partial": on_partial,
            "on_final": on_final,
            "on_error": on_error,
        }

    def cancel(self, *, turn_id, reason):
        self.cancelled.append((turn_id, reason))

    def partial(self, turn_id, text):
        return self.turns[turn_id]["on_partial"](text)

    def final(self, turn_id, text):
        return self.turns[turn_id]["on_final"](text)

    def fail(self, turn_id, reason):
        return self.turns[turn_id]["on_error"](reason)


class FakeTTS:
    provider_id = "fake-tts"

    def __init__(self):
        self.turns = {}
        self.cancelled = []

    def speak(
        self,
        *,
        session_id,
        turn_id,
        text,
        on_first_chunk,
        on_playback_started,
        on_completed,
        on_error,
    ):
        self.turns[turn_id] = {
            "session_id": session_id,
            "text": text,
            "on_first_chunk": on_first_chunk,
            "on_playback_started": on_playback_started,
            "on_completed": on_completed,
            "on_error": on_error,
        }

    def cancel(self, *, turn_id, reason):
        self.cancelled.append((turn_id, reason))

    def first_chunk(self, turn_id):
        return self.turns[turn_id]["on_first_chunk"]()

    def playback_started(self, turn_id):
        return self.turns[turn_id]["on_playback_started"]()

    def completed(self, turn_id):
        return self.turns[turn_id]["on_completed"]()

    def fail(self, turn_id, reason):
        return self.turns[turn_id]["on_error"](reason)


ingress_calls = []

def canonical_ingress(text, session_id, turn_id, cancellation):
    ingress_calls.append({
        "text": text,
        "session_id": session_id,
        "turn_id": turn_id,
        "cancelled": cancellation.cancelled,
    })
    return "Réponse canonique à: " + text


events = []
session = LiveVoiceSession(session_id="TEST-R4", event_sink=events.append)
stt = FakeSTT()
tts = FakeTTS()
bridge = LiveVoiceProviderBindings(
    session=session,
    stt=stt,
    tts=tts,
    canonical_text_ingress=canonical_ingress,
)

session.start()
assert session.state is VoiceState.LISTENING

# ------------------------------------------------------------------
# Full fake STT -> canonical ingress -> fake TTS completion
# ------------------------------------------------------------------
turn1 = bridge.begin_user_turn()
assert session.state is VoiceState.TRANSCRIBING
assert stt.turns[turn1]["session_id"] == "TEST-R4"

d = stt.partial(turn1, "bon")
assert d.accepted is True
d = stt.partial(turn1, "bonjour")
assert d.accepted is True

d = stt.final(turn1, "Bonjour Aura")
assert d.accepted is True
assert d.reason == "turn_committed_to_canonical_ingress"
assert session.state is VoiceState.SPEAKING

assert len(ingress_calls) == 1
assert ingress_calls[0]["text"] == "Bonjour Aura"
assert ingress_calls[0]["session_id"] == "TEST-R4"
assert ingress_calls[0]["turn_id"] == turn1
assert ingress_calls[0]["cancelled"] is False

assert tts.turns[turn1]["text"] == "Réponse canonique à: Bonjour Aura"

assert tts.first_chunk(turn1).accepted is True
assert tts.playback_started(turn1).accepted is True
assert tts.completed(turn1).accepted is True
assert session.state is VoiceState.LISTENING
assert session.active_turn is None

# Duplicate/stale final callback must not call canonical ingress twice.
d = stt.final(turn1, "Bonjour Aura DUPLICATE")
assert d.accepted is False
assert d.reason == "stale_or_duplicate_stt_final"
assert len(ingress_calls) == 1

# ------------------------------------------------------------------
# Barge-in: state authority cancels first, provider receives cancel,
# stale TTS callback cannot resurrect or complete old turn.
# ------------------------------------------------------------------
turn2 = bridge.begin_user_turn()
stt.final(turn2, "Deuxième tour")
assert session.state is VoiceState.SPEAKING
old_token = session.active_turn.cancellation

d = bridge.request_barge_in(reason="user_speech")
assert d.accepted is True
assert d.turn_id == turn2
assert old_token.cancelled is True
assert session.state is VoiceState.LISTENING
assert session.active_turn is None
assert (turn2, "user_speech") in tts.cancelled

stale_done = tts.completed(turn2)
assert stale_done.accepted is False
assert stale_done.reason == "stale_tts_completed"
assert session.state is VoiceState.LISTENING
assert session.active_turn is None

# A new turn after barge-in must be independent.
turn3 = bridge.begin_user_turn()
assert turn3 != turn2
stt.final(turn3, "Troisième tour")
assert session.state is VoiceState.SPEAKING
tts.completed(turn3)
assert session.state is VoiceState.LISTENING

# ------------------------------------------------------------------
# STT provider failure recovers to LISTENING, cancels provider turn.
# ------------------------------------------------------------------
turn4 = bridge.begin_user_turn()
d = stt.fail(turn4, "synthetic_stt_failure")
assert d.accepted is True
assert d.reason == "stt_error_recovered"
assert (turn4, "synthetic_stt_failure") in stt.cancelled
assert session.state is VoiceState.LISTENING
assert session.active_turn is None

# ------------------------------------------------------------------
# TTS provider failure recovers to LISTENING and provider cancellation.
# ------------------------------------------------------------------
turn5 = bridge.begin_user_turn()
stt.final(turn5, "Cinquième tour")
assert session.state is VoiceState.SPEAKING
d = tts.fail(turn5, "synthetic_tts_failure")
assert d.accepted is True
assert d.reason == "tts_error_recovered"
assert (turn5, "synthetic_tts_failure") in tts.cancelled
assert session.state is VoiceState.LISTENING
assert session.active_turn is None

# ------------------------------------------------------------------
# Exact event invariants from underlying authority remain intact.
# ------------------------------------------------------------------
seqs = [e.sequence for e in session.events]
assert seqs == sorted(seqs)
assert len(seqs) == len(set(seqs))
assert all(e.session_id == "TEST-R4" for e in session.events)

names = [e.event for e in session.events]
for expected in (
    "stt_partial",
    "stt_final",
    "turn_committed",
    "llm_first_token",
    "tts_first_chunk",
    "playback_started",
    "barge_in_detected",
    "playback_cancelled",
    "recovery_started",
    "recovery_completed",
):
    assert expected in names, expected

# ------------------------------------------------------------------
# Static authority guard: R4 bridge may adapt providers but must not create
# its own state machine / turn counter / cancellation authority or do real I/O.
# ------------------------------------------------------------------
binding_path = ROOT / "voice" / "live_voice_bindings_v220.py"
source = binding_path.read_text(encoding="utf-8", errors="ignore")
tree = ast.parse(source, filename=str(binding_path))

forbidden_import_roots = {
    "sounddevice",
    "pyaudio",
    "requests",
    "httpx",
    "whisper",
    "xtts",
    "elevenlabs",
    "subprocess",
    "asyncio",
}
imports = set()
classes = set()
assigned_attrs = set()

for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.add(alias.name.split(".", 1)[0].casefold())
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            imports.add(node.module.split(".", 1)[0].casefold())
    elif isinstance(node, ast.ClassDef):
        classes.add(node.name)
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                assigned_attrs.add(target.attr)

assert not (imports & forbidden_import_roots), sorted(imports & forbidden_import_roots)
assert "LiveVoiceSession" not in classes
assert "_state" not in assigned_attrs
assert "state" not in assigned_attrs
assert "_active_turn" not in assigned_attrs
assert "_turn_counter" not in assigned_attrs
assert "_sequence" not in assigned_attrs

session.stop()
assert session.state is VoiceState.STOPPED

print("[PASS] AURA v2.2 R4 provider-neutral bindings invariant")
print("[PASS] fake STT callbacks feed LiveVoiceSession without owning state")
print("[PASS] final transcript reaches canonical text ingress exactly once")
print("[PASS] fake TTS callbacks drive speaking/playback/completion through LiveVoiceSession")
print("[PASS] duplicate/stale provider callbacks are rejected fail-closed")
print("[PASS] barge-in cancels session turn then signals provider cancellation")
print("[PASS] stale TTS completion cannot resurrect interrupted turn")
print("[PASS] STT/TTS provider failures recover to LISTENING")
print("[PASS] bridge creates no second state/turn/cancellation authority")
print("[PASS] no real microphone/audio/network/model/provider I/O")
