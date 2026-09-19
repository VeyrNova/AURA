from pathlib import Path

root = Path(__file__).resolve().parents[1]
orb_path = root / 'ui' / 'orb_widget.py'
gl_path = root / 'ui' / 'opengl_orb_surface.py'
orb = orb_path.read_text(encoding='utf-8')
gl = gl_path.read_text(encoding='utf-8')

checks = {
    'visual_progress_state_machine': 'self._visual_progress = min(self._target_progress, self._visual_progress + 0.012)' in orb,
    'boot_reset_is_immediate': 'target <= 0.02 or target + 0.10 < self._visual_progress' in orb,
    'hollow_stage_0_25': 'white_fill = self._stage(progress, 0.25, 0.60)' in orb,
    'color_stage_84_100': 'color_phase = self._stage(progress, 0.84, 1.00)' in orb,
    'white_fill_bottom_to_top': 'fill_top = bounds.bottom() - bounds.height() * white_fill' in orb,
    'fallback_strict_clip': 'neural_clip.addEllipse(QPointF(cx, cy), radius*.975, radius*.975)' in orb,
    'fallback_secondary_twigs': 'Short secondary dendrites create a denser cortex' in orb,
    'gpu_strict_containment': 'float filamentContain = 1.0 - smoothstep(0.945, 0.982, sphereNorm);' in gl,
    'gpu_dense_twigs': all(name in gl for name in ('float twigA =', 'float twigB =', 'float twigC =')),
    'gpu_orbits_inside': 'ringBand(sphereNorm,0.89' in gl and 'ringBand(sphereNorm,0.955' in gl,
    'gpu_motes_inside': 'neuralRadius*0.945, neuralRadius*0.985' in gl,
    'no_old_outer_orbits': 'ringBand(sphereNorm,1.12' not in gl and 'ringBand(sphereNorm,1.23' not in gl,
}

print('=== PATCH UI 15 DIAGNOSTICS ===')
failed = []
for name, ok in checks.items():
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        failed.append(name)
if failed:
    raise SystemExit('Failed: ' + ', '.join(failed))
print(f'Patch 15 diagnostics: {len(checks)}/{len(checks)} PASS')
