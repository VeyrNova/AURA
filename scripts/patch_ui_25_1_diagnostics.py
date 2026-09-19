from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

checks = []

def check(name: str, ok: bool):
    checks.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")

main = (ROOT / 'ui' / 'main_window.py').read_text(encoding='utf-8')
chat = (ROOT / 'ui' / 'chat_panel.py').read_text(encoding='utf-8')
route = (ROOT / 'ai' / 'voice_routing.py').read_text(encoding='utf-8')
social = (ROOT / 'ai' / 'local_first_voice.py').read_text(encoding='utf-8')
xtts = (ROOT / 'voice' / 'xtts_tts.py').read_text(encoding='utf-8')

check('legacy HTML normalizer exists', 'def normalize_conversation_text' in chat)
check('emoji font fallback preserved', 'Segoe UI Emoji' in main)
check('conversation result card exists', 'class _ResultCard' in chat and 'def add_result_card' in chat)
check('visual results embed in conversation', 'Visual Result embedded in conversation' in main)
check('embedded result duplicate suppression', 'Conversation duplicate bubble suppressed after embedded result' in main)
check('knowledge reference preempts fast router', 'Deterministic knowledge reference preempts Fast Intelligence Router' in main)
check('social feeling route is recognized', 'comment te sens tu' in route)
check('social local-first reply exists', 'Tous mes systèmes sont opérationnels' in social)
check('TTS worker cancellation event exists', 'self._cancel_event = threading.Event()' in main)
check('closeEvent cancels TTS worker', 'Fermeture: worker TTS annulé avant shutdown' in main)
check('shutdown discards pending speech work', 'TTS cleanup during shutdown: pending/fallback/prewarm discarded' in main)
check('XTTS checks cancellation after load', 'XTTS native stream annulé pendant le chargement du modèle' in xtts)
check('XTTS checks cancellation after conditioning', 'XTTS native stream annulé pendant le conditionnement' in xtts)
settings_text = (ROOT / 'config' / 'settings.py').read_text(encoding='utf-8') if (ROOT / 'config' / 'settings.py').exists() else ''
check('public version remains 0.7.2', 'APP_VERSION: str = "0.7.2"' in settings_text)

failed = [name for name, ok in checks if not ok]
print(f"\nPatch 25.1 diagnostics: {len(checks)-len(failed)}/{len(checks)} PASS")
if failed:
    print('Failures: ' + ', '.join(failed))
    sys.exit(1)
