import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import settings, read_elevenlabs_env_import, valid_elevenlabs_api_key
from regression_compat import assert_version_at_least
from voice.elevenlabs_tts import ElevenLabsTTS
from voice.voice_profile import VoiceProfile


class ElevenLabsStreamingSetupTests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.3.4.2")

    def test_jarvis_env_parser_reads_only_elevenlabs_values(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / ".env"
            p.write_text(
                "OTHER_SECRET=nope\nELEVENLABS_API_KEY=real-test-key-123456\n"
                "ELEVENLABS_VOICE_ID=voice-jarvis\nELEVENLABS_MODEL=eleven_flash_v2_5\n",
                encoding="utf-8",
            )
            values = read_elevenlabs_env_import(p)
        self.assertNotIn("OTHER_SECRET", values)
        self.assertEqual(values["ELEVENLABS_VOICE_ID"], "voice-jarvis")

    def test_placeholder_jarvis_key_is_rejected(self):
        self.assertFalse(valid_elevenlabs_api_key("sk_..."))
        self.assertFalse(valid_elevenlabs_api_key("a-valid-looking-key-123456"))
        self.assertTrue(valid_elevenlabs_api_key("sk_valid-looking-secret-123456"))

    def test_dialog_has_explicit_paste_and_jarvis_import_controls(self):
        source = (settings.BASE_DIR / "ui" / "voice_settings_dialog.py").read_text(encoding="utf-8")
        self.assertIn('QPushButton("Coller")', source)
        self.assertIn('Importer un .env Jarvis', source)
        self.assertIn('QApplication.clipboard()', source)

    def test_stream_endpoint_and_pcm_output_are_used(self):
        source = (settings.BASE_DIR / "voice" / "elevenlabs_tts.py").read_text(encoding="utf-8")
        self.assertIn('/stream?', source)
        self.assertIn('"output_format": "pcm_24000"', source)
        self.assertIn('ELEVENLABS_OPTIMIZE_STREAMING_LATENCY', source)

    def test_profile_keeps_jarvis_style_voice_controls(self):
        p = VoiceProfile(
            engine="elevenlabs",
            elevenlabs_voice_id="v",
            elevenlabs_stability=0.72,
            elevenlabs_similarity=0.88,
            elevenlabs_speed=1.1,
        ).normalized()
        self.assertAlmostEqual(p.elevenlabs_stability, 0.72)
        self.assertAlmostEqual(p.elevenlabs_similarity, 0.88)
        self.assertAlmostEqual(p.elevenlabs_speed, 1.1)


if __name__ == "__main__":
    unittest.main()
