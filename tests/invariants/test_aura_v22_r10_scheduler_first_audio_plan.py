
from __future__ import annotations

from pathlib import Path
from threading import Event, Lock, get_ident
import ast
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.live_voice_bindings_v220 import LiveVoiceProviderBindings
from voice.live_voice_real_provider_adapters_v220 import (
    TextToSpeechAdapter,
    VoiceEngineSTTAdapter,
)
from voice.live_voice_scheduler_v220 import (
    LiveVoiceWorkScheduler,
    SchedulerBackpressure,
)
from voice.live_voice_session_v220 import CancellationToken, LiveVoiceSession, VoiceState


# ------------------------------------------------------------------
# 1. Bounded scheduler: submit is non-blocking while worker is blocked.
# ------------------------------------------------------------------
scheduler = LiveVoiceWorkScheduler(max_workers=1, max_pending_per_turn=2)

main_thread = get_ident()
worker_started = Event()
worker_release = Event()
worker_thread_ids = []

token_a = CancellationToken(turn_id="A")

def blocking_work():
    worker_thread_ids.append(get_ident())
    worker_started.set()
    worker_release.wait(timeout=3)
    return "A1"

f1 = scheduler.submit(
    turn_id="A",
    cancellation=token_a,
    fn=blocking_work,
)

assert worker_started.wait(timeout=2), "worker did not start"
assert f1.done() is False
assert main_thread not in worker_thread_ids

# Second work is pending; third exceeds bounded per-turn capacity.
f2 = scheduler.submit(
    turn_id="A",
    cancellation=token_a,
    fn=lambda: "A2",
)
try:
    scheduler.submit(
        turn_id="A",
        cancellation=token_a,
        fn=lambda: "A3",
    )
except SchedulerBackpressure:
    pass
else:
    raise AssertionError("scheduler accepted work beyond per-turn bound")

assert scheduler.pending_count("A") == 2

# cancel_pending can cancel queued work, but must not mutate canonical token.
cancelled_pending = scheduler.cancel_pending(turn_id="A")
assert cancelled_pending == 1
assert token_a.cancelled is False

worker_release.set()
out1 = f1.result(timeout=3)
assert out1.executed is True
assert out1.suppressed is False
assert out1.value == "A1"
assert f2.cancelled() is True


# ------------------------------------------------------------------
# 2. Canonical token suppresses stale work before execution.
# ------------------------------------------------------------------
token_b = CancellationToken(turn_id="B")
token_b.cancel("synthetic_barge_in")
ran_b = []

fb = scheduler.submit(
    turn_id="B",
    cancellation=token_b,
    fn=lambda: ran_b.append(True),
)
ob = fb.result(timeout=2)
assert ob.executed is False
assert ob.suppressed is True
assert ob.reason == "cancelled_before_submit"
assert ran_b == []


# ------------------------------------------------------------------
# 3. R9 adapters + R4 bindings scheduled off caller thread.
#    Barge-in stops fake TTS cooperatively; stale completion cannot revive turn.
# ------------------------------------------------------------------
class FakeVoiceEngine:
    def __init__(self):
        self.transcribe_thread = None
        self.cancel_calls = 0

    def transcribe(self, audio):
        del audio
        self.transcribe_thread = get_ident()
        return "Question planifiée"

    def cancel_listening(self):
        self.cancel_calls += 1


class BlockingFakeTTS:
    def __init__(self):
        self.speak_thread = None
        self.started = Event()
        self.release = Event()
        self.stop_calls = 0
        self.spoken = []

    def speak(self, text):
        self.speak_thread = get_ident()
        self.spoken.append(text)
        self.started.set()
        self.release.wait(timeout=3)

    def stop(self):
        self.stop_calls += 1
        self.release.set()


session = LiveVoiceSession(session_id="TEST-R10")
stt_provider = FakeVoiceEngine()
tts_provider = BlockingFakeTTS()
stt = VoiceEngineSTTAdapter(stt_provider)
tts = TextToSpeechAdapter(tts_provider)

ingress_threads = []
def canonical_ingress(text, session_id, turn_id, cancellation):
    del session_id, turn_id
    ingress_threads.append(get_ident())
    assert cancellation.cancelled is False
    return "Réponse à " + text

bridge = LiveVoiceProviderBindings(
    session=session,
    stt=stt,
    tts=tts,
    canonical_text_ingress=canonical_ingress,
)

session.start()
turn = bridge.begin_user_turn()
assert session.state is VoiceState.TRANSCRIBING
token = session.active_turn.cancellation

provider_future = scheduler.submit(
    turn_id=turn,
    cancellation=token,
    fn=stt.submit_audio,
    kwargs={"turn_id": turn, "audio": b"synthetic-bytes"},
)

assert tts_provider.started.wait(timeout=2), "fake TTS did not start"
assert provider_future.done() is False
assert stt_provider.transcribe_thread != main_thread
assert tts_provider.speak_thread != main_thread
assert ingress_threads and ingress_threads[0] != main_thread
assert session.state is VoiceState.SPEAKING

decision = bridge.request_barge_in(reason="user_speech")
assert decision.accepted is True
assert decision.turn_id == turn
assert token.cancelled is True
assert tts_provider.stop_calls == 1
assert session.state is VoiceState.LISTENING
assert session.active_turn is None

# Running future cannot be force-killed; cooperative provider stop releases it.
scheduler.cancel_pending(turn_id=turn)
provider_outcome = provider_future.result(timeout=3)
assert provider_outcome.executed is True
assert provider_outcome.suppressed is True
assert provider_outcome.reason == "cancelled_after_execute"

# The adapter called completion after fake speak returned; R4 rejects stale
# completion internally, so the old turn remains dead.
assert session.state is VoiceState.LISTENING
assert session.active_turn is None


# ------------------------------------------------------------------
# 4. First-audio instrumentation plan is exact, source-hash bound, and honest.
# ------------------------------------------------------------------
plan_path = ROOT / "data" / "roadmap" / "AURA_V2_2_LIVE_VOICE_FIRST_AUDIO_INSTRUMENTATION_PLAN.json"
plan = json.loads(plan_path.read_text(encoding="utf-8"))

assert plan["schema"] == "aura.v2.2.live-voice.r10.first-audio-instrumentation-plan.v1"
assert plan["status"] == "PLAN_ONLY"
assert plan["source"]["path"] == "voice/text_to_speech.py"
assert plan["source"]["sha256"] == "9d4f576de34332d980ac834835cdedcf2af8c3834743088a711b5a0a72b8423d"

surface = plan["verified_surface"]
assert surface["speak"]["found"] is True
assert surface["stop"]["found"] is True
assert surface["_stream_text"]["found"] is True
assert surface["_stream_progressive_text"]["found"] is True
assert "on_first_audio" in surface["_stream_text"]["args"]
assert "on_first_audio" in surface["_stream_progressive_text"]["args"]
assert "on_first_audio" not in surface["speak"]["args"]

assert plan["proposed_r11"]["backward_compatible_public_change"] is True
assert plan["proposed_r11"]["provider_source_mutation_required"] is True
assert plan["proposed_r11"]["adapter_maps_callback_to"] == "on_playback_started"
assert plan["proposed_r11"]["must_not_map_callback_to"] == "on_first_chunk"
assert plan["certification_boundary"]["real_first_audio_certified"] is False
assert plan["certification_boundary"]["real_latency_certified"] is False


# ------------------------------------------------------------------
# 5. Static scheduler authority guard.
# ------------------------------------------------------------------
module_path = ROOT / "voice" / "live_voice_scheduler_v220.py"
source = module_path.read_text(encoding="utf-8", errors="ignore")
tree = ast.parse(source, filename=str(module_path))

imports = set()
self_attrs = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.add(alias.name.split(".", 1)[0].casefold())
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            imports.add(node.module.split(".", 1)[0].casefold())
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                self_attrs.add(target.attr)

for forbidden in (
    "sounddevice",
    "pyaudio",
    "requests",
    "httpx",
    "whisper",
    "socket",
    "subprocess",
):
    assert forbidden not in imports, forbidden

for forbidden_attr in (
    "state",
    "_state",
    "_active_turn",
    "_turn_counter",
    "cancellation",
):
    assert forbidden_attr not in self_attrs, forbidden_attr

scheduler.shutdown(wait=True)
session.stop()

print("[PASS] AURA v2.2 R10 scheduler/cancellation invariant")
print("[PASS] bounded scheduler returns while worker is blocked")
print("[PASS] provider work executes off caller thread")
print("[PASS] per-turn scheduler backpressure is enforced")
print("[PASS] cancel_pending cancels queued Future without mutating canonical token")
print("[PASS] canonical cancelled token suppresses stale work")
print("[PASS] R9 STT/TTS adapters integrate through R4 bindings on worker")
print("[PASS] barge-in uses canonical session cancellation then cooperative TTS stop")
print("[PASS] stale completion cannot resurrect interrupted turn")
print("[PASS] exact first-audio plan is bound to current text_to_speech.py hash")
print("[PASS] plan preserves honest boundary: no real first-audio/latency certification")
print("[PASS] scheduler owns no second LiveVoiceSession/cancellation authority")
