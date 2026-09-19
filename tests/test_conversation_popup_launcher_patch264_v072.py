from __future__ import annotations

import unittest
from pathlib import Path

from config.settings import settings
from ui.display_policy import conversation_ui_command, is_explicit_conversation_ui_request

ROOT = Path(__file__).resolve().parents[1]


class ConversationPopupLauncherPatch264V072Tests(unittest.TestCase):
    def test_public_version_stays_072(self):
        self.assertEqual(settings.APP_VERSION, "0.7.2")

    def test_primary_launch_phrase(self):
        self.assertEqual(conversation_ui_command("lance le mode conversation"), "open")

    def test_voice_and_text_variants(self):
        variants = (
            "ouvre le mode conversation",
            "active le mode conversation",
            "ouvre la conversation",
            "lance la conversation",
            "passe en mode conversation",
            "affiche la fenêtre de conversation",
            "ouvre la fenêtre conversation",
            "Aura, lance le mode conversation",
            "Bonjour Aura, ouvre la conversation",
        )
        for value in variants:
            with self.subTest(value=value):
                self.assertEqual(conversation_ui_command(value), "open")
                self.assertTrue(is_explicit_conversation_ui_request(value))

    def test_close_variants(self):
        for value in (
            "ferme la conversation",
            "quitte le mode conversation",
            "désactive le mode conversation",
            "retourne à l'accueil",
            "reviens sur accueil",
        ):
            with self.subTest(value=value):
                self.assertEqual(conversation_ui_command(value), "close")

    def test_social_and_search_phrases_are_not_hijacked(self):
        for value in (
            "Bonjour Aura",
            "Comment vas-tu ?",
            "cherche la chanson conversation",
            "parle-moi de la conversation humaine",
        ):
            with self.subTest(value=value):
                self.assertEqual(conversation_ui_command(value), "")

    def test_popup_is_true_child_tool_window(self):
        popup = (ROOT / "ui" / "conversation_popup.py").read_text(encoding="utf-8")
        self.assertIn('Qt.Tool | Qt.FramelessWindowHint', popup)
        self.assertIn('self.setModal(False)', popup)
        self.assertIn('def show_centered', popup)
        self.assertIn('width = min(1220, max(900, int(pw * 0.64)))', popup)
        self.assertIn('height = min(860, max(680, int(ph * 0.82)))', popup)
        self.assertIn('width = min(width, max(760, pw - 120))', popup)
        self.assertIn('height = min(height, max(620, ph - 90))', popup)

    def test_main_shell_remains_visible(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        helper = main[main.index('def _open_conversation_popup'):main.index('def _apply_conversation_suggestion')]
        self.assertNotIn('widget.setVisible(not enabled)', helper)
        self.assertIn('self._conversation_dimmer', main)
        self.assertIn('popup.show_centered', helper)

    def test_ui_command_preempts_llm_routing_for_voice_and_text(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('def _handle_conversation_ui_command', main)
        user_method = main[main.index('def _on_user_message'):main.index('def _continue_after_agent_router')]
        self.assertLess(
            user_method.index('if self._handle_conversation_ui_command(text):'),
            user_method.index('if self._llm_thread is not None:'),
        )
        home_method = main[main.index('def _on_home_message'):main.index('def _results_geometry')]
        self.assertIn('if self._handle_conversation_ui_command(text):', home_method)

    def test_user_name_is_dynamic_with_vous_fallback(self):
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn('getattr(settings, "USER_NAME", "")', chat)
        self.assertIn('or "VOUS"', chat)
        self.assertNotIn('QLabel("K-0S" if role == "user" else "AURA")', chat)

    def test_popup_close_does_not_close_main_window(self):
        popup = (ROOT / "ui" / "conversation_popup.py").read_text(encoding="utf-8")
        self.assertIn('self.close_button.clicked.connect(self.hide)', popup)
        self.assertIn('def reject(self)', popup)
        self.assertIn('self.hide()', popup)

    def test_ambient_greeting_policy_is_unchanged(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('Home display policy=ambient conversation_autoshow=False', main)
        self.assertEqual(conversation_ui_command("Bonjour Aura."), "")


if __name__ == "__main__":
    unittest.main()
