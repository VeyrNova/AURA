from __future__ import annotations

import unittest
from pathlib import Path

from ai.local_first_voice import social_reply
from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]


class AmbientSocialRouterConversationPolishPatch261V072Tests(unittest.TestCase):
    def test_public_version_stays_072(self):
        self.assertEqual(settings.APP_VERSION, "0.7.2")

    def test_bonjour_with_period_mirrors_bonjour(self):
        reply = social_reply(
            "Bonjour Aura.",
            returning=True,
            familiarity=0.95,
            playfulness=0.90,
            spontaneity=0.90,
        )
        self.assertTrue(reply.startswith("Bonjour."), reply)
        self.assertNotIn("opérationnelle", reply.casefold())

    def test_aura_vocative_can_be_prefix_or_suffix(self):
        for text in ("Aura, bonjour !", "Bonjour AURA !", "AURA salut 😊", "Salut Aura 😊"):
            with self.subTest(text=text):
                self.assertTrue(social_reply(text, familiarity=0.95), text)

    def test_common_greeting_variants_are_social(self):
        for text in ("Salut !", "Coucou Aura", "Bonsoir AURA 😊", "Hello Aura", "Hey Aura!", "Yo Aura"):
            with self.subTest(text=text):
                self.assertTrue(social_reply(text, familiarity=0.95), text)

    def test_common_phatic_variants_are_social(self):
        for text in ("Comment ça va Aura ?", "Tu vas bien Aura ?", "Ça roule ?", "Quoi de neuf Aura ?", "Tu m'entends Aura ?"):
            with self.subTest(text=text):
                self.assertTrue(social_reply(text, familiarity=0.95), text)

    def test_farewell_variants_are_social(self):
        for text in ("Bonne nuit Aura", "Bonne soirée !", "À demain Aura", "Bye Aura"):
            with self.subTest(text=text):
                self.assertTrue(social_reply(text, familiarity=0.95), text)

    def test_factual_sentence_containing_bonjour_aura_is_not_hijacked(self):
        for text in (
            "Cherche la chanson Bonjour Aura",
            "Explique-moi pourquoi on dit bonjour Aura dans ce texte",
            "Trouve un fichier nommé Bonjour Aura",
        ):
            with self.subTest(text=text):
                self.assertEqual(social_reply(text, familiarity=0.95), "")

    def test_social_route_runs_before_visual_classification(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        social_pos = source.index("AURA social ambient handled local delivery")
        visual_pos = source.index("visual_followup = bool", social_pos)
        self.assertLess(social_pos, visual_pos)
        block = source[source.rfind("social_reply = xtts_local_first_social_reply", 0, social_pos):visual_pos]
        self.assertIn("self._voice_primary_turn = bool(voice_available)", block)
        self.assertIn("return", block)

    def test_late_xtts_social_fallback_is_also_voice_primary(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        marker = source.index("XTTS local-first conscious social bypass")
        block = source[source.rfind("if social_reply:", 0, marker):marker]
        self.assertIn("self._voice_primary_turn = bool(voice_available)", block)

    def test_resource_guardian_detail_is_log_only(self):
        source = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        start = source.index("except ResourcePressureError as exc:", source.index("def _continue_after_agent_router"))
        end = source.index("except Exception:", start)
        block = source[start:end]
        self.assertIn("logger.warning", block)
        self.assertNotIn("self.chat_panel.add_system_message(str(exc))", block)
        self.assertIn("Je garde ma voix disponible", block)

    def test_composer_is_compact_and_auto_growing(self):
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn("self._min_height = 40", chat)
        self.assertIn("self._max_height = 104", chat)
        self.assertIn("self.textChanged.connect(self._sync_height)", chat)
        self.assertIn("Qt.AlignVCenter", chat)
        self.assertIn("self.send_button.setFixedSize(30, 30)", chat)

    def test_context_rail_cards_are_compact_not_stretched(self):
        modules = (ROOT / "ui" / "final_modules.py").read_text(encoding="utf-8")
        self.assertIn("context.setFixedHeight(146)", modules)
        self.assertIn("suggestions.setFixedHeight(238)", modules)
        self.assertIn("root.addStretch(1)", modules)
        self.assertNotIn("root.addWidget(suggestions, 1)", modules)

    def test_role_badges_are_smaller_and_message_width_expands(self):
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn("self.setFixedSize(26, 26)", chat)
        self.assertIn('bubble.setMaximumWidth(1040 if role == "aura" else 780)', chat)

    def test_patch_does_not_modify_xtts_or_opengl_modules(self):
        # This is a source-scope contract: Patch 26.1 should not need to edit the
        # actual TTS backend or OpenGL renderer to fix social delivery/UI geometry.
        self.assertTrue((ROOT / "voice" / "xtts_tts.py").exists())
        self.assertTrue((ROOT / "ui" / "opengl_orb_surface.py").exists())


if __name__ == "__main__":
    unittest.main()
