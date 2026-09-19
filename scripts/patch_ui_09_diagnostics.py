from pathlib import Path

root = Path(__file__).resolve().parents[1]
shader = (root/'ui'/'opengl_orb_surface.py').read_text(encoding='utf-8')
orb = (root/'ui'/'orb_widget.py').read_text(encoding='utf-8')
checks = {
    'v15_shader': 'V15 Neural Cortex Reference Match' in shader,
    'curved_dendrites': 'Major dendritic trunks' in shader and 'ridgeContour' in shader,
    'no_segment_distance': 'segmentDistance' not in shader,
    'no_point_to_point_partner': 'float partner' not in shader,
    'front_back_cortex': 'frontFibres' in shader and 'backFibres' in shader,
    'junction_particles': 'junctionAffinity' in shader and 'synapseNode' in shader,
    'speaking_curved_activation': 'hotFlow' in shader and 'speakingGate' in shader,
    'strong_holographic_pool': 'poolRings' in shader and 'er5' in shader,
    'logo_reference_treatment': 'PATCH 09: preserve the canonical OPEN' in orb,
    'logo_geometry_preserved': '_master_path' in orb and 'master_symbol_path' in orb,
}
failed = [k for k,v in checks.items() if not v]
for k,v in checks.items():
    print(f"{k}: {'PASS' if v else 'FAIL'}")
if failed:
    print('FAILED:', ', '.join(failed))
    raise SystemExit(1)
print(f'Patch 09 diagnostics: {len(checks)}/{len(checks)} PASS')
