"""Read-only v0.7.0.5 sentence-completion and fast-prosody diagnostics."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.response_guard import finalize_voice_reply, needs_voice_completion  # noqa: E402
from config.settings import settings  # noqa: E402
from voice.xtts_tts import XTTSTTS  # noqa: E402


def main() -> int:
    print(f"=== AURA v{settings.APP_VERSION} - VOICE COMPLETION DIAGNOSTICS ===")
    print(f"Voice num_predict      : {settings.LLM_VOICE_NUM_PREDICT}")
    print(f"Completion guard       : {settings.LLM_VOICE_COMPLETION_GUARD}")
    print(f"Completion budget      : {settings.LLM_VOICE_COMPLETION_NUM_PREDICT}")
    print(f"Trigger margin         : {settings.LLM_VOICE_COMPLETION_TRIGGER_MARGIN}")
    print()

    cut = "Les neutrons sont dans le noyau. Leur masse est proche de celle des protons ("
    continuation = "environ une unité de masse atomique)."
    triggered = needs_voice_completion(
        cut,
        output_tokens=settings.LLM_VOICE_NUM_PREDICT,
        num_predict=settings.LLM_VOICE_NUM_PREDICT,
        margin=settings.LLM_VOICE_COMPLETION_TRIGGER_MARGIN,
        done_reason="length",
    )
    final, _ = finalize_voice_reply(
        cut,
        output_tokens=settings.LLM_VOICE_NUM_PREDICT,
        num_predict=settings.LLM_VOICE_NUM_PREDICT,
        margin=settings.LLM_VOICE_COMPLETION_TRIGGER_MARGIN,
        done_reason="length",
        continuation=continuation,
    )
    print("Simulation troncature :")
    print(f"  Initial      : {cut}")
    print(f"  Guard        : {triggered}")
    print(f"  Continuation : {continuation}")
    print(f"  Final TTS    : {final}")
    print()

    speech = (
        "À Vidauban, Région PACA, France, il fait actuellement 36 virgule 2 degrés Celsius. "
        "Conditions actuelles : ciel dégagé. "
        "Le ressenti est de 35 virgule 2 degrés Celsius. "
        "L'humidité est de 30 pour cent, et le vent souffle à 16 kilomètres par heure."
    )
    plan = XTTSTTS._natural_chunk_plan(
        speech,
        first_limit=settings.FAST_SPEECH_FIRST_CHUNK_CHARS,
        next_limit=settings.FAST_SPEECH_NEXT_CHUNK_CHARS,
        min_chars=settings.FAST_SPEECH_MIN_CHUNK_CHARS,
        max_chunks=settings.FAST_SPEECH_MAX_CHUNKS,
    )
    print("Fast prosody :")
    for idx, chunk in enumerate(plan, 1):
        print(f"  {idx}: {len(chunk.text):3d} chars | {chunk.boundary:11s} | {chunk.text}")
    print()

    ok = (
        triggered
        and final.endswith("atomique).")
        and bool(plan)
        and plan[0].text.endswith("Celsius.")
        and "Conditions actuelles" not in plan[0].text
    )
    print("[PASS] Sentence Completion + Fast Prosody prêts." if ok else "[FAIL] Vérifie le garde-fou vocal.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
