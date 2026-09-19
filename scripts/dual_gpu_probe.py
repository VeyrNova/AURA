"""Explicit co-residency probe: Ollama voice model + XTTS CUDA."""
from __future__ import annotations
import json, os, sys, time, traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from ai.llm_manager import LLMManager  # noqa: E402
from config.settings import settings  # noqa: E402
from runtime.resource_guardian import ResourceGuardian  # noqa: E402
from voice.voice_engine import VoiceEngine  # noqa: E402


def out(msg=""):
    print(str(msg), flush=True)


def main() -> int:
    marker = settings.DUAL_BRAIN_MARKER
    marker.unlink(missing_ok=True)
    llm = LLMManager()
    voice = VoiceEngine()
    guardian = ResourceGuardian(llm, voice)
    try:
        out(f"[1/8] Cerveau vocal: {settings.LLM_VOICE_MODEL}")
        if not llm.model_available(settings.LLM_VOICE_MODEL):
            raise RuntimeError("Le modèle vocal n'est pas installé. Lance INSTALL_DUAL_BRAIN.bat.")
        if settings.XTTS_DEVICE.strip().lower() != "cuda" or not settings.XTTS_ALLOW_CUDA:
            raise RuntimeError("XTTS CUDA n'est pas activé. Lance ENABLE_XTTS_GPU.bat après un XTTS_GPU_PROBE PASS.")

        out("[2/8] Nettoyage des modèles résidents...")
        for model in {settings.LLM_TEXT_MODEL, settings.LLM_VOICE_MODEL}:
            llm.unload(model=model)
        voice.release_xtts_model()
        time.sleep(0.5)
        baseline = guardian.sample(force_gpu=True)
        out(f"      baseline VRAM={baseline.vram_used_mb:.0f}/{baseline.vram_total_mb:.0f} MiB RAM={baseline.ram_used_pct:.1f}%")

        out("[3/8] Chargement XTTS CUDA...")
        xtts_start = time.perf_counter()
        xtts = voice.xtts_runtime_info()
        xtts_load = time.perf_counter() - xtts_start
        after_xtts = guardian.sample(force_gpu=True)
        xtts_delta = max(0.0, after_xtts.vram_used_mb - baseline.vram_used_mb)
        xtts_est = max(xtts_delta, float(xtts.reserved_mb or 0))
        out(f"      XTTS chargé en {xtts_load:.1f}s | reserved={xtts.reserved_mb:.0f} MiB | delta GPU={xtts_delta:.0f} MiB")

        out("[4/8] Chargement du cerveau vocal Ollama à côté de XTTS...")
        llm.warmup(model=settings.LLM_VOICE_MODEL, keep_alive=settings.DUAL_BRAIN_VOICE_KEEP_ALIVE,
                   num_ctx=settings.LLM_VOICE_NUM_CTX, force=True)
        time.sleep(0.4)
        info = llm.running_model_info(model=settings.LLM_VOICE_MODEL)
        if not info:
            raise RuntimeError("Ollama n'a pas confirmé le chargement du cerveau vocal.")
        model_vram = float(info.get("size_vram", 0) or 0) / (1024 * 1024)
        combined = guardian.sample(force_gpu=True)
        out(f"      Ollama VRAM={model_vram:.0f} MiB | combiné={combined.vram_used_mb:.0f}/{combined.vram_total_mb:.0f} MiB")

        out("[5/8] Test d'inférence Llama 3.2 avec XTTS résident...")
        reply = llm.generate(
            [{"role": "system", "content": "Réponds uniquement par OK."}, {"role": "user", "content": "Test"}],
            model=settings.LLM_VOICE_MODEL,
            keep_alive=settings.DUAL_BRAIN_VOICE_KEEP_ALIVE,
            num_ctx=1024,
            num_predict=8,
        )
        out(f"      réponse={reply[:40]!r}")

        out("[6/8] Test de synthèse XTTS courte avec Ollama encore résident...")
        speaker = voice.profile.xtts_preset or settings.XTTS_PRESET_SPEAKER
        metrics = voice.preview_xtts_speaker(speaker, "Test AURA.", fast=True)
        after_synth = guardian.sample(force_gpu=True)
        peak = max(combined.vram_used_mb, after_synth.vram_used_mb)
        total = max(combined.vram_total_mb, after_synth.vram_total_mb, float(xtts.total_mb or 0))
        pct = 100.0 * peak / total if total else 0.0
        out(f"      first-audio={getattr(metrics,'time_to_audio_seconds',metrics.synthesis_seconds):.2f}s | pic VRAM={peak:.0f}/{total:.0f} MiB ({pct:.1f}%)")

        out("[7/8] Validation des marges...")
        ram = guardian.sample(force_gpu=True).ram_used_pct
        if total <= 0:
            raise RuntimeError("Impossible de mesurer la VRAM totale; le probe ne peut pas valider la co-résidence.")
        if pct > settings.DUAL_BRAIN_PROBE_MAX_VRAM_PCT:
            raise RuntimeError(f"Pic VRAM {pct:.1f}% > seuil {settings.DUAL_BRAIN_PROBE_MAX_VRAM_PCT:.1f}%.")
        if ram >= settings.RESOURCE_RAM_CRITICAL_PCT:
            raise RuntimeError(f"RAM trop élevée pendant le probe: {ram:.1f}%.")
        free = total - peak
        if free < settings.DUAL_BRAIN_MIN_FREE_VRAM_MB:
            raise RuntimeError(f"Marge VRAM insuffisante: {free:.0f} MiB.")

        data = {
            "passed": True,
            "app_version": settings.APP_VERSION,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "voice_model": settings.LLM_VOICE_MODEL,
            "gpu_name": after_synth.gpu_name or xtts.gpu_name,
            "vram_total_mb": total,
            "peak_vram_used_mb": peak,
            "voice_model_vram_mb": model_vram,
            "xtts_vram_mb": xtts_est,
            "ram_used_pct": ram,
            "speaker": speaker,
        }
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        out("[8/8] Marqueur de sécurité créé.")
        out(f"[PASS] Dual Brain co-résident validé. Marge VRAM: {free:.0f} MiB.")
        return 0
    except Exception as exc:
        marker.unlink(missing_ok=True)
        out(f"[FAIL] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        out("AURA restera automatiquement en mode séquentiel v0.6.3.")
        return 1
    finally:
        try: voice.release_xtts_model()
        except Exception: pass
        try: llm.unload(model=settings.LLM_VOICE_MODEL)
        except Exception: pass

if __name__ == "__main__":
    raise SystemExit(main())
