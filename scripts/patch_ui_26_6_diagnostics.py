from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from tools.internet_manager import InternetToolManager
from tools.search_intent import extract_explicit_search_query, is_explicit_search_request

checks: list[tuple[str, bool]] = []
def check(name: str, ok: bool) -> None:
    checks.append((name, bool(ok)))

check('app_version_defined', bool(str(settings.APP_VERSION or '').strip()))

samples = {
    'Aura, recherche-moi 5 destinations autour de Nice': '5 destinations autour de Nice',
    'fais des recherches sur les nouveautés IA': 'les nouveautés IA',
    'peux-tu faire une recherche sur Python 3': 'Python 3',
    'tu peux rechercher les sorties Deftones récentes ?': 'les sorties Deftones récentes',
    'va chercher les dernières actualités IA': 'les dernières actualités IA',
    'je veux que tu recherches les meilleurs restaurants à Toulon': 'les meilleurs restaurants à Toulon',
}
for text, expected in samples.items():
    check('parser_' + str(len(checks)), extract_explicit_search_query(text) == expected)

check('normal_question_not_forced', not is_explicit_search_request('Qui est Victor Hugo ?'))

manager = InternetToolManager()
plan = manager.plan('fais des recherches sur les nouveautés IA')
check('explicit_plan_web_search', plan is not None and plan.name == 'web_search' and plan.action == 'WEB_SEARCH')
check('explicit_plan_flag', bool(plan and plan.args.get('explicit_research')))
check('explicit_plan_engine', bool(plan and plan.args.get('engine') == 'brave-search'))

# The plan must still exist when Internet/search are disabled, so execution can
# produce an explicit fail-closed diagnostic instead of falling through to LLM.
old_internet = settings.INTERNET_TOOLS_ENABLED
old_search = settings.WEB_SEARCH_ENABLED
try:
    settings.INTERNET_TOOLS_ENABLED = False
    disabled_plan = manager.plan('peux-tu faire une recherche sur Python 3')
    check('plan_survives_internet_disabled', disabled_plan is not None and disabled_plan.name == 'web_search')
    disabled_result = manager.execute(disabled_plan)
    check('disabled_fails_closed', (not disabled_result.ok) and disabled_result.source == 'research_engine_disabled')
finally:
    settings.INTERNET_TOOLS_ENABLED = old_internet
    settings.WEB_SEARCH_ENABLED = old_search

main = (ROOT / 'ui/main_window.py').read_text(encoding='utf-8')
research_idx = main.find('if is_explicit_search_request(text):')
agent_idx = main.find('agent_plan = self.aura_core.plan_agent_task(text)', max(0, research_idx))
check('ui_research_before_agent', research_idx >= 0 and agent_idx > research_idx)
check('ui_route_log_marker', 'Explicit research route=ai-search-engine' in main)

manager_src = (ROOT / 'tools/internet_manager.py').read_text(encoding='utf-8')
check('no_explicit_wikipedia_fallback', 'normalized_query.startswith(reference_prefix)' not in manager_src)
check('fail_closed_source_marker', 'research_engine_disabled' in manager_src)

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
print(f"\nPatch 26.6 diagnostics: {len(checks) - len(failed)}/{len(checks)} PASS")
if failed:
    raise SystemExit('FAILED: ' + ', '.join(failed))
