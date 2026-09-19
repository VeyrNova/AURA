
from __future__ import annotations

from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.live_voice_session_v220 import LiveVoiceSession, VoiceState
from voice.live_voice_streaming_v220 import LiveVoiceStreamingPipeline
from voice.live_voice_turn_detection_v220 import (
    LiveVoiceTurnEndGate,
    TurnEndConfig,
    TurnEndPhase,
)


class CanonicalStream:
    def __init__(self):
        self.calls = []

    def __call__(self, text, session_id, turn_id, cancellation):
        self.calls.append((text, session_id, turn_id, cancellation.cancelled))
        return iter(["OK"])


session = LiveVoiceSession(session_id="TEST-R6")
canonical = CanonicalStream()
pipeline = LiveVoiceStreamingPipeline(
    session=session,
    canonical_streaming_ingress=canonical,
    stt_capacity=2,
    llm_capacity=2,
    tts_capacity=1,
)

gate = LiveVoiceTurnEndGate(
    session=session,
    final_turn_commit=lambda turn_id, text: pipeline.commit_stt_final(
        turn_id, text
    ).accepted,
    config=TurnEndConfig(
        min_speech_ms=120,
        silence_timeout_ms=420,
    ),
)

session.start()
assert session.state is VoiceState.LISTENING

# ------------------------------------------------------------------
# False end candidate: resume before timeout MUST keep same turn.
# ------------------------------------------------------------------
turn1 = gate.begin_user_turn(at_ms=0)
assert session.state is VoiceState.TRANSCRIBING

gate.speech_activity(turn1, at_ms=100)
gate.speech_activity(turn1, at_ms=250)

candidate = gate.speech_stopped(turn1, at_ms=300)
assert candidate.action == "HOLD"
assert candidate.reason == "waiting_for_silence_threshold"

before_timeout = gate.poll(turn1, at_ms=650)
assert before_timeout.action == "HOLD"
assert before_timeout.reason == "silence_threshold_not_reached"
assert before_timeout.silence_ms == 350
assert session.state is VoiceState.TRANSCRIBING

resumed = gate.speech_activity(turn1, at_ms=680)
assert resumed.action == "HOLD"
assert resumed.reason == "speech_active"
assert resumed.false_end_recoveries == 1
assert gate.detector.phase is TurnEndPhase.SPEAKING
assert session.active_turn is not None
assert session.active_turn.turn_id == turn1

gate.speech_activity(turn1, at_ms=820)
second_candidate = gate.speech_stopped(turn1, at_ms=900)
assert second_candidate.action == "HOLD"

# Exactly one millisecond before threshold: no commit.
pre = gate.poll(turn1, at_ms=1319)
assert pre.action == "HOLD"
assert pre.silence_ms == 419
assert session.state is VoiceState.TRANSCRIBING
assert len(canonical.calls) == 0

# At configured threshold: commit becomes eligible and final transcript
# traverses R5 canonical pipeline exactly once.
commit = gate.commit_if_ready(
    turn1,
    final_text="Phrase complète après reprise",
    at_ms=1320,
)
assert commit.action == "COMMIT"
assert commit.reason == "canonical_turn_committed"
assert commit.silence_ms == 420
assert commit.false_end_recoveries == 1
assert gate.detector.phase is TurnEndPhase.COMMITTED
assert session.state is VoiceState.THINKING
assert len(canonical.calls) == 1
assert canonical.calls[0][0] == "Phrase complète après reprise"
assert canonical.calls[0][2] == turn1
assert canonical.calls[0][3] is False

# Complete synthetic R5 stream so next turn can start.
assert pipeline.pump_llm_once(turn1).accepted is True
assert pipeline.promote_llm_to_tts(turn1).accepted is True
item = pipeline.consume_tts_chunk(turn1)
assert item is not None and item.text == "OK"
assert pipeline.pump_llm_once(turn1).reason == "llm_stream_eof"
assert pipeline.mark_playback_started(turn1).accepted is True
assert pipeline.complete_if_drained(turn1).accepted is True
assert session.state is VoiceState.LISTENING

# ------------------------------------------------------------------
# Minimum-speech guard: short noise never commits, even after long silence.
# ------------------------------------------------------------------
gate2 = LiveVoiceTurnEndGate(
    session=session,
    final_turn_commit=lambda turn_id, text: pipeline.commit_stt_final(
        turn_id, text
    ).accepted,
    config=TurnEndConfig(
        min_speech_ms=120,
        silence_timeout_ms=420,
    ),
)

turn2 = gate2.begin_user_turn(at_ms=2000)
short = gate2.speech_stopped(turn2, at_ms=2050)
assert short.action == "HOLD"
assert short.reason == "minimum_speech_guard"
assert short.voiced_ms == 50

still_guarded = gate2.poll(turn2, at_ms=3000)
assert still_guarded.action == "HOLD"
assert still_guarded.reason == "minimum_speech_guard"
assert session.state is VoiceState.TRANSCRIBING
assert len(canonical.calls) == 1

# User continues the same turn; this is recovery, not a new turn.
continued = gate2.speech_activity(turn2, at_ms=3010)
assert continued.action == "HOLD"
assert gate2.detector.false_end_recoveries == 1
gate2.speech_activity(turn2, at_ms=3120)
gate2.speech_stopped(turn2, at_ms=3180)

ready2 = gate2.poll(turn2, at_ms=3600)
assert ready2.action == "COMMIT"
assert ready2.silence_ms == 420

commit2 = gate2.commit_if_ready(
    turn2,
    final_text="Vraie phrase",
    at_ms=3600,
)
assert commit2.action == "COMMIT"
assert len(canonical.calls) == 2
assert canonical.calls[1][0] == "Vraie phrase"
assert session.state is VoiceState.THINKING

# ------------------------------------------------------------------
# Detector evidence is monotonic and explicitly records false-end recovery.
# ------------------------------------------------------------------
seqs = [e.sequence for e in gate.detector.evidence]
assert seqs == sorted(seqs)
assert len(seqs) == len(set(seqs))
names = [e.event for e in gate.detector.evidence]
assert "speech_ended_candidate" in names
assert "false_end_recovered" in names
assert "turn_end_ready" in names
assert "speech_ended" in names

# ------------------------------------------------------------------
# Static guard: no sleeps, no clocks, no audio/provider/network ownership,
# no competing session state machine.
# ------------------------------------------------------------------
module_path = ROOT / "voice" / "live_voice_turn_detection_v220.py"
source = module_path.read_text(encoding="utf-8", errors="ignore")
tree = ast.parse(source, filename=str(module_path))

imports = set()
class_names = set()
call_names = set()
self_attrs = set()

for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.add(alias.name.split(".", 1)[0].casefold())
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            imports.add(node.module.split(".", 1)[0].casefold())
    elif isinstance(node, ast.ClassDef):
        class_names.add(node.name)
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            call_names.add(node.func.id.casefold())
        elif isinstance(node.func, ast.Attribute):
            call_names.add(node.func.attr.casefold())
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                self_attrs.add(target.attr)

for forbidden_import in (
    "time",
    "asyncio",
    "sounddevice",
    "pyaudio",
    "requests",
    "httpx",
    "whisper",
    "subprocess",
):
    assert forbidden_import not in imports, forbidden_import

assert "sleep" not in call_names
assert "LiveVoiceSession" not in class_names
for forbidden_attr in (
    "state",
    "_state",
    "_active_turn",
    "_turn_counter",
    "cancellation",
):
    assert forbidden_attr not in self_attrs, forbidden_attr

assert TurnEndConfig().silence_timeout_ms <= 500

print("[PASS] AURA v2.2 R6 deterministic turn-end invariant")
print("[PASS] silence threshold is synthetic/configurable and <= 500 ms")
print("[PASS] false end resumes the SAME turn before timeout")
print("[PASS] 419 ms silence does not commit; 420 ms does")
print("[PASS] minimum-speech guard rejects short-noise turn end")
print("[PASS] final transcript commits through R5 canonical streaming path exactly once")
print("[PASS] detector evidence records candidate/recovery/ready/final end")
print("[PASS] detector owns no LiveVoiceSession state or cancellation authority")
print("[PASS] no fixed sleep/real clock/microphone/audio/network/model/provider I/O")
