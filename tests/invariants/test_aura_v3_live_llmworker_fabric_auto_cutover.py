from __future__ import annotations

from pathlib import Path
import ast

ROOT = Path(r"C:\AURA GPT version")
MAIN = ROOT / "ui" / "main_window.py"

text = MAIN.read_text(encoding="utf-8", errors="strict")
tree = ast.parse(text)

def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    return ""

def get_class(name):
    return next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name), None)

def get_method(cls, name):
    if cls is None:
        return None
    return next(
        (n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name),
        None,
    )

worker = get_class("LLMWorker")
assert worker is not None
init = get_method(worker, "__init__")
run = get_method(worker, "run")
assert init is not None
assert run is not None

args = [a.arg for a in init.args.args]
assert args[:3] == ["self", "aura_core", "messages"], args

stored_core = False
for node in ast.walk(init):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if dotted(target) == "self.aura_core" and dotted(node.value) == "aura_core":
                stored_core = True
assert stored_core

v3_calls = [
    n for n in ast.walk(run)
    if isinstance(n, ast.Call) and dotted(n.func).endswith("generate_conversation_v3")
]
legacy_calls = [
    n for n in ast.walk(run)
    if isinstance(n, ast.Call) and dotted(n.func).endswith("generate_conversation_fabric")
]
assert len(v3_calls) == 1, len(v3_calls)
assert len(legacy_calls) == 0, len(legacy_calls)

call = v3_calls[0]
assert len(call.args) >= 2
assert dotted(call.args[0]) == "self.aura_core"
assert dotted(call.args[1]) == "generation_messages"
keywords = {kw.arg: kw.value for kw in call.keywords if kw.arg}
assert "profile" in keywords
assert dotted(keywords["profile"]) == "profile"
assert "voice_response" in keywords
voice_src = ast.get_source_segment(text, keywords["voice_response"]) or ""
assert "self.voice_response" in voice_src

# The adapter import must be local to LLMWorker.run/fabric_auto so startup
# ownership/import order outside this path remains untouched.
local_adapter_imports = [
    n for n in ast.walk(run)
    if isinstance(n, ast.ImportFrom)
    and n.module == "runtime.aura_v3_conversation_route_adapter"
    and any(a.name == "generate_conversation_v3" for a in n.names)
]
assert len(local_adapter_imports) == 1

# Preserve the legacy post-processing contract after the v3 adapter result.
run_src = ast.get_source_segment(text, run) or ""
for required in (
    "apply_fabric_result_to_profile(profile, fabric_result)",
    "self.provider_changed.emit(actual_provider, actual_model)",
    'self.telemetry.emit("llm.fabric.route"',
    'self.telemetry.emit("llm.failover"',
    'stream_source = (str(fabric_result.get("text") or ""),)',
):
    assert required in run_src, required

# Preserve non-fabric branches and auxiliary correction/verification calls.
llm_generate_calls = [
    n for n in ast.walk(run)
    if isinstance(n, ast.Call) and dotted(n.func).endswith("llm_manager.generate")
]
llm_stream_calls = [
    n for n in ast.walk(run)
    if isinstance(n, ast.Call) and dotted(n.func).endswith("llm_manager.generate_stream")
]
assert len(llm_generate_calls) >= 2
assert len(llm_stream_calls) >= 1

# Both current construction sites must still inject the one existing AuraCore.
worker_instantiations = [
    n for n in ast.walk(tree)
    if isinstance(n, ast.Call) and dotted(n.func).endswith("LLMWorker")
]
assert len(worker_instantiations) == 2, len(worker_instantiations)
for node in worker_instantiations:
    assert node.args
    assert dotted(node.args[0]) == "self.aura_core", ast.get_source_segment(text, node)

print("PASS AURA v3 live LLMWorker fabric_auto cutover static invariant")
