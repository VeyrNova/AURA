"""Read-only diagnostics for AURA v0.7.0.9 Voice Brevity & Knowledge Quality."""
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
from ai.voice_brevity import trim_spoken_reply, voice_brevity_policy, voice_output_contract  # noqa: E402
from config.settings import settings  # noqa: E402


def main() -> int:
    print(f"=== AURA v{settings.APP_VERSION} - VOICE BREVITY & KNOWLEDGE QUALITY ===")
    print("Diagnostic local uniquement : aucun modèle n'est chargé.")
    print()

    question = "Explique-moi simplement ce qu'est un neutron"
    policy = voice_brevity_policy(
        question,
        max_sentences=settings.LLM_VOICE_MAX_SENTENCES,
        max_chars=settings.LLM_VOICE_MAX_CHARS,
        detail_max_sentences=settings.LLM_VOICE_DETAIL_MAX_SENTENCES,
        detail_max_chars=settings.LLM_VOICE_DETAIL_MAX_CHARS,
        first_sentence_target=settings.LLM_VOICE_FIRST_SENTENCE_TARGET,
    )
    print("Voice Brevity")
    print(f"  Factual explanation : {policy.factual_explanation}")
    print(f"  Max sentences       : {policy.max_sentences}")
    print(f"  Max chars           : {policy.max_chars}")
    print(f"  First target        : {policy.first_sentence_target}")
    print(f"  Voice temperature   : {settings.LLM_VOICE_TEMPERATURE:.2f}")
    print(f"  Voice top_p         : {settings.LLM_VOICE_TOP_P:.2f}")
    print(f"  Voice num_predict   : {settings.LLM_VOICE_NUM_PREDICT}")
    print()

    verbose = (
        "Un neutron est une particule sans charge électrique présente dans le noyau atomique. "
        "Sa masse est proche de celle d'un proton. "
        "Avec les protons, il contribue à la stabilité du noyau. "
        "Cette quatrième phrase est volontairement superflue pour le test vocal."
    )
    trimmed, changed = trim_spoken_reply(verbose, policy)
    print("Brevity trim")
    print(f"  Trim applied        : {changed}")
    print(f"  Result               : {trimmed}")
    print()

    bad = "Il possède une masse similaire à celle des protons et des électrons."
    risks = find_knowledge_risks(question, bad)
    fixed = deterministic_knowledge_fallback(bad, question)
    fixed_risks = find_knowledge_risks(question, fixed)
    print("Knowledge Quality")
    print(f"  Risky sentence      : {bad}")
    print(f"  Risks               : {[risk.code for risk in risks]}")
    print(f"  Deterministic fix   : {fixed}")
    print(f"  Risks after fix     : {[risk.code for risk in fixed_risks]}")
    print()

    contract = voice_output_contract(policy)
    ok = (
        settings.APP_VERSION == "0.7.0.9"
        and settings.LLM_VOICE_KNOWLEDGE_GATE
        and settings.LLM_VOICE_NUM_PREDICT < 128
        and settings.LLM_VOICE_TEMPERATURE < settings.LLM_TEMPERATURE
        and policy.factual_explanation
        and changed
        and len(risks) > 0
        and len(fixed_risks) == 0
        and "85 caractères" in contract
    )
    if ok:
        print("[PASS] Réponses vocales courtes, échantillonnage sobre et garde-fou factuel prêts.")
        return 0
    print("[FAIL] Une vérification v0.7.0.9 a échoué.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
