"""Read-only simulation of AURA v0.7.0.7 voice residency arbitration."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from config.settings import settings  # noqa: E402
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot  # noqa: E402


class _Voice:
    def __init__(self):
        self.loaded = True
        self.releases = 0

    def xtts_model_loaded(self):
        return self.loaded

    def release_xtts_model(self):
        self.releases += 1
        self.loaded = False
        return True

    def release_stt_model(self):
        return True


class _LLM:
    def __init__(self):
        self.resident = True
        self.unloaded = []

    def running_model_info(self, model=None):
        if self.resident and str(model or settings.LLM_VOICE_MODEL).casefold() == settings.LLM_VOICE_MODEL.casefold():
            return {"name": settings.LLM_VOICE_MODEL, "size": 2_000_000_000, "size_vram": 2_000_000_000}
        return None

    def running_model_query_ok(self):
        return True

    def unload(self, model=None):
        self.unloaded.append(model)
        self.resident = False
        return True


def _snap(ram):
    return ResourceSnapshot(
        ram_used_pct=ram,
        ram_total_gb=15.6,
        ram_available_gb=15.6 * (100.0 - ram) / 100.0,
        vram_used_mb=2375,
        vram_total_mb=6141,
        vram_used_pct=38.7,
        gpu_name="simulation",
    )


def main() -> int:
    print(f"=== AURA v{settings.APP_VERSION} - VOICE RESIDENCY DIAGNOSTICS ===")
    print("Simulation uniquement : aucun modèle n'est chargé ni déchargé sur le PC.")
    print()
    print(f"Priorité voix chaude : {settings.VOICE_RESIDENCY_PRIORITY}")
    print(f"Seuil éviction LLM   : {settings.VOICE_RESIDENCY_RELEASE_LLM_RAM_PCT:.0f}% RAM")
    print()

    voice = _Voice()
    llm = _LLM()
    guardian = ResourceGuardian(llm, voice, clock=lambda: 100.0)
    guardian._last_tts_use = 100.0
    guardian._last_llm_profile = {
        "name": "voice-fast",
        "model": settings.LLM_VOICE_MODEL,
        "co_resident": True,
        "keep_alive": settings.DUAL_BRAIN_VOICE_KEEP_ALIVE,
    }

    with patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), patch.object(
        guardian, "sample", side_effect=[_snap(88.1), _snap(61.8)]
    ):
        acted = guardian.idle_maintenance()

    print("Cas simulé : RAM 88.1%, XTTS chaud + cerveau vocal résident")
    print(f"Action effectuée      : {acted}")
    print(f"LLM vocal déchargé    : {settings.LLM_VOICE_MODEL in llm.unloaded}")
    print(f"XTTS encore chaud     : {voice.loaded}")
    print(f"Décision              : {guardian.last_decision}")
    print()
    ok = acted and (settings.LLM_VOICE_MODEL in llm.unloaded) and voice.loaded and voice.releases == 0
    if ok:
        print("[PASS] Sous pression RAM, AURA sacrifie le cerveau vocal avant XTTS.")
        return 0
    print("[FAIL] La priorité de résidence vocale n'est pas appliquée.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
