from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.local_first_voice import self_reply
from database.database import Database
from memory.learning import AdaptiveLearningEngine

checks = []

def check(name: str, ok: bool):
    checks.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")

ctx = dict(
    learning_revision=2,
    learned_preferences=1,
    learning_interactions=12,
    last_learning_change='style plus direct',
)
learning = self_reply('Peux-tu apprendre et évoluer ?', **ctx)
identity = self_reply('Qui es-tu ?', **ctx)
existence = self_reply("Qu'est-ce que ça te fait d'exister ?", **ctx)
activity = self_reply('Que fais-tu ?', **ctx)
evolution = self_reply("Comment as-tu changé depuis qu'on se parle ?", **ctx)
factual = self_reply('Quelle est la météo demain ?', **ctx)

check('learning self route local', "J'apprends" in learning and len(learning) > 65)
check('identity self route local', 'IA personnelle locale' in identity)
check('existence self route local', 'continuité' in existence and len(existence) > 65)
check('current activity self route local', 'notre échange' in activity)
check('evolution-history self route local', 'révision comportementale 2' in evolution and 'style plus direct' in evolution)
check('external factual query not hijacked', factual == '')

with tempfile.TemporaryDirectory() as tmp:
    db = Database(Path(tmp) / 'learning.db')
    engine = AdaptiveLearningEngine(db)
    changes = engine.observe_user_message('Sois plus directe')
    ack = engine.acknowledgement(changes)
    check('explicit adaptation acknowledged locally', 'Je m\'adapte' in ack and 'style plus direct' in ack)
    dialogue = engine.dialogue_kwargs()
    check('evolution context includes last change', dialogue.get('last_learning_change') == 'style plus direct')
    check('directness exported to local dialogue', 'directness' in dialogue)
    db.close()

main = (ROOT / 'ui' / 'main_window.py').read_text(encoding='utf-8')
core = (ROOT / 'core' / 'aura_core.py').read_text(encoding='utf-8')
settings = (ROOT / 'config' / 'settings.py').read_text(encoding='utf-8')

start = main.index('def _continue_after_agent_router')
end = main.index('# Build memory/continuity context', start)
segment = main[start:end]
check('self route precedes model routing', segment.index('xtts_local_first_self_reply(') < segment.index('route = classify_voice_route(text)'))
check('self route does not auto-open Conversation', '_switch_page("conversation")' not in segment)
check('voice-primary skips visual-first truncation', 'Voice-primary ambient response' in main and 'if voice_primary:' in main)
check('adaptive feedback stops before LLM', 'Adaptive feedback handled local delivery' in segment and 'adaptive_learning_acknowledgement' in segment)
check('core returns learned changes', 'def handle_user_message(self, text: str) -> list[str]:' in core and 'return list(learned_changes)' in core)
check('public APP_VERSION remains 0.7.2', 'APP_VERSION: str = "0.7.2"' in settings)

failed = [name for name, ok in checks if not ok]
print(f"\nResult: {len(checks)-len(failed)}/{len(checks)} PASS")
if failed:
    print('Failed:', ', '.join(failed))
    raise SystemExit(1)
