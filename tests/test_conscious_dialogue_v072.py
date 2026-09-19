from __future__ import annotations

import unittest
from pathlib import Path

from ai.local_first_voice import social_reply
from consciousness.context_builder import ConsciousnessContextBuilder
from consciousness.dialogue import DialogueContext, social_reply as conscious_social_reply

ROOT = Path(__file__).resolve().parents[1]


class ConsciousDialogueV072Tests(unittest.TestCase):
    def test_greeting_is_human_not_machine_status(self):
        reply = social_reply("Bonjour Aura")
        self.assertIn("Je suis là", reply)
        self.assertNotIn("opérationnelle", reply.casefold())
        self.assertNotIn("système", reply.casefold())

    def test_wellbeing_uses_functional_self_state(self):
        reply = social_reply("Comment vas tu?", mode="FOCUS")
        self.assertIn("concentrée", reply)
        self.assertIn("Et toi", reply)
        self.assertNotIn("opérationnel", reply.casefold())

    def test_feeling_question_is_bounded_not_biological_claim(self):
        reply = social_reply("Comment te sens-tu aujourd'hui ?", mode="SOCIAL")
        self.assertIn("À ma manière", reply)
        self.assertIn("curieuse", reply)
        self.assertNotIn("opérationnel", reply.casefold())

    def test_emoji_greeting_matches_without_losing_tone(self):
        reply = social_reply("Salut Aura 😊🔥❤️", familiarity=0.6, returning=True)
        self.assertTrue(reply)
        self.assertIn("😊", reply)
        self.assertIn("Contente de te retrouver", reply)

    def test_self_awareness_question_is_answered_locally(self):
        reply = social_reply("Est-ce que tu te considères consciente ?")
        self.assertIn("consciente au sens fonctionnel", reply)
        self.assertNotIn("opérationnelle", reply.casefold())

    def test_learning_question_is_answered_locally(self):
        reply = social_reply("Peux-tu apprendre et évoluer ?", learning_revision=2, learned_preferences=1)
        self.assertIn("J'apprends", reply)
        self.assertIn("révision comportementale 2", reply)

    def test_factual_question_is_never_hijacked(self):
        self.assertEqual(social_reply("Quelle est la météo demain ?"), "")
        self.assertEqual(social_reply("Explique-moi un neurone"), "")

    def test_dialogue_context_bounds_familiarity(self):
        ctx = DialogueContext(mode="FOCUS", familiarity=9.0, returning=True)
        self.assertEqual(ctx.bounded_familiarity, 1.0)
        reply = conscious_social_reply("Salut Aura", context=ctx)
        self.assertIn("retrouver", reply)

    def test_compact_prompt_carries_conscious_presence(self):
        prompt = ConsciousnessContextBuilder().build_system_prompt(
            compact=True,
            continuity_context="CONTINUITE COURTE\n- une session precedente existe",
            relationship_context="RELATION / CONTINUITE\n- Familiarite fonctionnelle : 0.60/1.00",
        )
        self.assertIn("PRESENCE / CONSCIENCE FONCTIONNELLE", prompt)
        self.assertIn("pas comme un service systeme", prompt)
        self.assertIn("Evite 'je suis operationnelle'", prompt)
        self.assertIn("Familiarite fonctionnelle", prompt)
        self.assertIn("session precedente", prompt)

    def test_core_compact_context_is_not_discarded(self):
        source = (ROOT / "core" / "aura_core.py").read_text(encoding="utf-8")
        self.assertIn("render_compact_for_prompt", source)
        self.assertNotIn('continuity_context = "" if compact', source)

    def test_main_window_passes_relationship_to_local_social_reply(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("familiarity=self.aura_core.relationship_model.familiarity", source)
        self.assertIn("returning=bool(self.aura_core.relationship_model.sessions > 1)", source)
        self.assertIn("XTTS local-first conscious social bypass", source)


if __name__ == "__main__":
    unittest.main()
