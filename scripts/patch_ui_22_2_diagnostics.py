from pathlib import Path
import ast
import array
import math
import py_compile

root = Path(__file__).resolve().parents[1]
main_path = root / 'ui' / 'main_window.py'
gl_path = root / 'ui' / 'opengl_orb_surface.py'
xtts_path = root / 'voice' / 'xtts_tts.py'

for path in (main_path, gl_path, xtts_path):
    py_compile.compile(str(path), doraise=True)

main = main_path.read_text(encoding='utf-8')
gl = gl_path.read_text(encoding='utf-8')
xtts = xtts_path.read_text(encoding='utf-8')

checks = {
    'focus_mode_still_enabled': 'UI_FOCUS_MODE = True' in gl,
    'pcm_32ms_visual_frames': 'float(sample_rate) * 0.032' in xtts,
    'time_aligned_visual_worker': 'def _visual_envelope_loop' in xtts and "name='aura-xtts-visual-envelope'" in xtts,
    'audio_write_contract_preserved': 'stream.write(payload)' in xtts,
    'persistent_bridge_uses_sliced_writer': '_write_pcm_with_visual_envelope(\n                        stream, payload' in xtts,
    'fallback_bridge_uses_sliced_writer': '_write_pcm_with_visual_envelope(\n                        stream, item' in xtts,
    'speaking_does_not_fake_full_voice': 'self._target_voice = 1.0 if state == "SPEAKING" else 0.0' not in gl,
    'shader_perceptual_voice_gain': 'float voiceGain = pow(voice, 0.68);' in gl,
    'shader_transient_geometry': 'float transientWave' in gl,
    'fast_attack_slow_release': 'smooth_alpha(30.0 if self._target_voice > self._voice else 5.2)' in gl,
    'hud_24ms_cadence': 'self._timer.start(24)' in main,
    'hud_micro_spikes': 'spike_gate = abs(math.sin' in main,
    'orb_remains_disabled': 'orb/cortex/particles/base disabled' in gl,
}

# Extract only lightweight helpers, avoiding XTTS/CUDA imports.
module = ast.parse(xtts)
level_node = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == '_pcm_float32_level')
ns = {}
exec(compile(ast.Module(body=[level_node], type_ignores=[]), str(xtts_path), 'exec'), ns)
level_fn = ns['_pcm_float32_level']

sr = 24000
def sine_level(amplitude: float) -> float:
    n = int(sr * 0.032)
    pcm = array.array('f', (amplitude * math.sin(2.0 * math.pi * 220.0 * i / sr) for i in range(n)))
    return float(level_fn(pcm.tobytes()))

silence = sine_level(0.0)
quiet = sine_level(0.008)
normal = sine_level(0.030)
strong = sine_level(0.120)
checks['envelope_silence_flat'] = silence == 0.0
checks['envelope_dynamic_range'] = 0.05 < quiet < normal < strong <= 1.0

class FakeStream:
    def __init__(self):
        self.parts = []
    def write(self, payload):
        self.parts.append(bytes(payload))

stream = FakeStream()
queued = []
writer_node = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == '_write_pcm_with_visual_envelope')
writer_ns = {'_queue_visual_envelope': lambda payload, sample_rate: queued.append((bytes(payload), int(sample_rate)))}
exec(compile(ast.Module(body=[writer_node], type_ignores=[]), str(xtts_path), 'exec'), writer_ns)
n = int(sr * 0.100)
pcm = array.array('f', (0.05 * math.sin(2.0 * math.pi * 220.0 * i / sr) for i in range(n))).tobytes()
writer_ns['_write_pcm_with_visual_envelope'](stream, pcm, sample_rate=sr)
checks['audio_chunk_stays_single_write'] = len(stream.parts) == 1
checks['visual_sequence_is_queued'] = len(queued) == 1 and queued[0][0] == pcm and queued[0][1] == sr
checks['pcm_bytes_preserved'] = b''.join(stream.parts) == pcm

failed = False
for name, ok in checks.items():
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    failed |= not ok
print(f"Envelope levels silence={silence:.3f} quiet={quiet:.3f} normal={normal:.3f} strong={strong:.3f}")
if failed:
    raise SystemExit(1)
print(f"Patch 22.2 diagnostics: {sum(checks.values())}/{len(checks)} PASS")
