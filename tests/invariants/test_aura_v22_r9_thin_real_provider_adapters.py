
from __future__ import annotations

from pathlib import Path
import ast
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice.live_voice_real_provider_adapters_v220 import (
    TextToSpeechAdapter,
    VoiceEngineSTTAdapter,
)


class FakeVoiceEngine:
    def __init__(self):
        self.transcribe_calls = []
        self.cancel_calls = 0
        self.stop_calls = 0
        self.warmup_calls = 0
        self.mode = "ok"

    def transcribe(self, audio):
        self.transcribe_calls.append(audio)
        if self.mode == "raise":
            raise RuntimeError("synthetic_stt_failure")
        if self.mode == "dict":
            return {"text": "dict transcript"}
        if self.mode == "empty":
            return ""
        return "bonjour aura"

    def cancel_listening(self):
        self.cancel_calls += 1

    def stop_listening(self):
        self.stop_calls += 1

    def warmup(self):
        self.warmup_calls += 1


class FakeVoiceEngineStopOnly:
    def __init__(self):
        self.stop_calls = 0

    def transcribe(self, audio):
        return str(audio)

    def stop_listening(self):
        self.stop_calls += 1


class FakeTTS:
    def __init__(self):
        self.spoken = []
        self.stop_calls = 0
        self.warmup_calls = 0
        self.mode = "ok"

    def speak(self, text):
        if self.mode == "raise":
            raise RuntimeError("synthetic_tts_failure")
        self.spoken.append(text)

    def stop(self):
        self.stop_calls += 1

    def warmup(self):
        self.warmup_calls += 1


# ------------------------------------------------------------------
# STT adapter: exact final transcript mapping, no invented partial callback.
# ------------------------------------------------------------------
stt_provider = FakeVoiceEngine()
stt = VoiceEngineSTTAdapter(stt_provider)

events = []

stt.start_turn(
    session_id="S1",
    turn_id="T1",
    on_partial=lambda text: events.append(("partial", text)),
    on_final=lambda text: events.append(("final", text)),
    on_error=lambda err: events.append(("error", err)),
)

assert stt.submit_audio(turn_id="T1", audio=b"fake-audio") is True
assert stt_provider.transcribe_calls == [b"fake-audio"]
assert events == [("final", "bonjour aura")]
assert all(kind != "partial" for kind, _ in events)

# Dict result normalization.
stt_provider.mode = "dict"
events.clear()
stt.start_turn(
    session_id="S1",
    turn_id="T2",
    on_partial=lambda text: events.append(("partial", text)),
    on_final=lambda text: events.append(("final", text)),
    on_error=lambda err: events.append(("error", err)),
)
assert stt.submit_audio(turn_id="T2", audio="A2") is True
assert events == [("final", "dict transcript")]

# Empty transcript fails closed.
stt_provider.mode = "empty"
events.clear()
stt.start_turn(
    session_id="S1",
    turn_id="T3",
    on_partial=lambda text: events.append(("partial", text)),
    on_final=lambda text: events.append(("final", text)),
    on_error=lambda err: events.append(("error", err)),
)
assert stt.submit_audio(turn_id="T3", audio="A3") is False
assert events == [("error", "empty_transcript")]

# Provider exception fails closed.
stt_provider.mode = "raise"
events.clear()
stt.start_turn(
    session_id="S1",
    turn_id="T4",
    on_partial=lambda text: events.append(("partial", text)),
    on_final=lambda text: events.append(("final", text)),
    on_error=lambda err: events.append(("error", err)),
)
assert stt.submit_audio(turn_id="T4", audio="A4") is False
assert events == [("error", "transcribe_error:RuntimeError")]

# Cancel path prefers cancel_listening and removes pending callback state.
stt_provider.mode = "ok"
events.clear()
stt.start_turn(
    session_id="S1",
    turn_id="T5",
    on_partial=lambda text: events.append(("partial", text)),
    on_final=lambda text: events.append(("final", text)),
    on_error=lambda err: events.append(("error", err)),
)
stt.cancel(turn_id="T5", reason="barge_in")
assert stt_provider.cancel_calls == 1
assert stt.submit_audio(turn_id="T5", audio="stale") is False
assert events == []

# Fallback cancellation uses stop_listening if cancel_listening is absent.
stop_only = FakeVoiceEngineStopOnly()
stt_stop_only = VoiceEngineSTTAdapter(stop_only)
stt_stop_only.start_turn(
    session_id="S2",
    turn_id="T6",
    on_partial=lambda text: None,
    on_final=lambda text: None,
    on_error=lambda err: None,
)
stt_stop_only.cancel(turn_id="T6", reason="stop")
assert stop_only.stop_calls == 1

# Warmup is explicit only; constructor never triggers it.
assert stt_provider.warmup_calls == 0
assert stt.warmup() is True
assert stt_provider.warmup_calls == 1

# Capability contract from R8 limitation.
assert stt.capabilities.supports_partial is False
assert stt.capabilities.supports_final is True
assert stt.capabilities.supports_cancel is True
assert stt.capabilities.runtime_certified is False

# ------------------------------------------------------------------
# TTS adapter: speak/stop/warmup mapping, no fabricated first-audio callbacks.
# ------------------------------------------------------------------
tts_provider = FakeTTS()
tts = TextToSpeechAdapter(tts_provider)

tts_events = []
tts.speak(
    session_id="S1",
    turn_id="T7",
    text="Réponse AURA",
    on_first_chunk=lambda: tts_events.append("first_chunk"),
    on_playback_started=lambda: tts_events.append("playback_started"),
    on_completed=lambda: tts_events.append("completed"),
    on_error=lambda err: tts_events.append(("error", err)),
)

assert tts_provider.spoken == ["Réponse AURA"]
assert tts_events == ["completed"]
assert "first_chunk" not in tts_events
assert "playback_started" not in tts_events

tts.cancel(turn_id="T7", reason="barge_in")
assert tts_provider.stop_calls == 1

assert tts_provider.warmup_calls == 0
assert tts.warmup() is True
assert tts_provider.warmup_calls == 1

assert tts.capabilities.supports_cancel is True
assert tts.capabilities.supports_precise_first_audio_callback is False
assert tts.capabilities.runtime_certified is False
assert tts.capabilities.live_audio_certified is False

# Empty text fails closed without calling provider.
tts_events.clear()
tts.speak(
    session_id="S1",
    turn_id="T8",
    text="   ",
    on_first_chunk=lambda: tts_events.append("first_chunk"),
    on_playback_started=lambda: tts_events.append("playback_started"),
    on_completed=lambda: tts_events.append("completed"),
    on_error=lambda err: tts_events.append(("error", err)),
)
assert tts_events == [("error", "empty_tts_text")]
assert tts_provider.spoken == ["Réponse AURA"]

# Provider exception maps to error callback only.
tts_provider.mode = "raise"
tts_events.clear()
tts.speak(
    session_id="S1",
    turn_id="T9",
    text="fail",
    on_first_chunk=lambda: tts_events.append("first_chunk"),
    on_playback_started=lambda: tts_events.append("playback_started"),
    on_completed=lambda: tts_events.append("completed"),
    on_error=lambda err: tts_events.append(("error", err)),
)
assert tts_events == [("error", "speak_error:RuntimeError")]

# ------------------------------------------------------------------
# Static guard: adapter module must never import the concrete providers or I/O.
# ------------------------------------------------------------------
module_path = ROOT / "voice" / "live_voice_real_provider_adapters_v220.py"
source = module_path.read_text(encoding="utf-8", errors="ignore")
tree = ast.parse(source, filename=str(module_path))

imports = set()
call_names = set()

for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.add(alias.name.casefold())
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            imports.add(node.module.casefold())
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            call_names.add(node.func.id.casefold())
        elif isinstance(node.func, ast.Attribute):
            call_names.add(node.func.attr.casefold())

for forbidden in (
    "voice.voice_engine",
    "voice.text_to_speech",
    "sounddevice",
    "pyaudio",
    "requests",
    "httpx",
    "subprocess",
    "socket",
    "torch",
    "whisper",
):
    assert forbidden not in imports, forbidden

for forbidden_call in (
    "sleep",
    "monotonic",
    "perf_counter",
):
    assert forbidden_call not in call_names, forbidden_call

print("[PASS] AURA v2.2 R9 thin real-provider adapter invariant")
print("[PASS] voice_engine STT maps transcribe(audio) to FINAL transcript only")
print("[PASS] adapter does not fabricate STT partials")
print("[PASS] empty/error STT results fail closed")
print("[PASS] STT cancellation prefers cancel_listening with stop_listening fallback")
print("[PASS] text_to_speech maps speak/stop/warmup without constructing provider")
print("[PASS] TTS adapter does not fabricate first-audio/playback milestones")
print("[PASS] provider exceptions map to error callback")
print("[PASS] real provider modules are not imported")
print("[PASS] no real microphone/audio/network/model/provider I/O")
