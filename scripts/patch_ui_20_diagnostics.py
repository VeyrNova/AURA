from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
shader_path = root / 'ui' / 'opengl_orb_surface.py'
orb_path = root / 'ui' / 'orb_widget.py'
shader = shader_path.read_text(encoding='utf-8')
orb = orb_path.read_text(encoding='utf-8')

checks = {
    'visual_core_v22': 'Visual Core V22 Dense Neural Cortex' in shader,
    'micro_dendrite_function': 'float microDendriteField(' in shader,
    'front_micro_a': 'frontMicroA = microDendriteField' in shader,
    'front_micro_b': 'frontMicroB = microDendriteField' in shader,
    'mid_micro_a': 'midMicroA   = microDendriteField' in shader,
    'back_micro_a': 'backMicroA  = microDendriteField' in shader,
    'six_arm_hub_field': 'vec2 r5 = rotate2(l,a0+5.25);' in shader,
    'smaller_shader_hubs': 'neuralHub(frontP,h1,0.035)' in shader,
    'denser_shader_nodes': 'nodeGrid = (s + vec2(1.15)) * 37.0' in shader,
    'more_anchor_synapses': 'for (int i = 0; i < 56; ++i)' in shader,
    'shader_containment_kept': 'filamentContain' in shader and '0.982' in shader,
    'waveform_kept': 'Reference waveform sits behind the orb instead of cutting it in half.' in shader,
    'holographic_base_kept': '// ------------------------------------------------ holographic neural pool' in shader,
    'fallback_nodes_520': 'total = 520' in orb,
    'fallback_dense_budget': 'int(18 + 18*links)' in orb,
    'fallback_three_neighbors': 'targets = candidates[:3]' in orb,
    'fallback_smaller_hubs': 'radius*(.013+.008*act)' in orb,
    'fallback_six_arms': 'for arm in range(6):' in orb,
    'fallback_tertiary_twigs': 'tertiary twig from the secondary arm' in orb,
    'fallback_containment_kept': 'radius*.975, radius*.975' in orb,
}

failed = []
print('=== PATCH UI 20 DIAGNOSTICS ===')
for name, ok in checks.items():
    print(f'[{"PASS" if ok else "FAIL"}] {name}')
    if not ok:
        failed.append(name)

# Lightweight structural sanity checks for the embedded GLSL source.
for opening, closing, name in [('{','}','glsl_braces'),('(',')','glsl_parentheses'),('[',']','glsl_brackets')]:
    ok = shader.count(opening) == shader.count(closing)
    print(f'[{"PASS" if ok else "FAIL"}] {name}')
    if not ok:
        failed.append(name)

if failed:
    print('FAILED:', ', '.join(failed))
    raise SystemExit(1)
print(f'Patch 20 diagnostics: PASS ({len(checks)+3}/{len(checks)+3})')
