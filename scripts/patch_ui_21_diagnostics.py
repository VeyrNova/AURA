from pathlib import Path
import hashlib

root = Path(__file__).resolve().parents[1]
gl_path = root / 'ui' / 'opengl_orb_surface.py'
orb_path = root / 'ui' / 'orb_widget.py'
gl = gl_path.read_text(encoding='utf-8')

checks = {
    'opengl_surface_exists': gl_path.exists(),
    'orb_widget_exists': orb_path.exists(),
    'volumetric_layer_function': 'float volumetricFilamentLayer(' in gl,
    'front_layer': 'float frontLayer = volumetricFilamentLayer(' in gl,
    'mid_layer': 'float midLayer   = volumetricFilamentLayer(' in gl,
    'back_layer': 'float backLayer  = volumetricFilamentLayer(' in gl,
    'micro_field_no_runtime_calls': gl.count('microDendriteField(') == 1,
    'bezier_five_segments': 'for (int i=1; i<=5; ++i)' in gl and 'float(i)/5.0' in gl,
    'anchor_nodes_40': 'for (int i = 0; i < 40; ++i)' in gl,
    'small_hub_halo': 'neuralHub(frontP,h1,0.052)' in gl,
    'balanced_braces': gl.count('{') == gl.count('}'),
    'balanced_parentheses': gl.count('(') == gl.count(')'),
}

print('=== PATCH UI 21 DIAGNOSTICS ===')
failed = False
for name, ok in checks.items():
    print(f'[{"PASS" if ok else "FAIL"}] {name}')
    failed |= not ok

if failed:
    raise SystemExit(1)
print(f'PASS {sum(checks.values())}/{len(checks)}')
