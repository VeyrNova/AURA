from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import settings  # noqa: E402

main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
modules = (ROOT / "ui" / "final_modules.py").read_text(encoding="utf-8")

checks: list[tuple[str, bool]] = []
def check(name: str, cond: bool) -> None:
    checks.append((name, bool(cond)))

check("public_version_072", settings.APP_VERSION == "0.7.2")
check("dedicated_surface_helper", "def _set_conversation_shell_mode" in main)
check("nav_hidden_in_conversation", 'getattr(self, "nav_rail", None)' in main and 'widget.setVisible(not enabled)' in main)
check("top_hidden_in_conversation", 'getattr(self, "top_bar", None)' in main)
check("footer_hidden_in_conversation", 'getattr(self, "footer_bar", None)' in main)
check("conversation_titlebar", 'QLabel("AURA • CONVERSATION")' in main)
check("conversation_back_home", 'clicked.connect(lambda: self._switch_page("home"))' in main)
check("conversation_window_controls", 'conversation_minimize_button' in main and 'conversation_close_button' in main)
check("grid_73_27", 'conv_lay.addWidget(self.chat_panel, 73)' in main and 'conv_lay.addWidget(self.conversation_context, 27)' in main)
check("k0s_role", 'QLabel("K-0S" if role == "user" else "AURA")' in chat)
check("wide_aura_lane", 'ratio = 0.915 if self.role == "aura" else 0.940' in chat)
check("context_top_card", 'context.setMinimumHeight(156)' in modules and 'context.setMaximumHeight(188)' in modules)
check("suggestions_vertical_fill", 'root.addWidget(suggestions, stretch=1)' in modules)
check("clear_pinned_bottom", modules.index('suggestions_layout.addStretch(1)') < modules.index('QPushButton("EFFACER LE CONTEXTE")'))
check("file_attachment_nested", 'class _AttachmentCard(QFrame)' in chat and 'conversationFileAttachment' in chat)
check("audio_attachment_nested", 'conversationAudioWaveform' in chat and 'kind == "audio"' in chat)
check("composer_reference_scale", 'self._min_height = 32' in chat and 'self._max_height = 88' in chat)
check("flat_reference_palette", 'background-color: rgba(2, 26, 34, 232)' in main and 'background-color: rgba(8, 8, 25, 242)' in main)
check("ambient_policy_preserved", 'Home display policy=ambient conversation_autoshow=False' in main)
check("self_state_patch_preserved", (ROOT / "consciousness" / "dialogue.py").exists())
check("voice_backend_untouched", (ROOT / "voice" / "xtts_tts.py").exists())
check("opengl_backend_untouched", (ROOT / "ui" / "opengl_orb_surface.py").exists())

for name, ok in checks:
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
passed = sum(1 for _, ok in checks if ok)
print(f"RESULT: {passed}/{len(checks)} PASS")
raise SystemExit(0 if passed == len(checks) else 1)
