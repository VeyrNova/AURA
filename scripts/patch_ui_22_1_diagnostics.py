from pathlib import Path
import py_compile

root = Path(__file__).resolve().parents[1]
files = [
    root/'ui'/'main_window.py',
    root/'ui'/'opengl_orb_surface.py',
    root/'voice'/'voice_engine.py',
    root/'voice'/'xtts_tts.py',
]
for f in files:
    py_compile.compile(str(f), doraise=True)

main = (root/'ui'/'main_window.py').read_text(encoding='utf-8')
gl = (root/'ui'/'opengl_orb_surface.py').read_text(encoding='utf-8')
xtts = (root/'voice'/'xtts_tts.py').read_text(encoding='utf-8')
engine = (root/'voice'/'voice_engine.py').read_text(encoding='utf-8')
checks = {
    'qt_voice_signal': 'voice_amplitude_changed = Signal(float)' in main,
    'main_registers_callback': 'set_visual_amplitude_callback(self.voice_amplitude_changed.emit)' in main,
    'no_fake_constant_speaking_amp': 'set_voice_amplitude(1.0 if state == AuraState.SPEAKING else 0.0)' not in main,
    'pcm_rms_level': 'def _pcm_float32_level(payload: bytes) -> float:' in xtts,
    'playback_packet_drives_level': '_emit_visual_amplitude_from_pcm(payload)' in xtts,
    'fallback_packet_drives_level': '_emit_visual_amplitude_from_pcm(item)' in xtts,
    'speech_end_resets_level': '_emit_visual_amplitude(0.0)' in xtts,
    'voice_engine_bridge': 'def set_visual_amplitude_callback(self, callback)' in engine,
    'focus_mode_still_enabled': 'UI_FOCUS_MODE = True' in gl,
    'fake_sine_voice_removed': 'self._voice * (0.72 + 0.28 * math.sin' not in gl,
}
failed = False
for name, ok in checks.items():
    print(f"[{ 'PASS' if ok else 'FAIL' }] {name}")
    failed |= not ok
if failed:
    raise SystemExit(1)
print(f"Patch 22.1 diagnostics: {sum(checks.values())}/{len(checks)} PASS")
