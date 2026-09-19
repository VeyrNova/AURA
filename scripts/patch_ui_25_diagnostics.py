from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

checks = []

def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, bool(ok), detail))


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

main = text("ui/main_window.py")
chat = text("ui/chat_panel.py")
modules = text("ui/final_modules.py")
ctx = text("consciousness/context_builder.py")
tts = text("voice/text_to_speech.py")
settings = text("config/settings.py")

check("version 0.7.2", 'APP_VERSION: str = "0.7.2"' in settings or 'APP_VERSION = "0.7.2"' in settings)
check("conversation workspace", 'setObjectName("conversationWorkspace")' in main)
check("conversation header", 'QLabel("CONVERSATION EN COURS")' in main)
check("context rail", 'class ConversationContextPanel' in modules and 'EFFACER LE CONTEXTE' in modules)
check("wide multiline composer", 'QPlainTextEdit' in chat and 'setMinimumHeight(48)' in chat)
check("enter + shift-enter", 'Qt.Key_Return' in chat and 'Qt.ShiftModifier' in chat)
check("plain text bubbles", chat.count('setTextFormat(Qt.PlainText)') >= 2)
check("emoji display font", 'Segoe UI Emoji' in main)
check("emoji prompt full", 'Tu peux utiliser toi-meme des emojis' in ctx)
check("emoji prompt compact", 'Les emojis Unicode font partie du message' in ctx)
check("emoji silent for TTS", '_EMOJI_FOR_SPEECH_RE.sub(" ", value)' in tts)
check("thinking indicator", 'class _ThinkingIndicator' in chat and 'AURA RÉFLÉCHIT' in main)
check("stream API kept", all(m in chat for m in ('begin_aura_stream', 'append_aura_stream', 'set_aura_stream_text', 'finish_aura_stream')))
check("ambient greeting locked", 'Home display policy=ambient conversation_autoshow=False' in main)
check("persistent memory preserved on clear", 'self.aura_core.conversation_history.clear()' in main and 'memory_manager' not in main[main.index('def _clear_conversation_context'):main.index('def _on_home_message')])

failed = [item for item in checks if not item[1]]
for name, ok, detail in checks:
    suffix = f" — {detail}" if detail else ""
    print(f"{'PASS' if ok else 'FAIL'}  {name}{suffix}")
print(f"\nPatch 25 diagnostics: {len(checks)-len(failed)}/{len(checks)} PASS")
sys.exit(1 if failed else 0)
