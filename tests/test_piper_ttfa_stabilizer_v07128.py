from regression_compat import assert_version_at_least
import unittest
from unittest.mock import patch

from config.settings import settings
from voice.text_to_speech import PiperTTS, split_piper_progressive_segments


class FakeChunk:
    audio_int16_bytes = b"\x00\x00" * 16


class WarmVoice:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def synthesize(self, text, syn_config=None):
        self.calls.append(text)
        if self.fail:
            raise RuntimeError("warmup probe failure")
        yield FakeChunk()


class PiperTTFAStabilizerV07128Tests(unittest.TestCase):
    def test_version_and_defaults(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.1.2.8")
        self.assertTrue(settings.PIPER_INFERENCE_PREWARM)
        self.assertLessEqual(settings.PIPER_FIRST_SEGMENT_CHARS, 48)
        self.assertGreaterEqual(settings.PIPER_FIRST_SEGMENT_MIN_CHARS, 10)

    def test_first_weather_micro_phrase_prefers_early_clause(self):
        text = (
            "À Tokyo, 28 degrés Celsius, ciel couvert. "
            "Pas de pluie actuellement. Averses possibles plus tard aujourd'hui."
        )
        parts = split_piper_progressive_segments(text)
        self.assertGreaterEqual(len(parts), 2)
        self.assertLessEqual(len(parts[0]), settings.PIPER_FIRST_SEGMENT_CHARS)
        self.assertLess(len(parts[0]), 40)
        self.assertIn("Tokyo", parts[0])
        self.assertEqual(" ".join(parts), " ".join(text.split()))

    def test_inference_prewarm_consumes_pcm_without_audio_stream(self):
        backend = PiperTTS()
        voice = WarmVoice()
        with patch.object(backend, "_synthesis_config", return_value=None):
            elapsed = backend._prewarm_inference(voice)
        self.assertGreaterEqual(elapsed, 0.0)
        self.assertEqual(len(voice.calls), 1)
        self.assertNotEqual(voice.calls[0], "")
        self.assertIsNone(backend._active_stream)

    def test_inference_prewarm_failure_is_non_fatal(self):
        backend = PiperTTS()
        voice = WarmVoice(fail=True)
        with patch.object(backend, "_synthesis_config", return_value=None):
            elapsed = backend._prewarm_inference(voice)
        self.assertEqual(elapsed, 0.0)
        self.assertEqual(len(voice.calls), 1)


if __name__ == "__main__":
    unittest.main()
