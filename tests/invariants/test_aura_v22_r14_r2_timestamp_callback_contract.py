
from __future__ import annotations

from pathlib import Path
import ast
import copy
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.live_voice_first_audio_adapter_v220 import InstrumentedTextToSpeechAdapter

TTS = ROOT / "voice" / "text_to_speech.py"
ADAPTER = ROOT / "voice" / "live_voice_first_audio_adapter_v220.py"

# ------------------------------------------------------------------
# Provider helper contract: timestamped first-audio callback must pass through.
# ------------------------------------------------------------------
source = TTS.read_text(encoding="utf-8", errors="strict")
tree = ast.parse(source, filename=str(TTS))

helper_nodes = []
for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
    methods = {
        n.name: n
        for n in cls.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    speak = methods.get("speak")
    if speak is None:
        continue
    args = (
        [a.arg for a in speak.args.posonlyargs]
        + [a.arg for a in speak.args.args]
        + [a.arg for a in speak.args.kwonlyargs]
    )
    if "on_first_audio" not in args:
        continue
    helper = methods.get("_aura_chain_first_audio")
    if helper is not None:
        helper_nodes.append(helper)

assert len(helper_nodes) == 1
helper = helper_nodes[0]

helper_copy = copy.deepcopy(helper)
helper_copy.decorator_list = []
mini = ast.Module(body=[helper_copy], type_ignores=[])
ast.fix_missing_locations(mini)
namespace = {}
exec(compile(mini, "<r14_r2_helper>", "exec"), namespace)
chain = namespace["_aura_chain_first_audio"]

events = []
wrapped = chain(
    lambda timestamp: events.append(("existing", timestamp)),
    lambda timestamp: events.append(("external", timestamp)),
)
wrapped(123.456)
wrapped(999.0)
assert events == [
    ("existing", 123.456),
    ("external", 123.456),
]

# Keyword payload is preserved as well.
events = []
wrapped_kw = chain(
    lambda *, at: events.append(("existing", at)),
    lambda *, at: events.append(("external", at)),
)
wrapped_kw(at=7.25)
assert events == [
    ("existing", 7.25),
    ("external", 7.25),
]

# Observer failure stays isolated.
events = []
def bad_external(timestamp):
    events.append(("bad", timestamp))
    raise RuntimeError("observer failure")

wrapped_bad = chain(
    lambda timestamp: events.append(("existing", timestamp)),
    bad_external,
)
wrapped_bad(42.0)
assert events == [
    ("existing", 42.0),
    ("bad", 42.0),
]


# ------------------------------------------------------------------
# Adapter contract: provider may call on_first_audio(timestamp).
# ------------------------------------------------------------------
class TimestampedFakeTTS:
    def __init__(self):
        self.stop_calls = 0

    def speak(self, text, on_first_audio=None):
        assert text == "Timestamped test"
        if on_first_audio is not None:
            on_first_audio(321.123)
        return {"ok": True}

    def stop(self):
        self.stop_calls += 1


provider = TimestampedFakeTTS()
adapter = InstrumentedTextToSpeechAdapter(provider)

adapter_events = []
adapter.speak(
    session_id="R14-R2",
    turn_id="T1",
    text="Timestamped test",
    on_first_chunk=lambda: adapter_events.append("first_chunk"),
    on_playback_started=lambda: adapter_events.append("playback_started"),
    on_completed=lambda: adapter_events.append("completed"),
    on_error=lambda error: adapter_events.append(("error", error)),
)

assert adapter_events == ["playback_started", "completed"]
assert "first_chunk" not in adapter_events

# Duplicate timestamped provider callbacks still collapse to one playback event.
class DuplicateTimestampedFakeTTS(TimestampedFakeTTS):
    def speak(self, text, on_first_audio=None):
        if on_first_audio is not None:
            on_first_audio(1.0)
            on_first_audio(2.0)

provider2 = DuplicateTimestampedFakeTTS()
adapter2 = InstrumentedTextToSpeechAdapter(provider2)
events2 = []
adapter2.speak(
    session_id="R14-R2",
    turn_id="T2",
    text="Timestamped test",
    on_first_chunk=lambda: events2.append("first_chunk"),
    on_playback_started=lambda: events2.append("playback_started"),
    on_completed=lambda: events2.append("completed"),
    on_error=lambda error: events2.append(("error", error)),
)
assert events2 == ["playback_started", "completed"]

# ------------------------------------------------------------------
# Static evidence: both bridge closures accept arbitrary provider payloads.
# ------------------------------------------------------------------
tts_tree = ast.parse(source, filename=str(TTS))
tts_once = []
for node in ast.walk(tts_tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_once":
        # Restrict to the R11 marker region by line proximity to helper.
        if helper.lineno <= node.lineno <= getattr(helper, "end_lineno", node.lineno):
            tts_once.append(node)
assert len(tts_once) == 1
assert tts_once[0].args.vararg is not None
assert tts_once[0].args.kwarg is not None

adapter_source = ADAPTER.read_text(encoding="utf-8", errors="strict")
adapter_tree = ast.parse(adapter_source, filename=str(ADAPTER))
adapter_once = [
    node for node in ast.walk(adapter_tree)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    and node.name == "first_audio_once"
]
assert len(adapter_once) == 1
assert adapter_once[0].args.vararg is not None
assert adapter_once[0].args.kwarg is not None

print("[PASS] AURA v2.2 R14-R2 timestamp callback contract invariant")
print("[PASS] provider helper accepts positional timestamp payload")
print("[PASS] provider helper preserves keyword payload")
print("[PASS] provider helper remains single-shot")
print("[PASS] external observer failure remains isolated")
print("[PASS] first-audio adapter accepts provider timestamp payload")
print("[PASS] timestamped first-audio maps to playback_started only")
print("[PASS] duplicate timestamped callbacks collapse to one playback event")
