from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
CORE = ROOT / "core" / "aura_core.py"
text = CORE.read_text(encoding="utf-8")
tree = ast.parse(text)
compile(text, str(CORE), "exec")

# Import contract: exactly one composition-factory import.
factory_imports = []
for node in tree.body:
    if isinstance(node, ast.ImportFrom) and node.module == "runtime.aura_intelligence_gateway_composition_v3":
        names = [a.name for a in node.names]
        if "build_production_intelligence_gateway_v3" in names:
            factory_imports.append(node)
assert len(factory_imports) == 1, factory_imports

# Resolve AuraCore.__init__.
aura_cls = next(
    n for n in tree.body
    if isinstance(n, ast.ClassDef) and n.name == "AuraCore"
)
init = next(
    n for n in aura_cls.body
    if isinstance(n, ast.FunctionDef) and n.name == "__init__"
)

def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    return ""

assignments = []
factory_calls = []
gateway_execute_calls = []
fabric_build_calls = []
hardware_calls = []

for node in ast.walk(init):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            assignments.append((dotted(target), node.lineno, dotted(node.value)))
    elif isinstance(node, ast.AnnAssign):
        assignments.append((dotted(node.target), node.lineno, dotted(node.value)))
    elif isinstance(node, ast.Call):
        name = dotted(node.func)
        if name.endswith("build_production_intelligence_gateway_v3"):
            factory_calls.append(node)
        if name.endswith("intelligence_gateway_v3.execute") or name.endswith("gateway.execute"):
            gateway_execute_calls.append(node)
        if name.endswith("build_production_service"):
            fabric_build_calls.append(node)
        if name.endswith("HardwareCapabilityServiceV3"):
            hardware_calls.append(node)

hardware_assign = [
    row for row in assignments if row[0] == "self.hardware_capabilities"
]
composition_assign = [
    row for row in assignments if row[0] == "self.intelligence_gateway_composition_v3"
]
gateway_assign = [
    row for row in assignments if row[0] == "self.intelligence_gateway_v3"
]

assert len(hardware_assign) == 1, hardware_assign
assert len(composition_assign) == 1, composition_assign
assert len(gateway_assign) == 1, gateway_assign
assert len(hardware_calls) == 1, hardware_calls
assert len(factory_calls) == 1, factory_calls

hardware_line = hardware_assign[0][1]
composition_line = composition_assign[0][1]
gateway_line = gateway_assign[0][1]

assert hardware_line < composition_line < gateway_line
assert composition_assign[0][2].endswith("build_production_intelligence_gateway_v3")
assert gateway_assign[0][2].endswith("self.intelligence_gateway_composition_v3.gateway")

# Factory call must use the already-owned HCS facade.
factory = factory_calls[0]
kwargs = {kw.arg: dotted(kw.value) for kw in factory.keywords}
assert kwargs.get("capability_service") == "self.hardware_capabilities", kwargs

# Constructor must bind only; it must not execute the gateway or construct Fabric.
assert not gateway_execute_calls, gateway_execute_calls
assert not fabric_build_calls, fabric_build_calls

# No duplicate canonical runtime owners.
owner_targets = {
    "self.llm_manager": 0,
    "self.resource_guardian": 0,
    "self.hardware_capabilities": 0,
    "self.intelligence_gateway_composition_v3": 0,
    "self.intelligence_gateway_v3": 0,
}
for target, _, _ in assignments:
    if target in owner_targets:
        owner_targets[target] += 1
assert all(v == 1 for v in owner_targets.values()), owner_targets

# Composition must remain independent from AuraCore/MainWindow.
COMP = ROOT / "runtime" / "aura_intelligence_gateway_composition_v3.py"
comp_text = COMP.read_text(encoding="utf-8")
comp_tree = ast.parse(comp_text)
for node in ast.walk(comp_tree):
    if isinstance(node, ast.ImportFrom):
        module = (node.module or "").casefold()
        assert module != "core.aura_core"
        assert "main_window" not in module and "mainwindow" not in module
    elif isinstance(node, ast.Import):
        for alias in node.names:
            module = alias.name.casefold()
            assert module != "core.aura_core"
            assert "main_window" not in module and "mainwindow" not in module

print("PASS AURA v3 AuraCore IntelligenceGatewayV3 wiring invariant")
