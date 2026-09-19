import unittest
from unittest.mock import patch

from voice.voice_engine import VoiceEngine
from voice.xtts_tts import XTTSTTS


class ResourceReleaseTests(unittest.TestCase):
    def tearDown(self):
        XTTSTTS._shared_api = None
        XTTSTTS._shared_device = None

    def test_xtts_shared_model_can_be_released_without_loading_a_new_one(self):
        XTTSTTS._shared_api = object()
        XTTSTTS._shared_device = "cpu"
        self.assertTrue(XTTSTTS.shared_model_loaded())
        self.assertTrue(XTTSTTS.release_shared_model())
        self.assertFalse(XTTSTTS.shared_model_loaded())

    def test_voice_engine_can_force_lightweight_fallback(self):
        engine = VoiceEngine()
        primary = engine.tts
        fallback = engine.fallback_tts
        if primary is None or fallback is None:
            self.skipTest("Primary/fallback TTS not configured")
        with (
            patch.object(engine, "_tts_available", side_effect=lambda obj: obj is fallback),
            patch.object(primary, "speak") as primary_speak,
            patch.object(fallback, "speak") as fallback_speak,
        ):
            engine.speak("test", force_fallback=True)
        primary_speak.assert_not_called()
        fallback_speak.assert_called_once_with("test")
        self.assertEqual(engine._last_engine_used, "piper")

    def test_guardian_disables_heavy_voice_warmup_by_default(self):
        engine = VoiceEngine()
        with (
            patch.object(engine.stt, "warmup") as stt_warmup,
            patch.object(engine, "_output_backend") as output_backend,
        ):
            engine.warmup()
        if __import__("config.settings", fromlist=["settings"]).settings.RESOURCE_GUARDIAN_ENABLED:
            stt_warmup.assert_not_called()
            output_backend.assert_not_called()


if __name__ == "__main__":
    unittest.main()
