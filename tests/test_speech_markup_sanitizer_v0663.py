import unittest
from unittest.mock import Mock

from voice.text_to_speech import sanitize_for_speech
from voice.xtts_tts import XTTSTTS


class SpeechMarkupSanitizerV0663Tests(unittest.TestCase):
    def test_memory_html_break_is_not_spoken(self):
        text = "Je me souviens de ceci :<br> • Tu préfères les réponses concises."
        spoken = sanitize_for_speech(text, max_chars=500)
        self.assertNotIn("<br", spoken.lower())
        self.assertNotIn("•", spoken)
        self.assertEqual(spoken, "Je me souviens de ceci : Tu préfères les réponses concises.")

    def test_html_entities_and_tags_are_cleaned(self):
        text = "<b>AURA</b>&nbsp;: <i>bonjour</i><br/>Comment ça va ?"
        spoken = sanitize_for_speech(text, max_chars=500)
        self.assertNotIn("<", spoken)
        self.assertNotIn("&nbsp;", spoken)
        self.assertEqual(spoken, "AURA : bonjour Comment ça va ?")

    def test_legacy_malformed_br_fragment_is_cleaned(self):
        text = "Voici ce que j'ai en mémoire :<br 1 · preference — réponse concise"
        spoken = sanitize_for_speech(text, max_chars=500)
        self.assertNotIn("<br", spoken.lower())
        self.assertIn("1 · preference", spoken)

    def test_decorative_bullets_are_silent(self):
        text = "• Premier souvenir\n• Deuxième souvenir"
        spoken = sanitize_for_speech(text, max_chars=500)
        self.assertEqual(spoken, "Premier souvenir Deuxième souvenir")

    def test_xtts_preview_uses_the_same_sanitizer(self):
        backend = object.__new__(XTTSTTS)
        backend._speak_impl = Mock(return_value="ok")
        result = backend.speak_preview("Bonjour<br>• monde", fast=True)
        self.assertEqual(result, "ok")
        sent_text = backend._speak_impl.call_args.args[0]
        self.assertEqual(sent_text, "Bonjour monde")


if __name__ == "__main__":
    unittest.main()
