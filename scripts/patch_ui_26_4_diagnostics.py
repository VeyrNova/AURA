from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
main = (ROOT / 'ui' / 'main_window.py').read_text(encoding='utf-8')
popup = (ROOT / 'ui' / 'conversation_popup.py').read_text(encoding='utf-8')
chat = (ROOT / 'ui' / 'chat_panel.py').read_text(encoding='utf-8')
policy = (ROOT / 'ui' / 'display_policy.py').read_text(encoding='utf-8')
settings = (ROOT / 'config' / 'settings.py').read_text(encoding='utf-8')

checks: list[tuple[str, bool]] = []
def check(name: str, ok: bool) -> None:
    checks.append((name, bool(ok)))

check('popup_module_exists', (ROOT / 'ui' / 'conversation_popup.py').exists())
check('popup_is_tool_window', 'Qt.Tool | Qt.FramelessWindowHint' in popup)
check('popup_non_modal', 'self.setModal(False)' in popup)
check('popup_smaller_than_parent_width', 'pw - 120' in popup)
check('popup_smaller_than_parent_height', 'ph - 90' in popup)
check('popup_centered', 'def show_centered' in popup and 'parent.mapToGlobal' in popup)
check('popup_escape_hides_only_popup', 'def reject(self)' in popup and 'self.hide()' in popup)
check('main_shell_not_hidden_for_conversation', 'widget.setVisible(not enabled)' not in main[main.index('def _set_conversation_shell_mode'):main.index('def _apply_conversation_suggestion')])
check('dimmer_overlay_present', 'conversationDimmer' in main and '_conversation_dimmer' in main)
check('popup_open_helper', 'def _open_conversation_popup' in main)
check('popup_close_helper', 'def _close_conversation_popup' in main)
check('text_voice_ui_command_preempts_llm', 'if self._handle_conversation_ui_command(text):' in main)
check('primary_phrase_supported', 'lance|lancer' in policy and 'mode\\s+' in policy)
check('close_phrase_supported', 'ferme|fermer|quitte|quitter' in policy)
check('bonjour_not_hijacked_by_ui_command', '_strip_aura_address' in policy)
check('dynamic_user_name', 'getattr(settings, "USER_NAME", "")' in chat)
check('vous_fallback', 'or "VOUS"' in chat)
check('k0s_not_hardcoded_as_user_role', 'QLabel("K-0S" if role == "user" else "AURA")' not in chat)
check('reference_72_28_layout', 'body_layout.addWidget(self.chat_panel, 72)' in popup and 'body_layout.addWidget(self.context_panel, 28)' in popup)
check('app_version_remains_072', 'APP_VERSION' in settings and '0.7.2' in settings)

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
print(f"\nPatch 26.4 diagnostics: {len(checks)-len(failed)}/{len(checks)} PASS")
if failed:
    raise SystemExit('FAILED: ' + ', '.join(failed))
