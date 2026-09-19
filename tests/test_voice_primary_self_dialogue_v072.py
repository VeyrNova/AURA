from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ai.local_first_voice import self_reply
from database.database import Database
from memory.learning import AdaptiveLearningEngine


class VoicePrimarySelfDialogueV072Tests(unittest.TestCase):
    def test_self_questions_are_local_without_factual_hijack(self):
        kwargs = dict(
            learning_revision=3,
            learned_preferences=2,
            learning_interactions=18,
            last_learning_change="style plus direct",
        )
        self.assertIn("J'apprends", self_reply("Peux-tu apprendre et évoluer ?", **kwargs))
        self.assertIn("IA personnelle locale", self_reply("Qui es-tu ?", **kwargs))
        self.assertIn("continuité", self_reply("Qu'est-ce que ça te fait d'exister ?", **kwargs))
        self.assertIn("calme", self_reply("Que fais-tu ?", **kwargs))
        evolution = self_reply("Comment as-tu changé depuis qu'on se parle ?", **kwargs)
        self.assertIn("révision comportementale 3", evolution)
        self.assertIn("style plus direct", evolution)
        self.assertEqual(self_reply("Quelle est la météo demain ?", **kwargs), "")

    def test_explicit_learning_has_local_acknowledgement(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "learning.db")
            learning = AdaptiveLearningEngine(db)
            changes = learning.observe_user_message("Sois plus directe")
            reply = learning.acknowledgement(changes)
            self.assertIn("Je m'adapte", reply)
            self.assertIn("style plus direct", reply)
            self.assertEqual(learning.revision, 1)
            db.close()

    def test_adaptive_dialogue_exports_evolution_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / "learning.db")
            learning = AdaptiveLearningEngine(db)
            learning.observe_user_message("Sois plus directe")
            context = learning.dialogue_kwargs()
            self.assertEqual(context["learning_revision"], 1)
            self.assertEqual(context["last_learning_change"], "style plus direct")
            self.assertIn("directness", context)
            self.assertGreaterEqual(context["learning_interactions"], 1)
            db.close()

    def test_main_window_uses_voice_primary_before_model_routing(self):
        root = Path(__file__).resolve().parents[1]
        main = (root / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("xtts_local_first_self_reply", main)
        self.assertIn("Voice-primary ambient response", main)
        self.assertIn("Adaptive feedback handled local delivery", main)
        self.assertLess(main.index("xtts_local_first_self_reply("), main.index("route = classify_voice_route(text)"))

    def test_self_route_does_not_open_conversation_workspace(self):
        root = Path(__file__).resolve().parents[1]
        main = (root / "ui" / "main_window.py").read_text(encoding="utf-8")
        start = main.index("def _continue_after_agent_router")
        end = main.index("# Build memory/continuity context", start)
        self.assertNotIn('_switch_page("conversation")', main[start:end])


if __name__ == "__main__":
    unittest.main()
