from pathlib import Path
import ast

root = Path(__file__).resolve().parents[1]
gl_path = root / "ui" / "opengl_orb_surface.py"
orb_path = root / "ui" / "orb_widget.py"
gl_text = gl_path.read_text(encoding="utf-8")
orb_text = orb_path.read_text(encoding="utf-8")

checks = {
    "visual_core_v20": "Visual Core V20 Neural Hierarchy + Holographic Base" in gl_text,
    "master_axon_function": "float masterAxon(" in gl_text,
    "master_branch_function": "float masterBranch(" in gl_text,
    "seven_master_paths": all(k in gl_text for k in ["masterFrontA", "masterFrontB", "masterFrontC", "masterMidA", "masterMidB", "masterBackA", "masterBackB"]),
    "master_flow": "float masterFlow" in gl_text,
    "junction_hierarchy": "masterFrontA*masterFrontB" in gl_text,
    "strict_containment": "float filamentContain = 1.0 - smoothstep(0.945, 0.982, sphereNorm);" in gl_text,
    "holographic_pool_core": "float poolCore" in gl_text and "float verticalReflect" in gl_text,
    "fallback_master_edges": "master_edge =" in orb_text,
    "fallback_secondary_bifurcation": "Secondary bifurcation attached to the same master axon" in orb_text,
    "fallback_junction_nodes": "Bright synaptic junction at the bifurcation" in orb_text,
    "fallback_six_base_rings": "(.30, .020, 48)" in orb_text,
    "boot_logo_untouched": "self._visual_progress" in orb_text and "white_fill = self._stage(progress, 0.25, 0.60)" in orb_text and "color_phase = self._stage(progress, 0.84, 1.00)" in orb_text,
}

# Parse Python and extract GLSL to ensure the embedded source is structurally balanced.
ast.parse(gl_text)
ast.parse(orb_text)
module = ast.parse(gl_text)
fragment = None
for node in module.body:
    if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "FRAGMENT_SHADER" for t in node.targets):
        fragment = ast.literal_eval(node.value)
        break
checks["fragment_shader_present"] = bool(fragment)
if fragment:
    checks["glsl_braces_balanced"] = fragment.count("{") == fragment.count("}")
    checks["glsl_parentheses_balanced"] = fragment.count("(") == fragment.count(")")
else:
    checks["glsl_braces_balanced"] = False
    checks["glsl_parentheses_balanced"] = False

failed = []
print("=== PATCH UI 18 DIAGNOSTICS ===")
for name, ok in checks.items():
    print(f"[{ 'PASS' if ok else 'FAIL' }] {name}")
    if not ok:
        failed.append(name)
if failed:
    raise SystemExit(f"Patch 18 diagnostics failed: {', '.join(failed)}")
print(f"Patch 18 diagnostics: {len(checks)}/{len(checks)} PASS")
