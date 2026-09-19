"""AURA v0.6.6.1 NVIDIA VRAM detection diagnostics (read-only)."""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from ai.llm_manager import LLMManager  # noqa: E402
from runtime.resource_guardian import ResourceGuardian  # noqa: E402
from voice.voice_engine import VoiceEngine  # noqa: E402


def main() -> int:
    print("=== AURA v0.6.6.1 - NVIDIA VRAM DIAGNOSTICS ===")
    print("Lecture seule : aucun modèle lourd n'est chargé.")
    print()
    guardian = ResourceGuardian(LLMManager(), VoiceEngine())
    found = guardian._find_nvidia_smi()
    print(f"nvidia-smi trouvé     : {found or 'non'}")
    used, total, name, path, detail = guardian._run_nvidia_smi_detailed()
    print(f"nvidia-smi direct     : {'PASS' if total > 0 else 'FAIL'}")
    if path:
        print(f"  chemin              : {path}")
    if detail:
        print(f"  détail              : {detail}")
    if total > 0:
        print(f"  GPU                 : {name}")
        print(f"  VRAM                : {used:.0f} / {total:.0f} MiB")
    else:
        nused, ntotal, nname, ndetail = guardian._run_nvml_ctypes()
        print(f"NVML direct           : {'PASS' if ntotal > 0 else 'FAIL'}")
        print(f"  détail              : {ndetail}")
        if ntotal > 0:
            print(f"  GPU                 : {nname}")
            print(f"  VRAM                : {nused:.0f} / {ntotal:.0f} MiB")

    snap = guardian.sample(force_gpu=True)
    print()
    print("Méthode retenue :")
    print(f"  source              : {guardian._gpu_probe_source}")
    print(f"  outil               : {guardian._gpu_probe_executable or '-'}")
    print(f"  GPU                 : {snap.gpu_name or '-'}")
    print(f"  VRAM                : {snap.vram_used_mb:.0f} / {snap.vram_total_mb:.0f} MiB")
    if guardian._gpu_probe_detail:
        print(f"  détail              : {guardian._gpu_probe_detail}")
    print()
    if snap.vram_total_mb > 0:
        print("[PASS] Mesure VRAM exploitable par Resource Guardian.")
        return 0
    print("[FAIL] Aucune méthode fiable n'a pu mesurer la VRAM.")
    print("Le Guardian restera en mode fail-safe et n'effectuera pas le prewarm XTTS.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
