
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "voice" / "live_voice_canonical_ingress_bridge_v220.py"


source = TARGET.read_text(encoding="utf-8")
tree = ast.parse(source, filename=str(TARGET))

forbidden = {
    "socket",
    "subprocess",
    "requests",
    "httpx",
    "urllib",
    "sounddevice",
    "pyaudio",
    "winsound",
    "sqlite3",
}

for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            assert alias.name.split(".")[0] not in forbidden
    elif isinstance(node, ast.ImportFrom) and node.module:
        assert node.module.split(".")[0] not in forbidden

assert "class LiveVoiceCanonicalIngressBridge" in source

constant_values = {}
for node in tree.body:
    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ):
        constant_values[node.targets[0].id] = node.value.value

assert constant_values.get("SESSION_METHOD") == "stt_final"
assert constant_values.get("CORE_METHOD") == "try_handle_intent"

spec = importlib.util.spec_from_file_location(
    "aura_r17_r1_bridge",
    str(TARGET),
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class SessionSpy:
    def __init__(self, log):
        self.log = log

    def stt_final(self, *, turn_id, text):
        self.log.append(
            (
                "session",
                str(turn_id),
                str(text),
            )
        )
        return "SESSION_OK"


class CoreSpy:
    def __init__(self, log):
        self.log = log

    def try_handle_intent(self, *, text):
        self.log.append(
            (
                "core",
                str(text),
            )
        )
        return "CORE_OK"


log = []
bridge = module.LiveVoiceCanonicalIngressBridge(
    live_session=SessionSpy(log),
    aura_core=CoreSpy(log),
)

result = bridge.deliver_final_text(
    turn_id="R17-R1-T1",
    text="  Bonjour AURA  ",
)

assert result.text == "Bonjour AURA"
assert result.turn_id == "R17-R1-T1"
assert result.session_result == "SESSION_OK"
assert result.core_result == "CORE_OK"
assert log == [
    ("session", "R17-R1-T1", "Bonjour AURA"),
    ("core", "Bonjour AURA"),
]

log2 = []
bridge2 = module.LiveVoiceCanonicalIngressBridge(
    live_session=SessionSpy(log2),
    aura_core=CoreSpy(log2),
)

try:
    bridge2.deliver_final_text(
        turn_id="R17-R1-T2",
        text="   ",
    )
    raise AssertionError("blank final text must fail closed")
except ValueError:
    pass

assert log2 == []

class FailingSession:
    def stt_final(self, *, turn_id, text):
        raise RuntimeError("SESSION_FAIL")

class MustNotRunCore:
    def try_handle_intent(self, *, text):
        raise AssertionError("core must not run after session boundary failure")

bridge3 = module.LiveVoiceCanonicalIngressBridge(
    live_session=FailingSession(),
    aura_core=MustNotRunCore(),
)
try:
    bridge3.deliver_final_text(
        turn_id="R17-R1-T3",
        text="Bonjour",
    )
    raise AssertionError("session failure must propagate")
except RuntimeError as exc:
    assert str(exc) == "SESSION_FAIL"

print("[PASS] AURA v2.2 R17-R1 canonical ingress bridge invariant")
print("[PASS] stateless router / no device, provider, persistence or network authority")
print("[PASS] order = LiveVoiceSession final boundary -> AuraCore ingress boundary")
print("[PASS] exactly-once synthetic delivery")
print("[PASS] blank text and session failure fail closed")
