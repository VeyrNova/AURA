import unittest
from pathlib import Path

from config.settings import settings
from consciousness.context_builder import ConsciousnessContextBuilder
from voice.text_to_speech import sanitize_for_speech

ROOT = Path(__file__).resolve().parents[1]


class ConversationWorkspaceEmojiV072Tests(unittest.TestCase):
    def test_public_version_stays_072(self):
        self.assertEqual(settings.APP_VERSION, "0.7.2")

    def test_conversation_workspace_markers_exist(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        popup = (ROOT / "ui" / "conversation_popup.py").read_text(encoding="utf-8")
        self.assertIn('setObjectName("conversationPopupSurface")', popup)
        self.assertIn('setObjectName("conversationPopupTitleBar")', popup)
        self.assertIn('QLabel("AURA • CONVERSATION")', popup)
        self.assertIn('self.context_panel.setMinimumWidth(270)', popup)
        self.assertIn('self.chat_panel.set_thinking(True, "AURA RÉFLÉCHIT")', main)

    def test_chat_panel_is_plain_text_unicode_safe(self):
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("QPlainTextEdit", chat)
        self.assertIn("setTextFormat(Qt.PlainText)", chat)
        self.assertIn("toPlainText().strip()", chat)
        self.assertIn("Shift+Enter", chat)
        self.assertIn("Segoe UI Emoji", main)
        self.assertNotIn('.encode("ascii")', chat)

    def test_prompt_explicitly_understands_and_may_use_emojis(self):
        builder = ConsciousnessContextBuilder(user_name="")
        full = builder.build_system_prompt(compact=False)
        compact = builder.build_system_prompt(compact=True)
        for prompt in (full, compact):
            self.assertIn("emojis Unicode", prompt)
        self.assertIn("Tu peux utiliser toi-meme des emojis", full)

    def test_history_preserves_emoji_verbatim(self):
        text = "Salut AURA 😊🔥 — famille 👨‍👩‍👧"
        messages = ConsciousnessContextBuilder(user_name="").build_messages(
            [{"role": "user", "content": text}], compact=True
        )
        self.assertEqual(messages[-1]["content"], text)

    def test_visual_emoji_stay_silent_in_tts_payload(self):
        spoken = sanitize_for_speech("Ça marche 😊🔥, je m'en occupe ✨")
        self.assertEqual(spoken, "Ça marche , je m'en occupe")
        self.assertNotIn("😊", spoken)
        self.assertNotIn("🔥", spoken)
        self.assertNotIn("✨", spoken)

    def test_clear_context_does_not_touch_persistent_memory(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        block = main[main.index("def _clear_conversation_context"):main.index("def _on_home_message")]
        self.assertIn("self.aura_core.conversation_history.clear()", block)
        self.assertNotIn("memory_manager", block)
        self.assertIn("persistent memory preserved", block)

    def test_ambient_greeting_policy_remains_locked(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("Home display policy=ambient conversation_autoshow=False", main)


if __name__ == "__main__":
    unittest.main()
