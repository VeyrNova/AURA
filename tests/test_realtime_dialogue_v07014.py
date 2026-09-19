import unittest

from voice.realtime_dialogue import (
    RealtimeSentenceBuffer,
    prepare_sentence_for_realtime_speech,
    remaining_final_sentences,
)


class RealtimeDialogueTests(unittest.TestCase):
    def test_stream_releases_only_complete_sentences(self):
        buf = RealtimeSentenceBuffer()
        self.assertEqual(buf.feed("Bonjour ! Je peux"), ("Bonjour !",))
        self.assertEqual(buf.feed(" t'aider maintenant."), ("Je peux t'aider maintenant.",))
        self.assertEqual(buf.pending, "")

    def test_decimal_does_not_split_sentence(self):
        buf = RealtimeSentenceBuffer()
        self.assertEqual(buf.feed("Il fait 32.8 degrés"), ())
        self.assertEqual(buf.feed(" Celsius."), ("Il fait 32.8 degrés Celsius.",))

    def test_deterministic_french_fix_before_early_speech(self):
        decision = prepare_sentence_for_realtime_speech("Je peux me aider aujourd'hui.")
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.text, "Je peux m'aider aujourd'hui.")

    def test_unresolved_quality_issue_is_held(self):
        decision = prepare_sentence_for_realtime_speech("Ce rôle importantes reste central.")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "quality-hold")

    def test_unresolved_factual_risk_is_held(self):
        decision = prepare_sentence_for_realtime_speech(
            "Tous les atomes ont exactement 7 protons.",
            user_text="Explique-moi les atomes",
            factual_explanation=True,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "knowledge-hold")

    def test_remaining_sentences_skip_spoken_prefix(self):
        remaining = remaining_final_sentences(
            "Bonjour ! Je vais bien. Et toi ?",
            ("Bonjour !", "Je vais bien."),
        )
        self.assertEqual(remaining, ("Et toi ?",))


if __name__ == "__main__":
    unittest.main()
