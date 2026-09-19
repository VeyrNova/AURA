from pathlib import Path
import hashlib

root = Path(__file__).resolve().parents[1]
source21 = Path('/mnt/data/AURA_UI_PATCH_21_VOLUMETRIC_NEURAL_SHELL_OPTIMIZATION')
gl = (root/'ui/opengl_orb_surface.py').read_text(encoding='utf-8')
orb = (root/'ui/orb_widget.py').read_text(encoding='utf-8')

checks = {
    'focus_flag_enabled': 'UI_FOCUS_MODE = True' in gl,
    'focus_shader_present': 'FOCUS_FRAGMENT_SHADER = r"""' in gl,
    'focus_shader_selected': 'FOCUS_FRAGMENT_SHADER if UI_FOCUS_MODE else FRAGMENT_SHADER' in gl,
    'multipass_disabled_in_focus': '(not UI_FOCUS_MODE)' in gl and 'multipass = (' in gl,
    'focus_log_present': 'orb/cortex/particles/base disabled; logo+waveform only' in gl,
    'fallback_neural_field_not_called': 'self._draw_neural_field(p, cx, cy, radius, primary, violet,' not in orb[orb.find('def paintEvent(self, event):'):orb.find('# ---------------------------------------------------------------------------\n# v0.7.0.15.6.11')],
    'fallback_reflection_not_called': 'self._draw_neural_reflection(p, cx, cy, radius, primary, violet' not in orb[orb.find('def paintEvent(self, event):'):orb.find('# ---------------------------------------------------------------------------\n# v0.7.0.15.6.11')],
    'fallback_waveform_kept': 'self._draw_neural_wave(p, cx, cy, w, radius, primary, violet, wave_reveal)' in orb,
    'full_neural_shader_retained': 'FRAGMENT_SHADER = r"""' in gl and 'dendriteCluster' in gl,
}

# Validate that the logo renderer class itself is byte-identical to Patch 21.
def logo_block(text: str) -> str:
    a = text.index('class _AuraMarkWidget(QWidget):')
    b = text.index('class PainterOrbWidget(QWidget):')
    return text[a:b]
if source21.exists():
    old_orb = (source21/'ui/orb_widget.py').read_text(encoding='utf-8')
    checks['logo_renderer_unchanged'] = logo_block(old_orb) == logo_block(orb)

print('=== PATCH UI 22 DIAGNOSTICS ===')
failed = False
for name, ok in checks.items():
    print(f'[{"PASS" if ok else "FAIL"}] {name}')
    failed |= not ok
if failed:
    raise SystemExit(1)
print(f'PASS {sum(checks.values())}/{len(checks)}')
