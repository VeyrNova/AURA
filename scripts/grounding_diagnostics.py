"""Read-only Grounded Intelligence diagnostic. No LLM or voice model is loaded."""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from consciousness.self_model import CapabilityState, SelfModel  # noqa: E402
from config.settings import settings  # noqa: E402
from grounding.manager import GroundedIntelligence  # noqa: E402


def main() -> int:
    guard = GroundedIntelligence()
    model = SelfModel(CapabilityState(internet=False))
    print(f"=== AURA v{settings.APP_VERSION} - GROUNDING DIAGNOSTICS ===")
    print("Lecture seule : aucun LLM, XTTS ou modele lourd n'est charge.\n")
    samples = [
        "Quelle heure est-il ?",
        "Quelle météo fait-il aujourd'hui ?",
        "Quelles sont les actualités du jour ?",
        "Quel est le prix actuel du bitcoin ?",
        "Quel est le score du match ce soir ?",
        "Y a-t-il des bouchons maintenant ?",
        "Pourquoi le ciel est-il bleu ?",
    ]
    expected_handled = [True, True, True, True, True, True, False]
    ok = True
    for text, expected in zip(samples, expected_handled):
        result = guard.evaluate(text, model)
        state = "INTERCEPT" if result.handled else "LLM-OK"
        print(f"[{state:9}] {text}")
        if result.handled:
            print(f"           category={result.category} source={result.source}")
        if result.handled != expected:
            ok = False
    print()
    if ok:
        print("[PASS] Grounded Intelligence bloque les faits temps reel non sources sans surbloquer les questions stables.")
        return 0
    print("[FAIL] Une classification de grounding est incoherente.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
