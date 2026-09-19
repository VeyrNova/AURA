from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
orb = (root / 'ui' / 'orb_widget.py').read_text(encoding='utf-8')
gl = (root / 'ui' / 'opengl_orb_surface.py').read_text(encoding='utf-8')
checks = {
    'brand_outline_phase': 'outline_phase = self._stage(progress, 0.02, 0.32)' in orb,
    'brand_white_phase': 'white_phase = self._stage(progress, 0.28, 0.72)' in orb,
    'brand_color_phase': 'color_phase = self._stage(progress, 0.72, 0.98)' in orb,
    'sphere_clip_containment': 'clip.addEllipse(QPointF(cx, cy), radius*.985, radius*.985)' in orb,
    'shader_corona_inside': 'smoothstep(0.985, 1.00, sphereNorm)' in gl,
    'shader_outer_corona_damped': '0.12*trunkA + 0.18*branchA + 0.24*branchB' in gl,
}
print('=== PATCH UI 14 DIAGNOSTICS ===')
failed = False
for name, ok in checks.items():
    print(f'[{"PASS" if ok else "FAIL"}] {name}')
    failed = failed or (not ok)
if failed:
    raise SystemExit(1)
