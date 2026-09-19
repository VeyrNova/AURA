from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
CORE = ROOT / "core" / "aura_core.py"
ADAPTER = ROOT / "runtime" / "aura_hardware_capability_service_v3.py"

text = CORE.read_text(encoding="utf-8")
tree = ast.parse(text)
compile(text, str(CORE), "exec")

def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    return ""

def fmap(tree):
    out = {}
    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack = []
        def visit_ClassDef(self, node):
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()
        def visit_FunctionDef(self, node):
            out[".".join(self.stack + [node.name])] = node
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()
    V().visit(tree)
    return out

imports = [
    n for n in tree.body
    if isinstance(n, ast.ImportFrom)
    and n.module == "runtime.aura_hardware_capability_service_v3"
    and any(a.name == "HardwareCapabilityServiceV3" for a in n.names)
]
assert len(imports) == 1, len(imports)

init = fmap(tree)["AuraCore.__init__"]
positions = {}
binding = None

for n in init.body:
    if isinstance(n, (ast.Assign, ast.AnnAssign)):
        targets = n.targets if isinstance(n, ast.Assign) else [n.target]
        for t in targets:
            q = dotted(t)
            if q in {"self.llm_manager", "self.resource_guardian", "self.hardware_capabilities"}:
                positions[q] = n.lineno
            if q == "self.hardware_capabilities":
                binding = n

assert positions["self.llm_manager"] < positions["self.resource_guardian"] < positions["self.hardware_capabilities"]
assert binding is not None
assert isinstance(binding.value, ast.Call)
assert dotted(binding.value.func) == "HardwareCapabilityServiceV3"
assert any(
    kw.arg == "aura_core"
    and isinstance(kw.value, ast.Name)
    and kw.value.id == "self"
    for kw in binding.value.keywords
)

init_source = ast.get_source_segment(text, init) or ""
assert "SystemService(" not in init_source

adapter_text = ADAPTER.read_text(encoding="utf-8")
adapter_tree = ast.parse(adapter_text)
for n in ast.walk(adapter_tree):
    if isinstance(n, ast.ImportFrom):
        mod = n.module or ""
        assert not mod.startswith("core.aura_core")
        assert not mod.startswith("services.core_bridge")
    elif isinstance(n, ast.Import):
        for a in n.names:
            assert not a.name.startswith("core.aura_core")
            assert not a.name.startswith("services.core_bridge")

print("PASS AURA v3 HardwareCapabilityServiceV3 AuraCore wiring invariant")
