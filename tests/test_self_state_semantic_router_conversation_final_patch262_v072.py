from __future__ import annotations

import unittest
from pathlib import Path

from ai.local_first_voice import self_reply, social_reply
from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]


class SelfStateSemanticRouterConversationFinalPatch262V072Tests(unittest.TestCase):
    def test_public_version_stays_072(self):
        self.assertEqual(settings.APP_VERSION, "0.7.2")

    def test_emotion_family_is_answered_locally(self):
        variants = (
            "Quelles sont tes émotions ?",
            "Que ressens-tu ?",
            "Qu'est-ce que tu ressens en ce moment ?",
            "Est-ce que tu ressens quelque chose ?",
            "As-tu des émotions ?",
            "Peux-tu ressentir des émotions ?",
            "As-tu des sentiments ?",
            "Quelle est ton humeur ?",
        )
        for text in variants:
            with self.subTest(text=text):
                reply = self_reply(text, familiarity=0.95)
                self.assertTrue(reply, text)
                self.assertNotIn("moteur", reply.casefold())
                self.assertNotIn("ollama", reply.casefold())

    def test_specific_self_state_families_are_bounded(self):
        cases = {
            "Tu peux avoir peur ?": "prudence",
            "Es-tu heureuse ?": "humain",
            "Est-ce que tu es triste ?": "tristesse",
            "Tu peux te mettre en colère ?": "colère",
            "Qu'est-ce qui te rend curieuse ?": "curiosité",
            "Tu m'aimes ?": "amour humain",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                reply = self_reply(text, familiarity=0.95)
                self.assertTrue(reply, text)
                self.assertIn(expected.casefold(), reply.casefold())

    def test_external_emotion_questions_are_not_hijacked(self):
        for text in (
            "Quelles émotions sont présentes dans ce film ?",
            "Explique les émotions du personnage principal",
            "Cherche un article sur les émotions humaines",
        ):
            with self.subTest(text=text):
                self.assertEqual(self_reply(text, familiarity=0.95), "")

    def test_social_defensive_route_also_knows_self_state(self):
        self.assertTrue(social_reply("Quelles sont tes émotions ?", familiarity=0.95))

    def test_self_state_route_precedes_visual_and_model_routing(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self_pos = main.index("AURA self dialogue handled local delivery")
        visual_pos = main.index("visual_followup = bool", self_pos)
        self.assertLess(self_pos, visual_pos)
        block = main[main.rfind("self_reply = xtts_local_first_self_reply", 0, self_pos):visual_pos]
        self.assertIn("self._voice_primary_turn = bool(voice_available)", block)
        self.assertIn("return", block)

    def test_conversation_widths_are_percentage_driven(self):
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn("min_ratio, max_ratio, growth_chars = 0.56, 0.70, 230.0", chat)
        self.assertIn("min_ratio, max_ratio, growth_chars = 0.43, 0.52, 170.0", chat)
        self.assertIn("def _apply_feed_widths", chat)
        self.assertIn("def resizeEvent", chat)
        self.assertIn("card.apply_available_width", chat)

    def test_conversation_readability_is_increased(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("QLabel#messageRoleUser { color: #67b7ff; font-size: 10px;", main)
        self.assertIn("QLabel#messageRoleAura { color: #9f72ff; font-size: 10px;", main)
        self.assertIn("QLabel#messageTime { color: #65738e; font-size: 9px; }", main)
        self.assertIn("font-size: 13px; line-height: 1.24;", main)
        self.assertIn("margin-left: 35px; margin-right: 18px;", main)

    def test_patch_scope_does_not_touch_voice_or_opengl_backends(self):
        self.assertTrue((ROOT / "voice" / "xtts_tts.py").exists())
        self.assertTrue((ROOT / "ui" / "opengl_orb_surface.py").exists())


if __name__ == "__main__":
    unittest.main()
