"""Read-only v0.7.0.5 fast-prosody diagnostics."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from config.settings import settings
from voice.text_to_speech import sanitize_for_speech
from voice.xtts_tts import XTTSTTS


def main():
    sample = (
        "À Vidauban, il fait actuellement 36.1 °C. Conditions actuelles : ciel dégagé. "
        "Le ressenti est de 35.5 °C. L'humidité est de 29%, et le vent souffle à 12 km/h. "
        "Les précipitations actuelles sont de 0.0 mm. Source : Open-Meteo, vérifiée à 13:15."
    )
    spoken = sanitize_for_speech(sample)
    plan = XTTSTTS._natural_chunk_plan(
        spoken,
        first_limit=settings.FAST_SPEECH_FIRST_CHUNK_CHARS,
        next_limit=settings.FAST_SPEECH_NEXT_CHUNK_CHARS,
        min_chars=settings.FAST_SPEECH_MIN_CHUNK_CHARS,
        max_chunks=settings.FAST_SPEECH_MAX_CHUNKS,
    )
    chunks = tuple(item.text for item in plan)
    print(f"=== AURA v{settings.APP_VERSION} - VOICE POLISH DIAGNOSTICS ===")
    print(f"Continuous playback : {settings.FAST_SPEECH_CONTINUOUS_PLAYBACK}")
    print(f"First chunk target   : {settings.FAST_SPEECH_FIRST_CHUNK_CHARS} (premiere phrase complete prioritaire)")
    print(f"Next chunk target    : {settings.FAST_SPEECH_NEXT_CHUNK_CHARS}")
    print(f"Tail fade            : {settings.TTS_TAIL_FADE_MS:.0f} ms")
    print(f"Tail safety silence  : {settings.TTS_TAIL_SILENCE_MS:.0f} ms")
    print()
    print("Texte TTS normalise :")
    print(spoken)
    print()
    print("Chunks :")
    for idx, item in enumerate(plan, 1):
        print(f"  {idx}: {len(item.text):3d} chars | boundary={item.boundary:11s} | {item.text}")
    required = (
        "36 virgule 1 degrés Celsius",
        "29 pour cent",
        "12 kilomètres par heure",
        "0 virgule 0 millimètres",
        "13 heures 15",
    )
    ok = all(token in spoken for token in required) and bool(chunks)
    print()
    print("[PASS] Normalisation et chunking vocal prêts." if ok else "[FAIL] Vérifie la normalisation vocale.")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
