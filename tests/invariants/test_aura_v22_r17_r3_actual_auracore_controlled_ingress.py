
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "core" / "aura_core.py"
BRIDGE = ROOT / "voice" / "live_voice_canonical_ingress_bridge_v220.py"
SESSION = ROOT / "voice" / "live_voice_session_v220.py"


def class_method(path: Path, class_name: str, method_name: str):
    source = path.read_text(encoding="utf-8", errors="strict")
    tree = ast.parse(source, filename=str(path))

    cls = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == class_name
        ),
        None,
    )
    assert cls is not None, class_name

    method = next(
        (
            node
            for node in cls.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == method_name
        ),
        None,
    )
    assert method is not None, method_name
    return method


core_method = class_method(
    CORE,
    "AuraCore",
    "try_handle_intent",
)

assert not isinstance(core_method, ast.AsyncFunctionDef)

positional = (
    list(core_method.args.posonlyargs)
    + list(core_method.args.args)
)
names = [
    item.arg
    for item in positional
    if item.arg != "self"
]
kwonly = [
    item.arg
    for item in core_method.args.kwonlyargs
]

assert "text" in names + kwonly
assert "allow_grounding" in names + kwonly

session_final = class_method(
    SESSION,
    "LiveVoiceSession",
    "stt_final",
)
session_commit = class_method(
    SESSION,
    "LiveVoiceSession",
    "commit_turn",
)

assert session_final.lineno < session_commit.lineno

bridge_source = BRIDGE.read_text(
    encoding="utf-8",
    errors="strict",
)

assert "LiveVoiceCanonicalIngressBridge" in bridge_source
assert "try_handle_intent" in bridge_source
assert "stt_final" in bridge_source

print("[PASS] AURA v2.2 R17-R3 actual AuraCore controlled-ingress invariant")
print("[PASS] AuraCore.try_handle_intent remains synchronous")
print("[PASS] text and allow_grounding parameters remain available")
print("[PASS] LiveVoiceSession evidenced final-before-commit contract remains present")
print("[PASS] retained canonical bridge still targets stt_final -> try_handle_intent")
