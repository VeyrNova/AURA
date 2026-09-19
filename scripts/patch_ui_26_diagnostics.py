from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
CHAT = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
MODULES = (ROOT / "ui" / "final_modules.py").read_text(encoding="utf-8")

checks = {
    "conversation_header_38px": 'conv_header.setFixedHeight(38)' in MAIN,
    "conversation_context_272px": 'self.conversation_context.setFixedWidth(272)' in MAIN,
    "conversation_compact_margins": 'conv_lay.setContentsMargins(8,7,8,9)' in MAIN,
    "vector_role_avatars": 'class _ConversationAvatar(QWidget)' in CHAT and 'QPainter(self)' in CHAT,
    "aura_card_wider_than_user": 'bubble.setMaximumWidth(920 if role == "aura" else 730)' in CHAT,
    "dense_feed_spacing": 'self._feed_layout.setSpacing(7)' in CHAT,
    "wide_multiline_composer": 'QPlainTextEdit' in CHAT and 'Parle-moi ou écris ton message…' in CHAT,
    "emoji_plaintext_preserved": 'setTextFormat(Qt.PlainText)' in CHAT and 'Segoe UI Emoji' in MAIN,
    "split_context_cards": 'conversationContextBlock' in MODULES and 'conversationSuggestionsBlock' in MODULES,
    "context_clear_non_destructive": 'persistent memory preserved' in MAIN,
    "ambient_policy_preserved": 'Home display policy=ambient conversation_autoshow=False' in MAIN,
    "explicit_conversation_only": 'if is_explicit_conversation_ui_request(text):' in MAIN,
    "no_opengl_payload_dependency": 'opengl_orb_surface' not in CHAT and 'opengl_orb_surface' not in MODULES,
    "no_xtts_payload_dependency": 'XTTSTTS' not in CHAT and 'XTTSTTS' not in MODULES,
    "public_version_not_hardcoded": 'APP_VERSION = "0.7.2"' not in MAIN + CHAT + MODULES,
}

print("=== PATCH UI 26 DIAGNOSTICS ===")
failed = []
for name, ok in checks.items():
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok:
        failed.append(name)
print(f"\n{len(checks)-len(failed)}/{len(checks)} PASS")
if failed:
    print("FAILED:", ", ".join(failed))
    sys.exit(1)
