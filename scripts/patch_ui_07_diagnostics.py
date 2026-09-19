from pathlib import Path

root = Path(__file__).resolve().parents[1]
orb = root / 'ui' / 'opengl_orb_surface.py'
text = orb.read_text(encoding='utf-8')
checks = {
    'patch07_docstring': 'V13 Volumetric Neural Orb' in text,
    'patch07_node_rotation': 'PATCH 07 — pseudo-3D orbit' in text,
    'patch07_internal_strata': 'PATCH 07 — internal strata' in text,
    'patch07_radius': 'float neuralRadius = 0.485' in text,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"{name}: {'PASS' if ok else 'FAIL'}")
if failed:
    raise SystemExit(1)
print('Patch 07 diagnostics: PASS')
