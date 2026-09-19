import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class UIFocusWaveformV072Tests(unittest.TestCase):
    def setUp(self):
        self.gl = (ROOT / 'ui' / 'opengl_orb_surface.py').read_text(encoding='utf-8')
        self.orb = (ROOT / 'ui' / 'orb_widget.py').read_text(encoding='utf-8')
        self.main = (ROOT / 'ui' / 'main_window.py').read_text(encoding='utf-8')
        self.xtts = (ROOT / 'voice' / 'xtts_tts.py').read_text(encoding='utf-8')

    def test_focus_mode_is_enabled(self):
        self.assertIn('UI_FOCUS_MODE = True', self.gl)

    def test_focus_shader_keeps_u_speed_live(self):
        self.assertIn('clamp(u_speed, 0.0, 2.0)', self.gl)

    def test_focus_shader_uses_real_voice_level(self):
        self.assertIn('float voice = clamp(u_voice, 0.0, 1.0);', self.gl)
        self.assertIn('speaking*(0.004 + 0.115*voiceGain)', self.gl)

    def test_qpainter_fallback_does_not_fake_full_voice(self):
        self.assertNotIn('self._target_voice = 1.0 if self.state == "SPEAKING" else 0.0', self.orb)
        self.assertIn('voice_gain = voice ** .68', self.orb)
        self.assertIn('speech_amp = speaking * (.012 + .105*voice_gain)', self.orb)

    def test_pcm_callback_is_authoritative(self):
        block = self.main[self.main.index('def _on_voice_amplitude_changed'):self.main.index('def _on_state_changed')]
        self.assertNotIn('if self.aura_core.state != AuraState.SPEAKING', block)
        self.assertIn('self.orb.set_voice_amplitude(value)', block)

    def test_xtts_has_runtime_envelope_telemetry(self):
        self.assertIn('XTTS visual envelope live peak=', self.xtts)
        self.assertIn('float(sample_rate) * 0.032', self.xtts)


if __name__ == '__main__':
    unittest.main()
