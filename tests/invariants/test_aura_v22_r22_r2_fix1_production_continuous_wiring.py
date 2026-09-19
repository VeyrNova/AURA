from __future__ import annotations

from pathlib import Path
import ast
import hashlib

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "ui" / "main_window.py"
AUTOMIC = ROOT / "voice" / "live_voice_automatic_microphone_runtime_v220.py"
INGRESS = ROOT / "voice" / "live_voice_microphone_ingress_v220.py"
PTT = ROOT / "voice" / "microphone.py"
VOICE_ENGINE = ROOT / "voice" / "voice_engine.py"
CONTROLLER = ROOT / "voice" / "live_voice_continuous_turn_controller_v220.py"
PRECONDITIONER = ROOT / "voice" / "live_voice_microphone_preconditioner_v220.py"

EXPECTED = {
    AUTOMIC: "016d0c06c00eb66c2432eb3081ae2b9c6cb827eb198ed5204f215e10de05b63f",
    INGRESS: "81cb863f21e26a04330dce60d7ea027b625e2778b3c56bf23f6656d73e08dc17",
    PTT: "c4a3d811de7eee7b56599c509313316a6c3f3d845d36d1381054c075ff0ea27f",
    VOICE_ENGINE: "f59310277feed54eb6cabfadb63c81d210179928681610b2f50e6c3dd5320469",
    CONTROLLER: "a0e09f691f7dddca15cc1c86bbb0e46820dd3e43b9b64580d270a9f4355ab013",
    PRECONDITIONER: "348bc22107eae7cebd6f280d7d910596cfeb814d6a12e58ddc43e2e2c933ab37",
}

def sha(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

for path, expected in EXPECTED.items():
    assert sha(path) == expected, (path, sha(path), expected)

src = MAIN.read_text(encoding="utf-8-sig")
tree = ast.parse(src)

for marker in (
    "# AURA_R22_R2_FIX1_CONTINUOUS_RELAY",
    "# AURA_R22_R2_FIX1_CONTINUOUS_METHODS",
    "# AURA_R22_R2_FIX1_WIRE_AFTER_ACTUAL_RUNTIME_ASSIGNMENT",
    "# AURA_R22_R2_FIX1_PTT_CANCEL_PENDING_CONTINUOUS",
):
    assert src.count(marker) == 1, (marker, src.count(marker))

classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
assert "_AURAR22ContinuousVoiceFinalizedAudioRelay" in classes
relay_src = ast.get_source_segment(
    src, classes["_AURAR22ContinuousVoiceFinalizedAudioRelay"]
) or ""
assert "Signal(object)" in relay_src

main = classes["MainWindow"]
methods = {
    n.name: n
    for n in main.body
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
}

for name in (
    "_setup_automatic_microphone_runtime",
    "_wire_live_voice_continuous_turn_controller",
    "_on_live_voice_continuous_audio_finalized",
    "_suspend_automatic_microphone_for_ptt",
    "_on_stt_finished",
    "_on_user_message",
):
    assert name in methods, name

setup_src = ast.get_source_segment(
    src, methods["_setup_automatic_microphone_runtime"]
) or ""
wire_src = ast.get_source_segment(
    src, methods["_wire_live_voice_continuous_turn_controller"]
) or ""
final_src = ast.get_source_segment(
    src, methods["_on_live_voice_continuous_audio_finalized"]
) or ""
suspend_src = ast.get_source_segment(
    src, methods["_suspend_automatic_microphone_for_ptt"]
) or ""
finished_src = ast.get_source_segment(
    src, methods["_on_stt_finished"]
) or ""

assert "LiveVoiceAutomaticMicrophoneRuntime(" in setup_src
assert "self._automatic_microphone_runtime = runtime" in setup_src
assert "self._wire_live_voice_continuous_turn_controller()" in setup_src
assert setup_src.index("self._automatic_microphone_runtime = runtime") < setup_src.index(
    "self._wire_live_voice_continuous_turn_controller()"
)

assert "ContinuousVoiceTurnController(" in wire_src
assert "DeterministicTurnEndDetector()" in wire_src
assert "ProviderNeutralMicrophonePreconditioner()" in wire_src
assert 'getattr(decision, "action"' in wire_src
assert '"COMMIT"' in wire_src
assert "result.audio" in wire_src
assert "snapshot_chunks" in wire_src
assert "leading_silence_seconds" in wire_src
assert "existing_start" in wire_src
assert "controller.on_speech_started" in wire_src
assert "controller.on_audio_chunk" in wire_src
assert "controller.on_speech_ended" in wire_src
assert "ingress._on_speech_started = _r22_speech_started" in wire_src
assert "ingress._on_audio_chunk = _r22_audio_chunk" in wire_src
assert "ingress._on_speech_ended = _r22_speech_ended" in wire_src

assert "STTWorker(self.aura_core, audio)" in final_src
assert "self._stt_worker.finished.connect(self._on_stt_finished)" in final_src
assert "self._stt_worker.failed.connect(self._on_stt_failed)" in final_src
assert "self._stt_thread.finished.connect(self._cleanup_stt_thread)" in final_src
assert "QTimer.singleShot(12000, self._stt_watchdog_tick)" in final_src

assert 'controller.cancel("ptt_priority")' in suspend_src
assert "self._stop_automatic_microphone_runtime()" in suspend_src
assert "self._on_user_message" in finished_src

assert "LiveVoiceSession(" not in src
assert "LiveVoiceProviderBindings(" not in src

print("[PASS] R22-R2-FIX1 actual AutoMic setup anchor resolved")
print("[PASS] R22-R2-FIX1 controller wired after _automatic_microphone_runtime assignment")
print("[PASS] R22-R2-FIX1 existing automatic barge callback preserved")
print("[PASS] R22-R2-FIX1 continuous chunks/end feed subordinate controller")
print("[PASS] R22-R2-FIX1 certified preconditioner uses real .audio result")
print("[PASS] R22-R2-FIX1 Qt relay reuses existing STTWorker")
print("[PASS] R22-R2-FIX1 existing _on_stt_finished -> _on_user_message preserved")
print("[PASS] R22-R2-FIX1 PTT cancels pending automatic utterance")
print("[PASS] R22-R2-FIX1 protected voice neighbors unchanged")
print("[PASS] R22-R2-FIX1 no second LiveVoiceSession/ProviderBindings authority")
