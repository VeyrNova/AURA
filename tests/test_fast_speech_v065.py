from regression_compat import assert_version_at_least
import re
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import settings
from voice.voice_profile import VoiceProfile
from voice.xtts_tts import XTTSTTS, XTTSSynthesisMetrics


class FastSpeechV065Tests(unittest.TestCase):
    def setUp(self):
        self.profile = VoiceProfile(
            engine="xtts",
            xtts_mode="preset",
            xtts_preset="Nova Hogarth",
            xtts_language="fr",
        ).normalized()

    def test_version_is_065_or_newer(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.6.5")
        self.assertTrue(settings.FAST_SPEECH_ENABLED)

    def test_short_text_stays_one_chunk(self):
        chunks = XTTSTTS._bounded_text_chunks(
            "Bonjour, je suis AURA.", first_limit=72, next_limit=180,
            min_chars=28, max_chunks=8,
        )
        self.assertEqual(chunks, ("Bonjour, je suis AURA.",))

    def test_first_chunk_is_bounded(self):
        text = (
            "Bonjour. Je vais commencer par une réponse courte pour que ma voix arrive rapidement, "
            "puis je poursuivrai pendant que le premier morceau est déjà en lecture."
        )
        chunks = XTTSTTS._bounded_text_chunks(
            text, first_limit=72, next_limit=180, min_chars=28, max_chunks=8,
        )
        self.assertGreater(len(chunks), 1)
        self.assertLessEqual(len(chunks[0]), 108)
        self.assertGreaterEqual(len(chunks[0]), 12)

    def test_chunking_preserves_normalized_text(self):
        text = "Bonjour   Boris.  Voici une phrase, puis une autre phrase un peu plus longue pour le test."
        chunks = XTTSTTS._bounded_text_chunks(
            text, first_limit=42, next_limit=55, min_chars=20, max_chunks=8,
        )
        normalized = re.sub(r"\s+", " ", text.strip())
        self.assertEqual(" ".join(chunks), normalized)

    def test_chunk_count_is_bounded(self):
        text = " ".join(["segment"] * 300)
        chunks = XTTSTTS._bounded_text_chunks(
            text, first_limit=40, next_limit=60, min_chars=18, max_chunks=4,
        )
        self.assertLessEqual(len(chunks), 4)
        self.assertEqual(" ".join(chunks), text)

    def test_speak_routes_long_text_to_progressive(self):
        backend = XTTSTTS(self.profile)
        long_text = "x" * (settings.FAST_SPEECH_MIN_TEXT_CHARS + 20)
        expected = XTTSSynthesisMetrics("cuda", 1, 2, 3, len(long_text), progressive=True, chunk_count=2)
        with patch.object(settings, "FAST_SPEECH_NATIVE_STREAMING", False), \
             patch.object(backend, "_speak_progressive", return_value=expected) as progressive, \
             patch.object(backend, "_speak_impl") as monolithic:
            result = backend.speak(long_text)
        self.assertIs(result, expected)
        progressive.assert_called_once()
        monolithic.assert_not_called()

    def test_speak_routes_short_text_to_monolithic(self):
        backend = XTTSTTS(self.profile)
        short_text = "Bonjour AURA."
        expected = XTTSSynthesisMetrics("cuda", 1, 2, 3, len(short_text))
        with patch.object(settings, "FAST_SPEECH_NATIVE_STREAMING", False), \
             patch.object(backend, "_speak_progressive") as progressive, \
             patch.object(backend, "_speak_impl", return_value=expected) as monolithic:
            result = backend.speak(short_text)
        self.assertIs(result, expected)
        progressive.assert_not_called()
        monolithic.assert_called_once()

    def test_progressive_pipeline_reports_early_audio(self):
        backend = XTTSTTS(self.profile)
        backend._device = "cuda"
        text = (
            "Première phrase assez courte pour démarrer vite. "
            "Deuxième phrase qui continue pendant la lecture du premier morceau. "
            "Troisième phrase qui garde une prosodie naturelle sans coupure arbitraire. "
            "Quatrième phrase suffisamment longue pour garantir plusieurs morceaux dans ce test de pipeline progressif. "
            "Cinquième phrase pour terminer proprement."
        )

        def fake_render(api, chunk, wav_path: Path, *, split_sentences=False):
            import wave
            time.sleep(0.006)
            with wave.open(str(wav_path), "wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(22050)
                out.writeframes(b"\x00\x00" * 220)

        def fake_play(path: Path):
            time.sleep(0.012)

        with patch.object(backend, "_load_model", return_value=object()), \
             patch.object(backend, "_render_to_wav", side_effect=fake_render), \
             patch.object(backend, "_play_wav_blocking", side_effect=fake_play):
            metrics = backend._speak_progressive(text)

        self.assertTrue(metrics.progressive)
        self.assertGreater(metrics.chunk_count, 1)
        self.assertGreater(metrics.first_chunk_synthesis_seconds, 0)
        self.assertGreater(metrics.time_to_audio_seconds, 0)
        self.assertLess(metrics.time_to_audio_seconds, metrics.total_seconds)

    def test_stop_sets_progressive_cancel_event(self):
        backend = XTTSTTS(self.profile)
        backend._stop_event.clear()
        backend.stop()
        self.assertTrue(backend._stop_event.is_set())

    def test_metrics_remain_backward_compatible(self):
        metrics = XTTSSynthesisMetrics("cpu", 1.0, 2.0, 3.0, 10)
        self.assertFalse(metrics.progressive)
        self.assertEqual(metrics.chunk_count, 1)
        self.assertEqual(metrics.first_chunk_synthesis_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
