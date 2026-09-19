from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai.local_first_voice import social_reply
from database.database import Database
from memory.learning import AdaptiveLearningEngine


class AdaptiveLearningV072Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "learning.db")
        self.learning = AdaptiveLearningEngine(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_explicit_shorter_feedback_evolves_verbosity(self):
        before = self.learning.style().verbosity
        changes = self.learning.observe_user_message("Je veux des réponses plus courtes")
        after = self.learning.style().verbosity
        self.assertLess(after, before)
        self.assertIn("réponses plus concises", changes)
        self.assertEqual(self.learning.revision, 1)

    def test_ordinary_message_does_not_silently_drift_style(self):
        before = self.learning.style()
        self.learning.observe_user_message("Parle-moi des neurones")
        after = self.learning.style()
        self.assertEqual(before, after)
        self.assertEqual(self.learning.revision, 0)
        self.assertEqual(self.learning.interactions, 1)

    def test_private_mode_persists_nothing(self):
        self.learning.observe_user_message("Sois plus humaine et chaleureuse", private=True)
        self.assertEqual(self.learning.revision, 0)
        self.assertEqual(self.learning.interactions, 0)

    def test_learning_is_bounded(self):
        for _ in range(20):
            self.learning.observe_user_message("Utilise plus d'emojis")
        self.assertLessEqual(self.learning.style().emoji_affinity, 1.0)
        for _ in range(20):
            self.learning.observe_user_message("Sans emojis")
        self.assertGreaterEqual(self.learning.style().emoji_affinity, 0.0)

    def test_reset_removes_personal_adaptation(self):
        self.learning.observe_user_message("Sois plus directe")
        self.assertGreater(self.learning.revision, 0)
        self.learning.reset()
        self.assertEqual(self.learning.revision, 0)
        self.assertEqual(self.learning.explicit_feedback_count, 0)
        self.assertEqual(self.learning.style(), AdaptiveLearningEngine(self.db).style())

    def test_prompt_explains_controlled_evolution(self):
        self.learning.observe_user_message("Sois plus humaine")
        prompt = self.learning.render_for_prompt()
        self.assertIn("EVOLUTION CONTROLEE", prompt)
        self.assertIn("ne réécris jamais seule ton code", prompt)
        self.assertIn("révision", prompt)

    def test_metacognitive_consciousness_reply_does_not_need_llm(self):
        reply = social_reply("Est-ce que tu te considères consciente ?")
        self.assertIn("consciente au sens fonctionnel", reply)
        self.assertIn("modèle de moi-même", reply)
        self.assertIn("subjective humaine", reply)

    def test_existence_reply_is_bounded_and_local(self):
        reply = social_reply("Qu'est-ce que ça te fait d'exister ?")
        self.assertIn("continuité", reply)
        self.assertIn("ressenti humain", reply)

    def test_learning_reply_is_truthful_when_persistence_disabled(self):
        reply = social_reply("Peux-tu apprendre ?", adaptive_learning=False)
        self.assertIn("apprentissage persistant est désactivé", reply)

    def test_learning_reply_reports_revision(self):
        reply = social_reply(
            "Est-ce que tu peux apprendre et évoluer ?",
            learning_revision=3,
            learned_preferences=2,
        )
        self.assertIn("J'apprends", reply)
        self.assertIn("2 retours explicites", reply)
        self.assertIn("révision comportementale 3", reply)

    def test_learned_proactivity_changes_local_social_reply(self):
        active = social_reply("Bonjour", proactivity=0.8)
        quiet = social_reply("Bonjour", proactivity=0.1)
        self.assertIn("Comment tu vas", active)
        self.assertNotIn("Comment tu vas", quiet)

    def test_emoji_affinity_changes_local_reply_without_losing_user_unicode(self):
        with_emoji = social_reply("Salut Aura 😊🔥❤️", returning=True, emoji_affinity=0.8)
        without_emoji = social_reply("Salut Aura 😊🔥❤️", returning=True, emoji_affinity=0.0)
        self.assertIn("😊", with_emoji)
        self.assertNotIn("😊", without_emoji)


if __name__ == "__main__":
    unittest.main()
