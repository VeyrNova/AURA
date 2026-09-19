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

worker = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "LLMWorker"), None)
assert worker is not None
run = next(
    (n for n in worker.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "run"),
    None,
)
assert run is not None

consume = next(
    (
        n for n in ast.walk(run)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n is not run
        and n.name == "consume_stream"
    ),
    None,
)
assert consume is not None

# v3 call remains exactly one and legacy Fabric generation is gone from worker.
run_src = ast.get_source_segment(text, run) or ""
assert run_src.count("generate_conversation_v3(") == 1
assert "generate_conversation_fabric(" not in run_src

# Both bridge helpers are imported once in outer LLMWorker.run scope only.
outer_imports = []
nested_ranges = [
    (n.lineno, getattr(n, "end_lineno", n.lineno))
    for n in ast.walk(run)
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not run
]
def in_nested(line):
    return any(s <= line <= e for s, e in nested_ranges)

for n in ast.walk(run):
    if (
        isinstance(n, ast.ImportFrom)
        and n.module == "runtime.aura_conversation_fabric_bridge"
        and not in_nested(n.lineno)
    ):
        outer_imports.append(n)

assert len(outer_imports) == 1, len(outer_imports)
assert {a.name for a in outer_imports[0].names} == {
    "apply_fabric_result_to_profile",
    "fabric_metrics_from_result",
}

# fabric_result must exist in outer scope before consume_stream.
outer_fabric_stores = [
    n for n in ast.walk(run)
    if isinstance(n, ast.Name)
    and n.id == "fabric_result"
    and isinstance(n.ctx, ast.Store)
    and not in_nested(n.lineno)
]
assert len(outer_fabric_stores) == 1, [n.lineno for n in outer_fabric_stores]

# consume_stream must explicitly close over fabric_result.
nonlocals = [n for n in ast.walk(consume) if isinstance(n, ast.Nonlocal)]
assert any("fabric_result" in n.names for n in nonlocals)

# Existing post-processing and metrics contracts remain.
assert "apply_fabric_result_to_profile(profile, fabric_result)" in run_src
assert "fabric_metrics_from_result(fabric_result, profile)" in run_src
assert "self.aura_core.llm_manager.generate_stream(" in run_src

print("PASS AURA v3 LLMWorker Fabric result/helper scope invariant")
