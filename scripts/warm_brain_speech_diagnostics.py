"""Read-only diagnostics for AURA v0.7.0.7 Warm Brain & Speech Quality Gate."""
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

from ai.speech_quality import deterministic_french_fallback, find_voice_quality_issues  # noqa: E402
from config.settings import settings  # noqa: E402
from runtime.resource_guardian import ResourceGuardian, ResourceSnapshot  # noqa: E402
from voice.xtts_tts import XTTSTTS  # noqa: E402


class _Voice:
    def __init__(self):
        self.loaded = True

    def xtts_model_loaded(self):
        return self.loaded

    def release_xtts_model(self):
        self.loaded = False
        return True

    def release_stt_model(self):
        return True


class _LLM:
    def __init__(self):
        self.resident = False
        self.warmups = 0

    def model_available(self, model):
        return str(model).casefold() == settings.LLM_VOICE_MODEL.casefold()

    def running_model_info(self, model=None):
        if self.resident and str(model or settings.LLM_VOICE_MODEL).casefold() == settings.LLM_VOICE_MODEL.casefold():
            return {"name": settings.LLM_VOICE_MODEL, "size": 2_000_000_000, "size_vram": 600_000_000}
        return None

    def warmup(self, **kwargs):
        self.warmups += 1
        self.resident = True

    def unload(self, model=None):
        self.resident = False
        return True

    def running_model_query_ok(self):
        return True


def _snap(ram: float, avail: float) -> ResourceSnapshot:
    return ResourceSnapshot(
        ram_used_pct=ram,
        ram_total_gb=15.6,
        ram_available_gb=avail,
        vram_used_mb=1911,
        vram_total_mb=6141,
        vram_used_pct=31.1,
        gpu_name="simulation",
    )


def main() -> int:
    print(f"=== AURA v{settings.APP_VERSION} - WARM BRAIN & SPEECH QUALITY ===")
    print("Simulation uniquement : aucun modèle réel n'est chargé.")
    print()

    voice = _Voice()
    llm = _LLM()
    guardian = ResourceGuardian(llm, voice, clock=lambda: 100.0)
    with patch.object(guardian, "dual_brain_co_resident_ready", return_value=True), patch.object(
        guardian, "sample", side_effect=[_snap(55.6, 6.95), _snap(81.9, 2.82)]
    ):
        warm_ok = guardian.conditional_voice_llm_prewarm()

    print("Warm Brain")
    print(f"  Activé              : {settings.VOICE_BRAIN_POST_START_PREWARM}")
    print(f"  Plafond RAM prédit  : {settings.VOICE_BRAIN_PREWARM_MAX_RAM_PCT:.0f}%")
    print(f"  Préwarm simulé      : {warm_ok}")
    print(f"  XTTS conservé       : {voice.loaded}")
    print(f"  Cerveau vocal chaud : {llm.resident}")
    print()

    bad = "Les neutrons jouent un rôle essentiel dans la structure stables des noyaux."
    issues = find_voice_quality_issues(bad)
    fallback = deterministic_french_fallback(bad)
    print("Speech Quality Gate")
    print(f"  Entrée               : {bad}")
    print(f"  Issues détectées     : {[issue.code for issue in issues]}")
    print(f"  Fallback déterministe: {fallback}")
    print()

    long_sentence = (
        "Les neutrons jouent un rôle essentiel dans la structure stable des noyaux, "
        "car ils maintiennent l'équilibre entre les charges positives des protons "
        "et les forces électromagnétiques entre les protons eux-mêmes."
    )
    plan = XTTSTTS._natural_chunk_plan(
        long_sentence,
        first_limit=settings.FAST_SPEECH_FIRST_CHUNK_CHARS,
        next_limit=settings.FAST_SPEECH_NEXT_CHUNK_CHARS,
        min_chars=settings.FAST_SPEECH_MIN_CHUNK_CHARS,
        max_chunks=settings.FAST_SPEECH_MAX_CHUNKS,
    )
    print("Long Sentence Prosody")
    for index, chunk in enumerate(plan, 1):
        print(f"  chunk {index}: {len(chunk.text):3d} chars | {chunk.boundary} | {chunk.text}")
    print()

    max_len = max((len(chunk.text) for chunk in plan), default=0)
    ok = (
        settings.APP_VERSION in {"0.7.0.7", "0.7.0.8", "0.7.0.9"}
        and warm_ok
        and voice.loaded
        and llm.resident
        and bool(issues)
        and not find_voice_quality_issues(fallback)
        and len(plan) >= 2
        and max_len <= settings.FAST_SPEECH_MAX_SENTENCE_CHARS
    )
    if ok:
        print("[PASS] Warm Brain, qualité française et prosodie longue sont prêts.")
        return 0
    print("[FAIL] Une vérification v0.7.0.7 a échoué.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
