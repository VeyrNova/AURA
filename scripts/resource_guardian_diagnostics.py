"""Non-destructive Resource Guardian diagnostics for AURA v0.7.0.7."""
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

from ai.llm_manager import LLMManager  # noqa: E402
from config.settings import settings  # noqa: E402
from runtime.resource_guardian import ResourceGuardian  # noqa: E402
from voice.voice_engine import VoiceEngine  # noqa: E402


def main() -> int:
    print(f"=== AURA v{settings.APP_VERSION} — RESOURCE GUARDIAN DIAGNOSTICS ===")
    print("Ce diagnostic ne charge ni XTTS ni Whisper.")
    print()
    voice = VoiceEngine()
    llm = LLMManager()
    guardian = ResourceGuardian(llm, voice)
    data = guardian.diagnostics()

    print(f"Guardian actif       : {data['enabled']}")
    print(f"RAM utilisée         : {data['ram_used_pct']:.1f}%")
    print(f"RAM totale           : {data['ram_total_gb']:.1f} Go")
    print(f"RAM disponible       : {data['ram_available_gb']:.1f} Go")
    if data["vram_total_mb"] > 0:
        print(f"GPU NVIDIA            : {data['gpu_name'] or 'détecté'}")
        print(f"VRAM                  : {data['vram_used_mb']:.0f} / {data['vram_total_mb']:.0f} MiB")
        print(f"Source VRAM           : {data.get('gpu_probe_source') or 'inconnue'}")
        if data.get("gpu_probe_executable"):
            print(f"Outil VRAM            : {data['gpu_probe_executable']}")
    else:
        print("VRAM                  : mesure NVIDIA indisponible")
        print(f"Source VRAM           : {data.get('gpu_probe_source') or 'unavailable'}")
        if data.get("gpu_probe_detail"):
            print(f"Détail VRAM           : {data['gpu_probe_detail']}")
    if data["ollama_model"]:
        print(f"Ollama chargé         : {data['ollama_model']}")
        print(f"VRAM Ollama /api/ps   : {data['ollama_vram_mb']:.0f} MiB")
    else:
        print("Ollama chargé         : aucun modèle correspondant")
    print(f"XTTS chargé par AURA  : {data['xtts_loaded']}")
    print(f"Dual Brain activé     : {data['dual_brain_enabled']}")
    print(f"Cerveau vocal         : {data['dual_brain_voice_model']}")
    print(f"Co-résidence validée  : {data['dual_brain_co_resident_ready']}")
    print(f"XTTS prewarm actif    : {data.get('xtts_prewarm_active', False)}")
    print(f"XTTS prewarm résultat : {data.get('xtts_prewarm_last_result', 'not-run')}")
    print()
    print("Seuils :")
    print(f"  RAM avertissement   : {settings.RESOURCE_RAM_WARN_PCT:.0f}%")
    print(f"  RAM critique        : {settings.RESOURCE_RAM_CRITICAL_PCT:.0f}%")
    print(f"  RAM urgence         : {settings.RESOURCE_RAM_EMERGENCY_PCT:.0f}%")
    print(f"  VRAM critique       : {settings.RESOURCE_VRAM_CRITICAL_PCT:.0f}%")
    print(f"  Keep-alive texte    : {settings.RESOURCE_LLM_KEEP_ALIVE_TEXT}")
    print(f"  Keep-alive voix sûr : {settings.RESOURCE_LLM_KEEP_ALIVE_VOICE}")
    print(f"  Keep-alive voix dual: {settings.DUAL_BRAIN_VOICE_KEEP_ALIVE}")
    print(f"  XTTS idle standard  : {settings.RESOURCE_XTTS_IDLE_SECONDS:.0f}s")
    print(f"  XTTS idle dual      : {settings.DUAL_BRAIN_XTTS_IDLE_SECONDS:.0f}s")
    print(f"  Prewarm RAM max     : {settings.XTTS_PREWARM_MAX_RAM_PCT:.0f}%")
    print(f"  Prewarm RAM libre   : {settings.XTTS_PREWARM_MIN_AVAILABLE_RAM_GB:.1f} Go min")
    print(f"  Prewarm VRAM préd.  : {settings.XTTS_PREWARM_MAX_PREDICTED_VRAM_PCT:.0f}% max")
    print(f"  Voice LLM RAM estim.: {settings.DUAL_BRAIN_VOICE_RAM_ESTIMATE_GB:.1f} Go")
    print(f"  Voice LLM RAM max   : {settings.DUAL_BRAIN_LLM_PRELOAD_MAX_RAM_PCT:.0f}% prédit")
    print(f"  Voice LLM RAM libre : {settings.DUAL_BRAIN_LLM_PRELOAD_MIN_AVAILABLE_RAM_GB:.1f} Go min après chargement")
    print(f"  Priorité voix chaude: {settings.VOICE_RESIDENCY_PRIORITY}")
    print(f"  Eviction LLM voix   : dès {settings.VOICE_RESIDENCY_RELEASE_LLM_RAM_PCT:.0f}% RAM")
    print()

    ram = float(data["ram_used_pct"])
    if ram >= settings.RESOURCE_RAM_EMERGENCY_PCT:
        print("[DANGER] RAM en zone d'urgence. Ferme des applications avant de relancer des modèles lourds.")
        return 3
    if ram >= settings.RESOURCE_RAM_CRITICAL_PCT:
        print("[WARN] RAM en zone critique. Resource Guardian utilisera des fallbacks légers.")
        return 2
    if ram >= settings.RESOURCE_RAM_WARN_PCT:
        print("[WARN] RAM déjà élevée, mais la protection peut continuer à orchestrer les modèles.")
        return 0
    print("[PASS] Niveau mémoire compatible avec le mode protégé.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
