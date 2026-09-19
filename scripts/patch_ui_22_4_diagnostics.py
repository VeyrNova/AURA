from pathlib import Path
import py_compile

root = Path(__file__).resolve().parents[1]
files = [
    root/'ui/opengl_orb_surface.py', root/'ui/orb_widget.py', root/'ui/main_window.py', root/'voice/xtts_tts.py'
]
for p in files:
    py_compile.compile(str(p), doraise=True)

checks = {
    'focus_u_speed_live': 'clamp(u_speed, 0.0, 2.0)' in files[0].read_text(encoding='utf-8'),
    'fallback_real_voice': 'voice_gain = voice ** .68' in files[1].read_text(encoding='utf-8'),
    'fallback_no_fake_full_voice': 'self._target_voice = 1.0 if self.state == "SPEAKING" else 0.0' not in files[1].read_text(encoding='utf-8'),
    'pcm_callback_authoritative': 'if self.aura_core.state != AuraState.SPEAKING' not in files[2].read_text(encoding='utf-8')[files[2].read_text(encoding='utf-8').index('def _on_voice_amplitude_changed'):files[2].read_text(encoding='utf-8').index('def _on_state_changed')],
    'runtime_envelope_log': 'XTTS visual envelope live peak=' in files[3].read_text(encoding='utf-8'),
}
failed=False
for name,ok in checks.items():
    print(f'[{"PASS" if ok else "FAIL"}] {name}')
    failed |= not ok
if failed:
    raise SystemExit(1)
print('Patch 22.4 diagnostics: PASS')
