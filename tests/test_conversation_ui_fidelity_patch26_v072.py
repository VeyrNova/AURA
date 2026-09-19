from __future__ import annotations

import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]


class ConversationUIFidelityPatch26V072Tests(unittest.TestCase):
    def test_public_version_stays_072(self):
        self.assertEqual(settings.APP_VERSION, "0.7.2")

    def test_workspace_uses_compact_reference_geometry(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("conv_lay.setContentsMargins(8,7,8,9)", main)
        self.assertIn('conv_header.setFixedHeight(38)', main)
        self.assertIn('self.conversation_context.setFixedWidth(272)', main)
        self.assertIn('QLabel("CONVERSATION EN COURS")', main)

    def test_reference_style_is_flat_and_thin_bordered(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("border: 1px solid #202153", main)
        self.assertIn("border-radius: 7px", main)
        self.assertIn("background-color: rgba(1, 4, 13, 252)", main)
        self.assertIn("font-size: 12px", main)

    def test_role_avatars_are_vector_painted(self):
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn("class _ConversationAvatar(QWidget)", chat)
        self.assertIn("QPainter(self)", chat)
        self.assertIn("QPainterPath()", chat)
        self.assertIn('avatar = _ConversationAvatar(role)', chat)

    def test_message_card_widths_follow_reference_hierarchy(self):
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn('bubble.setMaximumWidth(920 if role == "aura" else 730)', chat)
        self.assertIn('bubble_col.setContentsMargins(13, 8, 13, 9)', chat)
        self.assertIn('self._feed_layout.setSpacing(7)', chat)

    def test_composer_is_wide_multiline_and_emoji_safe(self):
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn("QPlainTextEdit", chat)
        self.assertIn('setPlaceholderText("Parle-moi ou écris ton message…")', chat)
        self.assertIn("Shift+Enter", chat)
        self.assertIn("setTextFormat(Qt.PlainText)", chat)
        self.assertIn("Segoe UI Emoji", (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8"))

    def test_context_rail_is_split_into_two_reference_cards(self):
        modules = (ROOT / "ui" / "final_modules.py").read_text(encoding="utf-8")
        self.assertIn('self.setObjectName("conversationContextRail")', modules)
        self.assertIn('context.setObjectName("conversationContextBlock")', modules)
        self.assertIn('suggestions.setObjectName("conversationSuggestionsBlock")', modules)
        self.assertIn('QLabel("CONTEXTE ACTIF")', modules)
        self.assertIn('QLabel("SUGGESTIONS")', modules)

    def test_clear_context_remains_non_destructive(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        block = main[main.index("def _clear_conversation_context"):main.index("def _on_home_message")]
        self.assertIn("self.aura_core.conversation_history.clear()", block)
        self.assertNotIn("memory_manager", block)
        self.assertIn("persistent memory preserved", block)

    def test_ambient_policy_remains_locked(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("Home display policy=ambient conversation_autoshow=False", main)
        self.assertIn("if is_explicit_conversation_ui_request(text):", main)

    def test_patch_does_not_redefine_voice_or_opengl_behavior(self):
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        modules = (ROOT / "ui" / "final_modules.py").read_text(encoding="utf-8")
        self.assertNotIn("from voice.xtts", chat + modules)
        self.assertNotIn("from ui.opengl", chat + modules)


if __name__ == "__main__":
    unittest.main()
