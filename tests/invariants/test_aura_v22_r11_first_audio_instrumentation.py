
from __future__ import annotations

from pathlib import Path
import ast
import copy
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.live_voice_bindings_v220 import LiveVoiceProviderBindings
from voice.live_voice_first_audio_adapter_v220 import InstrumentedTextToSpeechAdapter
from voice.live_voice_session_v220 import LiveVoiceSession, VoiceState

TTS_PATH = ROOT / "voice" / "text_to_speech.py"
source = TTS_PATH.read_text(encoding="utf-8", errors="strict")
tree = ast.parse(source, filename=str(TTS_PATH))

classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]

# Bind every R11 structural assertion to the SAME concrete class that owns
# the unique public speak(self, text, ...) surface. Do not collect homonymous
# helper methods from unrelated classes in this provider module.
speak_owners = []
for cls in classes:
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "speak":
            args = [a.arg for a in node.args.args]
            if len(args) >= 2 and args[0] == "self" and args[1] == "text":
                speak_owners.append((cls, node))

assert len(speak_owners) == 1, [
    (cls.name, getattr(node, "lineno", None))
    for cls, node in speak_owners
]

target_class, speak = speak_owners[0]

target_methods = {
    node.name: node
    for node in target_class.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}

assert "_aura_chain_first_audio" in target_methods
helper = target_methods["_aura_chain_first_audio"]

arg_names = [a.arg for a in speak.args.args]
assert arg_names[:2] == ["self", "text"]
assert "on_first_audio" in arg_names

idx = arg_names.index("on_first_audio")
defaults = list(speak.args.defaults)
first_defaulted = len(speak.args.args) - len(defaults)
assert idx >= first_defaulted
default_node = defaults[idx - first_defaulted]
assert isinstance(default_node, ast.Constant) and default_node.value is None

stream_defs = {}
for name in ("_stream_text", "_stream_progressive_text"):
    assert name in target_methods, (target_class.name, name)
    stream_defs[name] = target_methods[name]

    # Account for normal positional args and keyword-only args. R10's exact
    # source audit established on_first_audio on these target-class helpers.
    args = (
        [a.arg for a in stream_defs[name].args.posonlyargs]
        + [a.arg for a in stream_defs[name].args.args]
        + [a.arg for a in stream_defs[name].args.kwonlyargs]
    )
    assert "on_first_audio" in args, (
        target_class.name,
        name,
        getattr(stream_defs[name], "lineno", None),
        args,
    )

stream_calls = []
for node in ast.walk(speak):
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
        and node.func.attr in {"_stream_text", "_stream_progressive_text"}
    ):
        stream_calls.append(node)

assert stream_calls

chained_calls = 0
for call in stream_calls:
    values = [kw.value for kw in call.keywords if kw.arg == "on_first_audio"]
    if len(call.args) >= 4:
        values.append(call.args[3])
    for value in values:
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id == "self"
            and value.func.attr == "_aura_chain_first_audio"
        ):
            chained_calls += 1
            break
assert chained_calls >= 1

helper_copy = copy.deepcopy(helper)
helper_copy.decorator_list = []
mini = ast.Module(body=[helper_copy], type_ignores=[])
ast.fix_missing_locations(mini)
ns = {}
exec(compile(mini, "<r11_helper_only>", "exec"), ns)
chain = ns["_aura_chain_first_audio"]

events = []
wrapped = chain(lambda: events.append("existing"), lambda: events.append("external"))
assert callable(wrapped)
wrapped()
wrapped()
assert events == ["existing", "external"]

events = []
same = lambda: events.append("same")
same_wrapped = chain(same, same)
same_wrapped()
same_wrapped()
assert events == ["same"]
assert chain(None, None) is None

events = []
def bad_external():
    events.append("bad_external")
    raise RuntimeError("observer failure")
wrapped_bad = chain(lambda: events.append("existing"), bad_external)
wrapped_bad()
assert events == ["existing", "bad_external"]

def bad_existing():
    raise ValueError("existing callback failure")
try:
    chain(bad_existing, lambda: None)()
except ValueError:
    pass
else:
    raise AssertionError("existing callback failure was incorrectly swallowed")


class FakeInstrumentedTTS:
    def __init__(self):
        self.spoken = []
        self.stop_calls = 0
        self.warmup_calls = 0
        self.fire_count = 1
        self.mode = "ok"

    def speak(self, text, on_first_audio=None):
        if self.mode == "raise_before_audio":
            raise RuntimeError("synthetic_tts_failure")
        self.spoken.append(text)
        if self.mode != "no_audio_callback" and on_first_audio is not None:
            for _ in range(self.fire_count):
                on_first_audio()

    def stop(self):
        self.stop_calls += 1

    def warmup(self):
        self.warmup_calls += 1


provider = FakeInstrumentedTTS()
adapter = InstrumentedTextToSpeechAdapter(provider)

adapter_events = []
adapter.speak(
    session_id="S",
    turn_id="T",
    text="Bonjour",
    on_first_chunk=lambda: adapter_events.append("first_chunk"),
    on_playback_started=lambda: adapter_events.append("playback_started"),
    on_completed=lambda: adapter_events.append("completed"),
    on_error=lambda error: adapter_events.append(("error", error)),
)
assert adapter_events == ["playback_started", "completed"]
assert "first_chunk" not in adapter_events

provider.fire_count = 2
adapter_events.clear()
adapter.speak(
    session_id="S",
    turn_id="T2",
    text="Double callback",
    on_first_chunk=lambda: adapter_events.append("first_chunk"),
    on_playback_started=lambda: adapter_events.append("playback_started"),
    on_completed=lambda: adapter_events.append("completed"),
    on_error=lambda error: adapter_events.append(("error", error)),
)
assert adapter_events == ["playback_started", "completed"]

provider.mode = "no_audio_callback"
provider.fire_count = 1
adapter_events.clear()
adapter.speak(
    session_id="S",
    turn_id="T3",
    text="No callback",
    on_first_chunk=lambda: adapter_events.append("first_chunk"),
    on_playback_started=lambda: adapter_events.append("playback_started"),
    on_completed=lambda: adapter_events.append("completed"),
    on_error=lambda error: adapter_events.append(("error", error)),
)
assert adapter_events == ["completed"]

provider.mode = "raise_before_audio"
adapter_events.clear()
adapter.speak(
    session_id="S",
    turn_id="T4",
    text="Failure",
    on_first_chunk=lambda: adapter_events.append("first_chunk"),
    on_playback_started=lambda: adapter_events.append("playback_started"),
    on_completed=lambda: adapter_events.append("completed"),
    on_error=lambda error: adapter_events.append(("error", error)),
)
assert adapter_events == [("error", "speak_error:RuntimeError")]


class FakeSTT:
    provider_id = "fake-stt"
    def __init__(self):
        self.turns = {}
    def start_turn(self, *, session_id, turn_id, on_partial, on_final, on_error):
        self.turns[turn_id] = {
            "session_id": session_id,
            "on_partial": on_partial,
            "on_final": on_final,
            "on_error": on_error,
        }
    def cancel(self, *, turn_id, reason):
        del turn_id, reason


provider2 = FakeInstrumentedTTS()
adapter2 = InstrumentedTextToSpeechAdapter(provider2)
session = LiveVoiceSession(session_id="TEST-R11")
fake_stt = FakeSTT()
bridge = LiveVoiceProviderBindings(
    session=session,
    stt=fake_stt,
    tts=adapter2,
    canonical_text_ingress=lambda text, session_id, turn_id, cancellation: "Réponse à " + text,
)

session.start()
turn = bridge.begin_user_turn()
decision = fake_stt.turns[turn]["on_final"]("Question")
assert decision.accepted is True
assert session.state is VoiceState.LISTENING
assert session.active_turn is None

names = [event.event for event in session.events]
assert "playback_started" in names
assert "tts_first_chunk" not in names
assert names.count("playback_started") == 1

adapter_path = ROOT / "voice" / "live_voice_first_audio_adapter_v220.py"
adapter_tree = ast.parse(adapter_path.read_text(encoding="utf-8", errors="strict"), filename=str(adapter_path))
imports = set()
for node in ast.walk(adapter_tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.add(alias.name.casefold())
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            imports.add(node.module.casefold())

for forbidden in (
    "voice.text_to_speech",
    "sounddevice",
    "pyaudio",
    "requests",
    "httpx",
    "torch",
    "whisper",
    "subprocess",
    "socket",
):
    assert forbidden not in imports, forbidden

print("[PASS] AURA v2.2 R11 first-audio instrumentation invariant")
print("[PASS] public speak(text, on_first_audio=None) is backward compatible")
print("[PASS] target-class stream helpers keep native on_first_audio surfaces")
print("[PASS] speak propagates chained first-audio callback into streaming path")
print("[PASS] callback combiner is single-shot and preserves existing callback semantics")
print("[PASS] external observer failure is isolated from provider audio")
print("[PASS] new adapter maps first-audio to playback_started only")
print("[PASS] adapter does not fabricate tts_first_chunk or missing playback callback")
print("[PASS] duplicate provider first-audio callback collapses to one playback event")
print("[PASS] R4/LiveVoiceSession integration records one playback_started event")
print("[PASS] no concrete provider/audio/network/model import in new adapter")
