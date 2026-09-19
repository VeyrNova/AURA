from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
main = (ROOT / 'ui' / 'main_window.py').read_text(encoding='utf-8')

checks: list[tuple[str, bool]] = []

def check(name: str, ok: bool) -> None:
    checks.append((name, bool(ok)))

check('glyph_map_present', 'COMPOSER_ACTION_GLYPHS' in main)
check('attach_icon_present', '"attach": "📎"' in main)
check('send_icon_present', '"send": "➤"' in main)
check('microphone_icon_present', '"microphone": "🎤"' in main)
check('qabstractbutton_imported', 'QAbstractButton,' in main)
check('role_inference_function_present', 'def infer_composer_action_role(widget: object) -> str:' in main)
check('attach_role_tokens_present', 'composerplus' in main and 'pièce jointe' in main)
check('send_role_tokens_present', 'sendbutton' in main and 'envoyer' in main)
check('microphone_role_tokens_present', 'micbutton' in main and 'microphone' in main)
check('runtime_apply_method_present', 'def _apply_composer_action_icons(self):' in main)
check('runtime_scan_buttons', 'self.findChildren(QAbstractButton)' in main)
check('timer_present', 'self._composer_icon_timer = QTimer(self)' in main)
check('timer_connected', 'self._composer_icon_timer.timeout.connect(self._apply_composer_action_icons)' in main)
check('immediate_refresh_present', 'QTimer.singleShot(0, self._apply_composer_action_icons)' in main)
check('deferred_refresh_present', 'QTimer.singleShot(1200, self._apply_composer_action_icons)' in main)
check('semantic_property_marker', 'auraSemanticActionIcon' in main)
check('tooltip_attach_present', 'Joindre un fichier' in main)
check('tooltip_send_present', 'Envoyer' in main)
check('tooltip_microphone_present', 'Microphone' in main)

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
print(f"\nPatch 26.7 diagnostics: {len(checks) - len(failed)}/{len(checks)} PASS")
if failed:
    raise SystemExit('FAILED: ' + ', '.join(failed))
