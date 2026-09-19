from __future__ import annotations

import unittest
from pathlib import Path

from ai.local_first_voice import self_reply
from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]


class ConversationPopupVisualFidelitySelfStatePatch265V072Tests(unittest.TestCase):
    def test_public_version_stays_072(self):
        self.assertEqual(settings.APP_VERSION, "0.7.2")

    def test_stt_ressents_typo_is_local(self):
        for text in (
            "Que ressents tu?",
            "Qu'est-ce que tu ressents ?",
            "Tu ressents quoi ?",
            "Qu'est-ce que tu éprouves ?",
            "Tu éprouves quoi ?",
        ):
            with self.subTest(text=text):
                reply = self_reply(text, familiarity=0.95)
                self.assertTrue(reply, text)
                self.assertNotIn("moteur", reply.casefold())

    def test_comment_tu_te_sens_is_local_social_state(self):
        self.assertTrue(self_reply("Comment tu te sens ?", familiarity=0.95))

    def test_external_feelings_are_not_hijacked(self):
        self.assertEqual(self_reply("Qu'est-ce que le personnage éprouve dans ce film ?", familiarity=0.95), "")

    def test_popup_size_contract_is_unchanged(self):
        popup = (ROOT / "ui" / "conversation_popup.py").read_text(encoding="utf-8")
        self.assertIn("width = min(1220, max(900, int(pw * 0.64)))", popup)
        self.assertIn("height = min(860, max(680, int(ph * 0.82)))", popup)

    def test_visual_fidelity_tokens_present(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        popup = (ROOT / "ui" / "conversation_popup.py").read_text(encoding="utf-8")
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn("QGraphicsDropShadowEffect", popup)
        self.assertIn("shadow.setBlurRadius(52.0)", popup)
        self.assertIn("font-size: 14px; line-height: 1.30;", main)
        self.assertIn("QLabel#conversationContextStatusValue", main)
        self.assertIn("self.setFixedSize(30, 30)", chat)
        self.assertIn("bubble.setMinimumHeight(58)", chat)

    def test_dynamic_user_name_preserved(self):
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn('getattr(settings, "USER_NAME", "")', chat)
        self.assertIn('or "VOUS"', chat)


if __name__ == "__main__":
    unittest.main()
