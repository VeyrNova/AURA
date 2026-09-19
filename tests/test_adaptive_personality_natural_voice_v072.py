from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai.local_first_voice import self_reply, social_reply
from database.database import Database
from memory.learning import AdaptiveLearningEngine
from voice.xtts_tts import _split_native_stream_text, _XTTS_NATIVE_SEGMENT_MAX_CHARS


class AdaptivePersonalityNaturalVoiceV072Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "adaptive-personality.db")
        self.learning = AdaptiveLearningEngine(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_sensuality_directive_is_learned_without_llm(self):
        before = self.learning.style().sensuality
        changes = self.learning.observe_user_message("Sois plus sensuelle")
        self.assertIn("présence plus sensuelle", changes)
        self.assertGreater(self.learning.style().sensuality, before)
        self.assertEqual(self.learning.revision, 1)

    def test_personality_directives_cover_playful_complicit_and_spontaneous(self):
        changes = self.learning.observe_user_message("Sois plus joueuse")
        self.assertIn("ton plus joueur", changes)
        playful = self.learning.style().playfulness
        changes = self.learning.observe_user_message("Sois plus complice")
        self.assertIn("présence plus complice", changes)
        self.assertGreater(self.learning.style().playfulness, playful)
        changes = self.learning.observe_user_message("Sois plus spontanée")
        self.assertIn("réponses plus spontanées", changes)
        self.assertGreater(self.learning.style().spontaneity, 0.58)

    def test_serious_and_reserved_directives_move_bounded_axes(self):
        initial = self.learning.style()
        self.learning.observe_user_message("Sois plus sérieuse")
        serious = self.learning.style()
        self.assertGreater(serious.formality, initial.formality)
        self.assertLess(serious.playfulness, initial.playfulness)
        self.assertLess(serious.sensuality, initial.sensuality)
        self.learning.observe_user_message("Sois plus réservée")
        reserved = self.learning.style()
        self.assertLess(reserved.expressiveness, serious.expressiveness)

    def test_less_formal_natural_phrase_is_understood(self):
        before = self.learning.style().formality
        changes = self.learning.observe_user_message("Adopte un ton beaucoup moins formel")
        self.assertTrue(changes)
        self.assertLess(self.learning.style().formality, before)

    def test_ordinary_trait_statement_does_not_mutate_personality(self):
        before = self.learning.style()
        changes = self.learning.observe_user_message("Elle est sensuelle et très joueuse dans ce film")
        self.assertEqual(changes, [])
        self.assertEqual(self.learning.style(), before)
        self.assertEqual(self.learning.revision, 0)

    def test_private_mode_blocks_personality_learning(self):
        self.learning.observe_user_message("Sois plus sensuelle", private=True)
        self.assertEqual(self.learning.revision, 0)
        self.assertEqual(self.learning.style().sensuality, 0.62)

    def test_legacy_style_json_loads_new_dimensions_from_defaults(self):
        self.db.set_preference(
            self.learning.KEY_STYLE,
            json.dumps({"warmth": 0.88, "verbosity": 0.20, "directness": 0.91}),
        )
        style = self.learning.style()
        self.assertAlmostEqual(style.warmth, 0.88)
        self.assertAlmostEqual(style.sensuality, 0.62)
        self.assertAlmostEqual(style.playfulness, 0.50)
        self.assertAlmostEqual(style.spontaneity, 0.58)

    def test_prompt_and_dialogue_context_export_personality_axes(self):
        self.learning.observe_user_message("Sois plus sensuelle")
        prompt = self.learning.render_for_prompt(compact=True)
        context = self.learning.dialogue_kwargs()
        self.assertIn("sensualité=", prompt)
        self.assertIn("spontanéité=", prompt)
        for key in ("playfulness", "sensuality", "formality", "expressiveness", "spontaneity"):
            self.assertIn(key, context)

    def test_local_first_voice_accepts_adaptive_personality_axes(self):
        reply = social_reply(
            "Salut Aura",
            returning=True,
            familiarity=0.95,
            playfulness=0.90,
            spontaneity=0.90,
            sensuality=0.80,
        )
        self.assertTrue(reply)
        self.assertIn("retrouver", reply)

    def test_self_evolution_reply_respects_concise_learned_style(self):
        reply = self_reply(
            "Comment as-tu changé depuis qu'on se parle ?",
            learning_revision=7,
            learned_preferences=5,
            last_learning_change="présence plus sensuelle, ton plus joueur et réponses plus spontanées",
            verbosity=0.20,
            directness=0.92,
        )
        self.assertIn("révision comportementale 7", reply)
        self.assertLessEqual(len(reply), _XTTS_NATIVE_SEGMENT_MAX_CHARS)

    def test_native_xtts_long_french_text_is_segmented_under_safe_limit(self):
        text = (
            "J'ai surtout changé dans ma manière de te répondre et de garder le fil entre nos échanges. "
            "J'ai intégré plusieurs retours explicites et j'en suis à une nouvelle révision comportementale. "
            "Ma dernière adaptation concerne ma façon d'être plus directe, plus naturelle et plus attentive avec toi dans nos échanges."
        )
        parts = _split_native_stream_text(text)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(part) <= _XTTS_NATIVE_SEGMENT_MAX_CHARS for part in parts))
        self.assertIn("révision comportementale", " ".join(parts))

    def test_native_xtts_short_text_keeps_single_segment(self):
        parts = _split_native_stream_text("Je suis là, attentive et prête à continuer avec toi.")
        self.assertEqual(len(parts), 1)


if __name__ == "__main__":
    unittest.main()
