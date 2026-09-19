"""Read-only Dual Brain status for AURA v0.6.4."""
from __future__ import annotations
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from ai.llm_manager import LLMManager  # noqa: E402
from config.settings import settings  # noqa: E402
from runtime.resource_guardian import ResourceGuardian  # noqa: E402
from voice.voice_engine import VoiceEngine  # noqa: E402


def main() -> int:
    print("=== AURA v0.6.4 — DUAL BRAIN STATUS ===")
    print("Lecture seule : aucun modèle lourd n'est chargé.")
    llm = LLMManager()
    voice = VoiceEngine()
    guardian = ResourceGuardian(llm, voice)
    local = llm.local_models(force=True)
    print(f"Cerveau texte       : {settings.LLM_TEXT_MODEL} | installé={llm.model_available(settings.LLM_TEXT_MODEL)}")
    print(f"Cerveau vocal       : {settings.LLM_VOICE_MODEL} | installé={llm.model_available(settings.LLM_VOICE_MODEL)}")
    print(f"Dual Brain activé   : {settings.DUAL_BRAIN_ENABLED}")
    marker = guardian.dual_brain_marker()
    print(f"Probe co-résidence  : {'PASS' if marker.get('passed') else 'NON VALIDÉ'}")
    if marker:
        print(f"GPU validé          : {marker.get('gpu_name','?')}")
        print(f"VRAM validée        : {float(marker.get('vram_total_mb') or 0):.0f} MiB")
        print(f"Pic combiné         : {float(marker.get('peak_vram_used_mb') or 0):.0f} MiB")
        print(f"XTTS estimé         : {float(marker.get('xtts_vram_mb') or 0):.0f} MiB")
    snap = guardian.sample(force_gpu=True)
    if snap.vram_total_mb:
        print(f"GPU actuel          : {snap.gpu_name}")
        print(f"VRAM actuelle       : {snap.vram_used_mb:.0f}/{snap.vram_total_mb:.0f} MiB")
    print(f"Co-résidence prête  : {guardian.dual_brain_co_resident_ready(snapshot=snap)}")
    print(f"Marqueur             : {settings.DUAL_BRAIN_MARKER}")
    if not llm.model_available(settings.LLM_VOICE_MODEL):
        print("[ACTION] Lance INSTALL_DUAL_BRAIN.bat.")
    elif not marker.get("passed"):
        print("[ACTION] Lance DUAL_GPU_PROBE.bat avant la co-résidence GPU.")
    else:
        print("[PASS] Dual Brain prêt pour les conversations vocales rapides.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
