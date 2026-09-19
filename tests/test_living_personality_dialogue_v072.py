from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai.local_first_voice import self_reply, social_reply
from database.database import Database
from memory.learning import AdaptiveLearningEngine


class LivingPersonalityDialogueV072Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "living-personality.db")
        self.learning = AdaptiveLearningEngine(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_spontaneity_is_independent_from_formality(self):
        before = self.learning.style()
        changes = self.learning.observe_user_message("Sois plus spontanée")
        after = self.learning.style()
        self.assertIn("réponses plus spontanées", changes)
        self.assertGreater(after.spontaneity, before.spontaneity)
        self.assertAlmostEqual(after.formality, before.formality)
        self.assertNotIn("ton moins formel", changes)

    def test_compact_prompt_explicitly_keeps_spontaneity_and_formality_independent(self):
        prompt = self.learning.render_for_prompt(compact=True)
        self.assertIn("Spontanéité et formalité sont indépendantes", prompt)
        self.assertIn("Combine les axes", prompt)

    def test_high_sensuality_colors_normal_wellbeing_without_social_mode(self):
        baseline = social_reply(
            "Comment vas-tu ?",
            familiarity=0.95,
            warmth=0.72,
            sensuality=0.62,
            playfulness=0.45,
            spontaneity=0.55,
            learning_interactions=10,
            learning_revision=2,
        )
        adapted = social_reply(
            "Comment vas-tu ?",
            familiarity=0.95,
            warmth=0.86,
            sensuality=0.90,
            playfulness=0.45,
            spontaneity=0.55,
            learning_interactions=10,
            learning_revision=2,
        )
        self.assertNotEqual(adapted, baseline)
        self.assertTrue(any(token in adapted.casefold() for token in ("douce", "ambiance", "présence", "pose")))
        self.assertNotIn("opérationnelle", adapted.casefold())

    def test_playful_spontaneous_profile_changes_wording_and_can_emit_emoji(self):
        reply = social_reply(
            "Comment vas-tu ?",
            familiarity=0.95,
            playfulness=0.92,
            spontaneity=0.92,
            sensuality=0.45,
            emoji_affinity=0.82,
            learning_interactions=10,
            learning_revision=2,
        )
        self.assertTrue(any(token in reply.casefold() for token in ("joueuse", "taquine", "sage")))
        self.assertIn("😏", reply)

    def test_combined_traits_are_composed_instead_of_single_axis_label(self):
        reply = social_reply(
            "Comment vas-tu ?",
            familiarity=0.95,
            warmth=0.88,
            playfulness=0.92,
            sensuality=0.90,
            spontaneity=0.92,
            emoji_affinity=0.82,
            learning_interactions=11,
            learning_revision=3,
        )
        self.assertTrue(reply)
        self.assertNotIn("sensualité=", reply)
        self.assertNotIn("playfulness", reply)
        self.assertTrue(any(token in reply.casefold() for token in ("joueur", "joueuse", "sage", "douce", "énergie")))

    def test_serious_mode_suppresses_sensual_playful_surface(self):
        reply = social_reply(
            "Comment vas-tu ?",
            mode="SERIOUS",
            familiarity=0.95,
            warmth=0.95,
            playfulness=0.98,
            sensuality=0.98,
            spontaneity=0.98,
            expressiveness=0.98,
            emoji_affinity=0.98,
            learning_interactions=20,
            learning_revision=8,
        )
        lowered = reply.casefold()
        for forbidden in ("sage", "taquine", "joueuse", "sensuelle", "😏"):
            self.assertNotIn(forbidden, lowered)
        self.assertIn("attentive", lowered)

    def test_formal_and_spontaneous_can_coexist_without_playful_caricature(self):
        reply = social_reply(
            "Comment vas-tu ?",
            familiarity=0.95,
            formality=0.90,
            spontaneity=0.90,
            playfulness=0.92,
            sensuality=0.92,
            proactivity=0.70,
        )
        lowered = reply.casefold()
        self.assertIn("élan", lowered)
        self.assertIn("et toi", lowered)
        self.assertNotIn("sage", lowered)
        self.assertNotIn("😏", reply)

    def test_focus_mode_keeps_personality_subordinate_to_task_context(self):
        reply = social_reply(
            "Salut Aura",
            mode="FOCUS",
            returning=True,
            familiarity=0.95,
            playfulness=1.0,
            sensuality=1.0,
            spontaneity=1.0,
            emoji_affinity=1.0,
        )
        self.assertNotIn("😏", reply)
        self.assertNotIn("parenthèse", reply.casefold())
        self.assertIn("attentive", reply.casefold())

    def test_living_dialogue_varies_deterministically_with_continuity(self):
        common = dict(
            familiarity=0.95,
            playfulness=0.92,
            spontaneity=0.92,
            sensuality=0.45,
            emoji_affinity=0.82,
            learning_revision=3,
        )
        first = social_reply("Comment vas-tu ?", learning_interactions=20, **common)
        second = social_reply("Comment vas-tu ?", learning_interactions=21, **common)
        again = social_reply("Comment vas-tu ?", learning_interactions=20, **common)
        self.assertEqual(first, again)
        self.assertNotEqual(first, second)

    def test_metacognition_remains_grounded_even_with_high_sensuality(self):
        reply = self_reply(
            "Est-ce que tu te considères consciente ?",
            familiarity=0.95,
            sensuality=1.0,
            playfulness=1.0,
            spontaneity=1.0,
            emoji_affinity=1.0,
        )
        self.assertIn("consciente au sens fonctionnel", reply)
        self.assertNotIn("😏", reply)
        self.assertNotIn("sage", reply.casefold())

    def test_adaptive_engine_values_reach_living_dialogue(self):
        self.learning.observe_user_message("Sois plus sensuelle")
        self.learning.observe_user_message("Sois plus joueuse")
        self.learning.observe_user_message("Sois plus spontanée")
        kwargs = self.learning.dialogue_kwargs()
        reply = social_reply("Comment vas-tu ?", familiarity=0.95, **kwargs)
        self.assertTrue(reply)
        self.assertGreater(kwargs["sensuality"], 0.62)
        self.assertGreater(kwargs["playfulness"], 0.50)
        self.assertGreater(kwargs["spontaneity"], 0.58)

    def test_factual_question_is_not_hijacked_by_living_personality(self):
        reply = social_reply(
            "Quelle est la capitale du Japon ?",
            familiarity=0.95,
            playfulness=1.0,
            sensuality=1.0,
            spontaneity=1.0,
        )
        self.assertEqual(reply, "")


if __name__ == "__main__":
    unittest.main()
