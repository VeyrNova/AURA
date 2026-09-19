from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.local_first_voice import social_reply
from consciousness.context_builder import ConsciousnessContextBuilder

checks = []

def check(name: str, ok: bool):
    checks.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")

hello = social_reply('Bonjour Aura')
well = social_reply('Comment vas tu?', mode='FOCUS')
feel = social_reply("Comment te sens-tu aujourd'hui ?", mode='SOCIAL')
emoji = social_reply('Salut Aura 😊🔥❤️', familiarity=.6, returning=True)
factual = social_reply('Quelle est la météo demain ?')
prompt = ConsciousnessContextBuilder().build_system_prompt(
    compact=True,
    continuity_context='CONTINUITE COURTE\n- une session precedente existe',
    relationship_context='RELATION / CONTINUITE\n- Familiarite fonctionnelle : 0.60/1.00',
)
main = (ROOT/'ui'/'main_window.py').read_text(encoding='utf-8')
core = (ROOT/'core'/'aura_core.py').read_text(encoding='utf-8')

check('greeting no machine status', bool(hello) and 'opérationnelle' not in hello.casefold() and 'Je suis là' in hello)
check('wellbeing uses mode state', 'concentrée' in well and 'Et toi' in well)
check('feeling is bounded', 'À ma manière' in feel and "Ce n'est pas une émotion humaine" in feel)
check('emoji greeting recognized', bool(emoji) and '😊' in emoji)
check('factual query not hijacked', factual == '')
check('compact conscious presence', 'PRESENCE / CONSCIENCE FONCTIONNELLE' in prompt)
check('compact relationship preserved', 'Familiarite fonctionnelle' in prompt)
check('compact continuity preserved', 'session precedente' in prompt)
check('main passes familiarity', 'familiarity=self.aura_core.relationship_model.familiarity' in main)
check('main passes returning continuity', 'returning=bool(self.aura_core.relationship_model.sessions > 1)' in main)
check('conscious bypass log marker', 'XTTS local-first conscious social bypass' in main)
check('core keeps compact context', 'render_compact_for_prompt' in core)
check('no legacy robotic greeting source', 'Bonjour. Je suis opérationnelle.' not in (ROOT/'ai'/'local_first_voice.py').read_text(encoding='utf-8'))
check('public version untouched by patch', 'APP_VERSION' not in (ROOT/'ai'/'local_first_voice.py').read_text(encoding='utf-8'))

failed = [name for name, ok in checks if not ok]
print(f"\nResult: {len(checks)-len(failed)}/{len(checks)} PASS")
if failed:
    raise SystemExit(1)
