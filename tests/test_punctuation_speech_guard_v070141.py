from regression_compat import assert_version_at_least
import unittest
from unittest.mock import patch

from voice.voice_profile import VoiceProfile
from voice.xtts_tts import XTTSTTS

from config.settings import settings
from voice.text_to_speech import strip_terminal_punctuation_for_synthesis


class PunctuationSpeechGuardV070141Tests(unittest.TestCase):
    def test_version(self):
        assert_version_at_least(self, settings.APP_VERSION, "0.7.0.15.6.10")

    def test_terminal_period_is_not_sent_to_synthesizer(self):
        self.assertEqual(strip_terminal_punctuation_for_synthesis("Bonsoir."), "Bonsoir")

    def test_realtime_complete_greeting_is_not_forced_to_merge(self):
        self.assertLessEqual(settings.REALTIME_DIALOGUE_MIN_SENTENCE_CHARS, len("Oui."))
        self.assertLessEqual(settings.REALTIME_DIALOGUE_MIN_SENTENCE_CHARS, len("Bonsoir."))

    def test_all_terminal_sentence_punctuation_is_silent(self):
        self.assertEqual(strip_terminal_punctuation_for_synthesis("Bonjour !"), "Bonjour")
        self.assertEqual(strip_terminal_punctuation_for_synthesis("Comment vas-tu ?"), "Comment vas-tu")
        self.assertEqual(strip_terminal_punctuation_for_synthesis("Très bien…"), "Très bien")
        self.assertEqual(strip_terminal_punctuation_for_synthesis("Attention :"), "Attention")
        self.assertEqual(strip_terminal_punctuation_for_synthesis("Suite ;"), "Suite")

    def test_internal_punctuation_is_preserved(self):
        self.assertEqual(
            strip_terminal_punctuation_for_synthesis("Bonsoir. Comment vas-tu ?"),
            "Bonsoir. Comment vas-tu",
        )

    def test_decimal_point_is_preserved(self):
        self.assertEqual(
            strip_terminal_punctuation_for_synthesis("Il fait 32.8."),
            "Il fait 32.8",
        )

    def test_closing_quote_is_preserved_but_period_is_silent(self):
        self.assertEqual(
            strip_terminal_punctuation_for_synthesis('« Bonjour. »'),
            '« Bonjour. »',
        )
        self.assertEqual(
            strip_terminal_punctuation_for_synthesis('«Bonjour.»'),
            '«Bonjour»',
        )

    def test_punctuation_only_payload_becomes_empty(self):
        self.assertEqual(strip_terminal_punctuation_for_synthesis("..."), "")

    def _backend(self):
        profile = VoiceProfile(
            engine="xtts", xtts_mode="preset", xtts_preset="Nova Hogarth", xtts_language="fr"
        ).normalized()
        backend = XTTSTTS(profile)
        backend._device = "cuda"
        return backend

    def test_monolithic_xtts_render_receives_no_terminal_period(self):
        backend = self._backend()
        rendered = []

        def fake_render(api, text, wav_path, *, split_sentences=False):
            rendered.append(text)
            wav_path.write_bytes(b"fake")

        with patch.object(backend, "_load_model", return_value=object()), \
             patch.object(backend, "_render_to_wav", side_effect=fake_render), \
             patch.object(backend, "_play_wav_blocking", return_value=None), \
             patch("voice.xtts_tts.polish_wav_tail", return_value=False):
            backend._speak_impl("Bonsoir.")
        self.assertEqual(rendered, ["Bonsoir"])

    def test_progressive_xtts_each_render_chunk_has_silent_terminal_punctuation(self):
        backend = self._backend()
        rendered = []
        text = (
            "Première phrase complète pour le test. "
            "Deuxième phrase complète qui doit aussi garder sa pause sans prononcer le point. "
            "Troisième phrase complète afin de forcer le pipeline progressif avec plusieurs segments."
        )

        def fake_render(api, chunk, wav_path, *, split_sentences=False):
            rendered.append(chunk)
            wav_path.write_bytes(b"fake")

        with patch.object(backend, "_load_model", return_value=object()), \
             patch.object(backend, "_render_to_wav", side_effect=fake_render), \
             patch.object(backend, "_play_progressive_path", return_value=None), \
             patch("voice.xtts_tts.polish_wav_tail", return_value=False):
            backend._speak_progressive(text)
        self.assertGreaterEqual(len(rendered), 2)
        self.assertTrue(all(not chunk.endswith((".", "!", "?", "…", ":", ";", ",")) for chunk in rendered))
        self.assertTrue(any("." in chunk for chunk in rendered), "La ponctuation interne doit rester disponible pour la prosodie")


if __name__ == "__main__":
    unittest.main()
