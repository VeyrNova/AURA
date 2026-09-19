from __future__ import annotations

import unittest
from pathlib import Path

from config.settings import settings

ROOT = Path(__file__).resolve().parents[1]


class ConversationReferenceRebuildPatch263V072Tests(unittest.TestCase):
    """Regression coverage for 26.3 foundations after 26.4 popup supersession."""

    def test_public_version_stays_072(self):
        self.assertEqual(settings.APP_VERSION, "0.7.2")

    def test_reference_title_moves_to_popup(self):
        popup = (ROOT / "ui" / "conversation_popup.py").read_text(encoding="utf-8")
        self.assertIn('QLabel("AURA • CONVERSATION")', popup)
        self.assertIn('setObjectName("conversationPopupTitleBar")', popup)
        self.assertIn('setObjectName("conversationPopupCloseButton")', popup)

    def test_conversation_grid_stays_reference_weighted(self):
        popup = (ROOT / "ui" / "conversation_popup.py").read_text(encoding="utf-8")
        self.assertIn('body_layout.addWidget(self.chat_panel, 72)', popup)
        self.assertIn('body_layout.addWidget(self.context_panel, 28)', popup)

    def test_user_role_is_dynamic_not_k0s_hardcoded(self):
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn('getattr(settings, "USER_NAME", "")', chat)
        self.assertIn('or "VOUS"', chat)
        self.assertNotIn('QLabel("K-0S" if role == "user" else "AURA")', chat)

    def test_transcript_cards_use_reference_lane_width(self):
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn('ratio = 0.915 if self.role == "aura" else 0.940', chat)

    def test_context_rail_matches_reference_vertical_structure(self):
        modules = (ROOT / "ui" / "final_modules.py").read_text(encoding="utf-8")
        self.assertIn('root.addWidget(suggestions, stretch=1)', modules)
        self.assertIn('suggestions_layout.addStretch(1)', modules)

    def test_attachments_can_live_inside_aura_card(self):
        chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
        self.assertIn('class _AttachmentCard(QFrame)', chat)
        self.assertIn('def add_aura_attachment_message', chat)
        self.assertIn('conversationAudioWaveform', chat)

    def test_ambient_policy_stays_locked(self):
        main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('Home display policy=ambient conversation_autoshow=False', main)
        self.assertIn('if is_explicit_conversation_ui_request(text):', main)


if __name__ == "__main__":
    unittest.main()
