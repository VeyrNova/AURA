from __future__ import annotations
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.local_first_voice import self_reply
from config.settings import settings
main=(ROOT/'ui/main_window.py').read_text(encoding='utf-8')
popup=(ROOT/'ui/conversation_popup.py').read_text(encoding='utf-8')
chat=(ROOT/'ui/chat_panel.py').read_text(encoding='utf-8')
dialogue=(ROOT/'consciousness/dialogue.py').read_text(encoding='utf-8')
checks=[]
def check(name, ok): checks.append((name,bool(ok)))
check('app_version_072', settings.APP_VERSION=='0.7.2')
check('popup_size_unchanged', 'width = min(1220, max(900, int(pw * 0.64)))' in popup and 'height = min(860, max(680, int(ph * 0.82)))' in popup)
check('popup_shadow', 'QGraphicsDropShadowEffect' in popup and 'shadow.setBlurRadius(52.0)' in popup)
check('dimmer_stronger', 'rgba(0, 2, 9, 180)' in main)
check('title_larger', 'conversationPopupTitle { color:#ded2ff; font-size:14px' in main)
check('avatar_30', 'self.setFixedSize(30, 30)' in chat)
check('message_min_height', 'bubble.setMinimumHeight(58)' in chat)
check('message_font_14', 'font-size: 14px; line-height: 1.30;' in main)
check('composer_font_12', 'font-size: 12px; selection-background-color' in main)
check('context_status', 'conversationContextStatusValue' in main and '("Statut", "● Actif")' in (ROOT/'ui/final_modules.py').read_text(encoding='utf-8'))
check('dynamic_user_name', 'getattr(settings, "USER_NAME", "")' in chat and 'or "VOUS"' in chat)
check('ressents_alias', '"ressents": "ressens"' in dialogue)
check('eprouves_family', 'qu est ce que tu eprouves' in dialogue)
check('stt_ressents_local', bool(self_reply('Que ressents tu?', familiarity=0.95)))
check('stt_eprouves_local', bool(self_reply("Qu'est-ce que tu éprouves ?", familiarity=0.95)))
check('comment_tu_te_sens_local', bool(self_reply('Comment tu te sens ?', familiarity=0.95)))
check('external_not_hijacked', self_reply("Qu'est-ce que le personnage éprouve dans ce film ?", familiarity=0.95)=='')
failed=[n for n,o in checks if not o]
for n,o in checks: print(f"[{'PASS' if o else 'FAIL'}] {n}")
print(f"\nPatch 26.5 diagnostics: {len(checks)-len(failed)}/{len(checks)} PASS")
if failed: raise SystemExit('FAILED: '+', '.join(failed))
