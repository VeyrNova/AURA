from pathlib import Path
import py_compile

root = Path(__file__).resolve().parents[1]
shader_path = root / 'ui' / 'opengl_orb_surface.py'
orb_path = root / 'ui' / 'orb_widget.py'

checks = {}
for path in (shader_path, orb_path):
    py_compile.compile(str(path), doraise=True)
    checks[f'compile:{path.name}'] = True

shader = shader_path.read_text(encoding='utf-8')
orb = orb_path.read_text(encoding='utf-8')

checks.update({
    'visual_core_v21': 'Visual Core V21 Neural Hubs + Depth Base' in shader,
    'hub_link_function': 'float hubLink(' in shader,
    'hub_branch_function': 'float hubBranches(' in shader,
    'six_gpu_hubs': all(f'vec2 h{i} =' in shader for i in range(1,7)),
    'route_to_hub_speaking': 'routeFlow*1.30' in shader and 'hubFlow*1.55' in shader,
    'explicit_hub_render': 'float hubCore =' in shader and 'float hubActive =' in shader,
    'strict_containment_kept': 'float filamentContain = 1.0 - smoothstep(0.945, 0.982, sphereNorm);' in shader,
    'six_base_rings': 'float er6 =' in shader and 'ringBand(er6,1.0,0.040)' in shader,
    'base_raised_gpu': 'float baseY = p.y + neuralRadius*1.10;' in shader,
    'six_fallback_hubs': 'hub_pts = [' in orb and orb.count('QPointF(cx') >= 6,
    'fallback_curved_routes': 'path.cubicTo(c1,c2,b)' in orb,
    'fallback_no_master_random': 'master_edge = False' in orb,
    'base_raised_fallback': 'y = cy + radius*1.08' in orb and 'base_y = cy + radius * 1.16' in orb,
})

# Structural shader string checks (not a GPU runtime compile).
checks['shader_braces_balanced'] = shader.count('{') == shader.count('}')
checks['shader_parentheses_balanced'] = shader.count('(') == shader.count(')')
checks['old_patch18_master_vars_removed'] = not any(x in shader for x in (
    'masterFrontA','masterFrontB','masterFrontC','masterMidA','masterMidB','masterBackA','masterBackB'
))

print('=== PATCH UI 19 DIAGNOSTICS ===')
failed = []
for name, ok in checks.items():
    print(f'[{"PASS" if ok else "FAIL"}] {name}')
    if not ok:
        failed.append(name)
print(f'PASS={len(checks)-len(failed)}/{len(checks)}')
if failed:
    raise SystemExit('Failed: ' + ', '.join(failed))
