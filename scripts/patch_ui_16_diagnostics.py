from pathlib import Path

root = Path(__file__).resolve().parents[1]
orb_path = root / 'ui' / 'orb_widget.py'
gl_path = root / 'ui' / 'opengl_orb_surface.py'
orb = orb_path.read_text(encoding='utf-8')
gl = gl_path.read_text(encoding='utf-8')

checks = {
    'orb_widget_exists': orb_path.exists(),
    'opengl_surface_exists': gl_path.exists(),
    'logo_uniform_white_morph': 'true morph from hollow outline to a solid white A' in orb,
    'logo_no_vertical_fill_clip': 'fill_top = bounds.bottom()' not in orb,
    'fallback_short_dendrites': 'short dendritic clusters instead of cross-sphere links' in orb,
    'fallback_cubic_branches': 'path.cubicTo(ctrl1, ctrl2, end_pt)' in orb,
    'fallback_no_old_partner_link': 'j = (i * 11 + 7' not in orb,
    'shader_v18': 'Visual Core V18 True Dendritic Cortex Orb' in gl,
    'shader_dendrite_cluster': 'float dendriteCluster(' in gl,
    'shader_front_mid_back': all(x in gl for x in ('float frontFibres', 'float midFibres', 'float backFibres')),
    'shader_no_old_curved_filament': 'curvedFilament(' not in gl,
    'shader_containment_preserved': 'float filamentContain = 1.0 - smoothstep(0.945, 0.982, sphereNorm);' in gl,
}

failed = []
print('=== PATCH UI 16 DIAGNOSTICS ===')
for name, ok in checks.items():
    print(f'[{"PASS" if ok else "FAIL"}] {name}')
    if not ok:
        failed.append(name)
if failed:
    raise SystemExit('FAILED: ' + ', '.join(failed))
print(f'Patch 16 diagnostics: {len(checks)}/{len(checks)} PASS')
