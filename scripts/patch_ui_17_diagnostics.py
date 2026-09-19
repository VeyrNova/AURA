from pathlib import Path

root = Path(__file__).resolve().parents[1]
gl = (root / 'ui' / 'opengl_orb_surface.py').read_text(encoding='utf-8')
orb = (root / 'ui' / 'orb_widget.py').read_text(encoding='utf-8')

checks = {
    'visual_core_v19': 'Visual Core V19 Connected Synaptic Web Orb' in gl,
    'connected_bundle_function': 'float connectedBundle(' in gl,
    'bundle_twig_function': 'float bundleTwig(' in gl,
    'front_connected_web': 'float webFrontA = connectedBundle' in gl,
    'mid_connected_web': 'float webMidA = connectedBundle' in gl,
    'back_connected_web': 'float webBackA = connectedBundle' in gl,
    'web_junctions': 'float webJunctions =' in gl,
    'web_flow': 'float webFlow =' in gl,
    'strict_containment_kept': 'float filamentContain = 1.0 - smoothstep(0.945, 0.982, sphereNorm);' in gl,
    'fallback_connected_graph': 'PATCH 17 — connected synaptic web' in orb,
    'fallback_cubic_curves': 'path.cubicTo(ctrl1, ctrl2, end_pt)' in orb,
    'fallback_link_length_cap': 'max_link = radius * .34' in orb,
    'no_old_cross_sphere_drawline': 'p.drawLine(a, b)' not in orb,
    'stronger_pedestal': 'rings = ((1.18, .080, 104)' in orb,
}

failed = []
print('=== PATCH UI 17 DIAGNOSTICS ===')
for name, ok in checks.items():
    print(f'[{"PASS" if ok else "FAIL"}] {name}')
    if not ok:
        failed.append(name)

# Simple GLSL source sanity checks available without an OpenGL context.
frag = gl.split('FRAGMENT_SHADER = r"""', 1)[1].split('"""', 1)[0]
brace_balance = frag.count('{') == frag.count('}')
paren_balance = frag.count('(') == frag.count(')')
print(f'[{"PASS" if brace_balance else "FAIL"}] glsl_brace_balance')
print(f'[{"PASS" if paren_balance else "FAIL"}] glsl_parenthesis_balance')
if not brace_balance:
    failed.append('glsl_brace_balance')
if not paren_balance:
    failed.append('glsl_parenthesis_balance')

if failed:
    raise SystemExit('Patch 17 diagnostics failed: ' + ', '.join(failed))
print(f'Patch 17 diagnostics: PASS ({len(checks)+2}/{len(checks)+2})')
