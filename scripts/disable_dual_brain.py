from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
from ai.llm_manager import LLMManager  # noqa: E402
from config.settings import settings  # noqa: E402

def main():
    try:
        settings.DUAL_BRAIN_MARKER.unlink(missing_ok=True)
    except Exception as exc:
        print(f"[FAIL] Impossible de supprimer le marqueur: {exc}")
        return 1
    try:
        LLMManager().unload(model=settings.LLM_VOICE_MODEL)
    except Exception:
        pass
    print("[PASS] Co-résidence Dual Brain désactivée. AURA reste en mode séquentiel sûr.")
    return 0
if __name__ == '__main__': raise SystemExit(main())
