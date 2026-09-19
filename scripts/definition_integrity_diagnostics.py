"""Read-only diagnostics for AURA v0.7.0.9 definition integrity."""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from ai.knowledge_quality import deterministic_knowledge_fallback, find_knowledge_risks  # noqa: E402
from ai.speech_quality import deterministic_french_fallback, find_voice_quality_issues  # noqa: E402
from config.settings import settings  # noqa: E402
from tools.internet_manager import InternetToolManager  # noqa: E402


def main() -> int:
    print(f"=== AURA v{settings.APP_VERSION} - DEFINITION INTEGRITY ===")
    print("Diagnostic local uniquement : aucun LLM ni accès Internet n'est utilisé.")
    print()

    question = "Explique-moi simplement ce qu'est un neutron"
    manager = InternetToolManager()
    plan = manager.plan(question)
    result = manager.execute(plan) if plan is not None else None

    print("Definition routing")
    print(f"  Question            : {question}")
    print(f"  Tool                : {getattr(plan, 'name', None)}")
    print(f"  Security action     : {getattr(plan, 'action', None)}")
    print(f"  Web allowed         : {getattr(plan, 'args', {}).get('allow_web') if plan else None}")
    print(f"  Source              : {getattr(result, 'source', None)}")
    print(f"  Answer              : {getattr(result, 'response', None)}")
    print()

    observed_bad = (
        "Le neutron est une particule subatomique qui constitue le noyau d'une atomique "
        "avec un nombre neutre, 0 ou un nombre entier positif, et est souvent associé à l'hydrogène."
    )
    language_issues = find_voice_quality_issues(observed_bad)
    knowledge_risks = find_knowledge_risks(question, observed_bad)
    french_fallback = deterministic_french_fallback(observed_bad)
    knowledge_fallback = deterministic_knowledge_fallback(observed_bad, question)

    print("Observed failure regression")
    print(f"  French issues       : {[issue.code for issue in language_issues]}")
    print(f"  Knowledge risks     : {[risk.code for risk in knowledge_risks]}")
    print(f"  French fallback     : {french_fallback}")
    print(f"  Knowledge fallback  : {knowledge_fallback}")
    print(f"  Self-verify enabled : {settings.LLM_VOICE_KNOWLEDGE_SELF_VERIFY}")
    print()

    answer = getattr(result, "response", "") if result else ""
    ok = (
        settings.APP_VERSION == "0.7.0.9"
        and plan is not None
        and plan.name == "knowledge_reference"
        and plan.action == "KNOWLEDGE_REFERENCE_LOCAL"
        and result is not None
        and result.ok
        and result.source == "aura-local-reference"
        and "sans charge électrique" in answer
        and "noyau" in answer
        and "d'une atomique" not in answer
        and "nombre neutre" not in answer
        and not settings.LLM_VOICE_KNOWLEDGE_SELF_VERIFY
        and any(issue.code == "dangling_science_adjective" for issue in language_issues)
        and any(risk.code == "neutron_malformed_definition" for risk in knowledge_risks)
    )
    if ok:
        print("[PASS] Les définitions directes sont grounded et le cas erroné du log est bloqué.")
        return 0
    print("[FAIL] Une protection de définition v0.7.0.9 n'est pas active.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
