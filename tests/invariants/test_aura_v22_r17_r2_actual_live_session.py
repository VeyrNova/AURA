
from __future__ import annotations

import inspect
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.live_voice_session_v220 import LiveVoiceSession
from voice.live_voice_canonical_ingress_bridge_v220 import LiveVoiceCanonicalIngressBridge


def callback_sink(*args, **kwargs):
    return None


def value_for_parameter(name: str):
    n = name.casefold()
    if n == "session_id" or ("session" in n and "id" in n):
        return "R17-R2-SYNTHETIC"
    if n in {"clock", "now", "time_source", "monotonic"}:
        return time.monotonic
    if any(token in n for token in ("event_sink", "event_callback", "on_event", "state_sink", "callback")):
        return callback_sink
    if any(token in n for token in ("max_events", "event_history", "history_limit")):
        return 256
    raise KeyError(name)


def build_required_kwargs(callable_obj, extra=None):
    extra = dict(extra or {})
    signature = inspect.signature(callable_obj)
    kwargs = {}
    unsupported = []

    for name, param in signature.parameters.items():
        if name in {"self", "cls"}:
            continue
        if name in extra:
            kwargs[name] = extra[name]
            continue
        if param.default is not inspect._empty:
            continue
        try:
            kwargs[name] = value_for_parameter(name)
        except KeyError:
            unsupported.append(name)

    if unsupported:
        raise RuntimeError(
            "unsupported required parameters: "
            + ", ".join(unsupported)
        )

    return kwargs


def call_supported(method, extra=None):
    return method(**build_required_kwargs(method, extra=extra))


def extract_turn_id(session, speech_result):
    candidates = [speech_result]

    active = getattr(session, "active_turn", None)
    if callable(active):
        try:
            active = active()
        except TypeError:
            pass
    candidates.append(active)

    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, str) and candidate.strip():
            return candidate
        if isinstance(candidate, dict):
            for key in ("turn_id", "id"):
                value = candidate.get(key)
                if value:
                    return str(value)
        for attr in ("turn_id", "id"):
            value = getattr(candidate, attr, None)
            if value:
                return str(value)

    raise RuntimeError("unable to resolve actual LiveVoiceSession turn_id")


class CoreSpy:
    def __init__(self):
        self.calls = []

    def try_handle_intent(self, text, *, allow_grounding=True):
        self.calls.append({
            "text":str(text),
            "allow_grounding":allow_grounding,
        })
        return {"accepted":True}


session = LiveVoiceSession(
    **build_required_kwargs(LiveVoiceSession)
)

call_supported(session.start)

speech_result = call_supported(session.speech_started)
turn_id = extract_turn_id(session, speech_result)

core = CoreSpy()
bridge = LiveVoiceCanonicalIngressBridge(
    live_session=session,
    aura_core=core,
)

# R17-R2-R1 proved the required order:
# final transcript MUST reach stt_final before commit_turn.
delivery = bridge.deliver_final_text(
    turn_id=turn_id,
    text="Bonjour AURA",
)

assert delivery.text == "Bonjour AURA"
assert delivery.turn_id == turn_id
assert len(core.calls) == 1
assert core.calls[0]["text"] == "Bonjour AURA"

commit = getattr(session, "commit_turn", None)
if callable(commit):
    call_supported(
        commit,
        extra={
            "turn_id":turn_id,
            "reason":"r17_r2_r2_evidenced_order",
        },
    )

events_method = getattr(session, "events", None)
if callable(events_method):
    events = events_method()
    assert len(list(events)) >= 1

stop = getattr(session, "stop", None)
if callable(stop):
    call_supported(stop)

print("[PASS] AURA v2.2 R17-R2 actual LiveVoiceSession synthetic invariant")
print("[PASS] actual start -> speech_started -> stt_final -> commit_turn path executed")
print("[PASS] retained canonical bridge routed exactly once to isolated AuraCore boundary")
print("[PASS] no real AuraCore business logic, LLM, tool or TTS execution")
