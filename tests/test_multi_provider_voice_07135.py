import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from config.settings import settings, valid_cloud_api_token
from voice.voice_profile import VoiceProfile
from voice.gradium_tts import GradiumTTS
from voice.resemble_tts import ResembleTTS
from voice.chatterbox_tts import ChatterboxTTS
from voice.voice_engine import VoiceEngine


class MultiProviderVoice07135Tests(unittest.TestCase):
    def test_profile_accepts_new_engines(self):
        for engine in ("gradium", "resemble", "chatterbox"):
            self.assertEqual(VoiceProfile(engine=engine).normalized().engine, engine)

    def test_cloud_token_shape(self):
        self.assertTrue(valid_cloud_api_token("abcdefghijklmnop1234"))
        self.assertFalse(valid_cloud_api_token("your_api_key"))
        self.assertFalse(valid_cloud_api_token("short"))
        self.assertFalse(valid_cloud_api_token("abc defghijklmnop"))

    def test_gradium_safe_detail_redacts_secret(self):
        old = settings.GRADIUM_API_KEY
        settings.GRADIUM_API_KEY = "supersecret012345"
        try:
            detail = GradiumTTS._safe_detail(json.dumps({"message": "bad supersecret012345"}))
            self.assertNotIn("supersecret012345", detail)
            self.assertIn("[REDACTED]", detail)
        finally:
            settings.GRADIUM_API_KEY = old

    def test_resemble_safe_detail_redacts_secret(self):
        old = settings.RESEMBLE_API_KEY
        settings.RESEMBLE_API_KEY = "resemblesecret012345"
        try:
            detail = ResembleTTS._safe_detail(json.dumps({"message": "bad resemblesecret012345"}))
            self.assertNotIn("resemblesecret012345", detail)
        finally:
            settings.RESEMBLE_API_KEY = old

    def test_resemble_wav_prefix_parser(self):
        # Minimal PCM16 mono 24kHz WAV header + data marker.
        import struct
        fmt = struct.pack("<HHIIHH", 1, 1, 24000, 48000, 2, 16)
        body = b"fmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", 4) + b"\x00\x00\x00\x00"
        wav = bytearray(b"RIFF" + struct.pack("<I", len(body)+4) + b"WAVE" + body)
        parsed = ResembleTTS._parse_wav_prefix(wav)
        self.assertIsNotNone(parsed)
        offset, rate, channels, bits = parsed
        self.assertEqual((rate, channels, bits), (24000, 1, 16))
        self.assertEqual(bytes(wav[offset:offset+4]), b"\x00\x00\x00\x00")

    def test_chatterbox_disabled_by_default(self):
        profile = VoiceProfile(engine="chatterbox")
        backend = ChatterboxTTS(profile)
        with patch.object(settings, "CHATTERBOX_ENABLED", False):
            self.assertFalse(backend.is_available())

    def test_voice_engine_builds_new_backends_without_loading_models(self):
        engine = VoiceEngine.__new__(VoiceEngine)
        engine.profile = VoiceProfile(engine="piper")
        self.assertIsInstance(engine._build_tts("gradium"), GradiumTTS)
        self.assertIsInstance(engine._build_tts("resemble"), ResembleTTS)
        self.assertIsInstance(engine._build_tts("chatterbox"), ChatterboxTTS)


if __name__ == "__main__":
    unittest.main()
