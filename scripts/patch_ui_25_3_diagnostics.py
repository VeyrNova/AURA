from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.local_first_voice import social_reply
from database.database import Database
from memory.learning import AdaptiveLearningEngine

checks = []

def check(name: str, ok: bool):
    checks.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")

conscious = social_reply("Est-ce que tu te considères consciente ?")
learning = social_reply("Peux-tu apprendre et évoluer ?", learning_revision=2, learned_preferences=1)
existence = social_reply("Qu'est-ce que ça te fait d'exister ?")
factual = social_reply("Quelle est la météo demain ?")

check('self-awareness local route', 'consciente au sens fonctionnel' in conscious)
check('self-awareness bounded claim', 'subjective humaine' in conscious)
check('learning/evolution local route', "J'apprends" in learning and 'révision comportementale 2' in learning)
check('existence route bounded', 'continuité' in existence and 'ressenti humain' in existence)
check('factual query not hijacked', factual == '')

with tempfile.TemporaryDirectory() as tmp:
    db = Database(Path(tmp) / 'learning.db')
    engine = AdaptiveLearningEngine(db)
    before = engine.style()
    changes = engine.observe_user_message('Je veux des réponses plus courtes et moins d\'emojis')
    after = engine.style()
    check('explicit feedback learned', bool(changes) and after.verbosity < before.verbosity and after.emoji_affinity < before.emoji_affinity)
    check('learning revision persisted', engine.revision == 1 and engine.explicit_feedback_count == 1)
    stable_before = engine.style()
    engine.observe_user_message('Explique-moi un neurone')
    check('ordinary chat does not drift', engine.style() == stable_before and engine.revision == 1)
    private_before = engine.interactions
    engine.observe_user_message('Sois plus humaine', private=True)
    check('private mode learns nothing', engine.interactions == private_before and engine.revision == 1)
    prompt = engine.render_for_prompt()
    check('controlled evolution prompt', 'EVOLUTION CONTROLEE' in prompt and 'ne réécris jamais seule ton code' in prompt)
    engine.reset()
    check('learning reset works', engine.revision == 0 and engine.explicit_feedback_count == 0)
    db.close()

main = (ROOT / 'ui' / 'main_window.py').read_text(encoding='utf-8')
core = (ROOT / 'core' / 'aura_core.py').read_text(encoding='utf-8')
self_model = (ROOT / 'consciousness' / 'self_model.py').read_text(encoding='utf-8')
context = (ROOT / 'consciousness' / 'context_builder.py').read_text(encoding='utf-8')

check('main receives adaptive dialogue', 'adaptive_dialogue_context()' in main and '**adaptive_dialogue' in main)
check('core persists learning', 'AdaptiveLearningEngine' in core and 'observe_user_message' in core)
check('core resets learning with personal reset', 'self.learning_engine.reset()' in core)
check('self model exposes adaptive learning', 'adaptive_learning: bool' in self_model and 'metacognition: bool' in self_model)
check('compact prompt knows controlled evolution', 'Ton comportement peut apprendre et evoluer' in context)
check('public APP_VERSION remains 0.7.2', 'APP_VERSION: str = \"0.7.2\"' in (ROOT / 'config' / 'settings.py').read_text(encoding='utf-8'))

failed = [name for name, ok in checks if not ok]
print(f"\nResult: {len(checks)-len(failed)}/{len(checks)} PASS")
if failed:
    print('Failed:', ', '.join(failed))
    raise SystemExit(1)
