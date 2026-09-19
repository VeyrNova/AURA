"""Read-only latency diagnostics for AURA v0.6.5."""
from __future__ import annotations
import os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
from config.settings import settings  # noqa: E402


def recent(path: Path, markers: tuple[str, ...], limit=18):
    if not path.is_file(): return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [l for l in lines if any(m in l for m in markers)][-limit:]


def main():
    print("=== AURA v0.6.5 — LATENCY DIAGNOSTICS ===")
    print("Lecture seule : aucun modèle lourd n'est chargé.")
    print()
    print("Dual Brain :")
    print(f"  Texte              : {settings.LLM_TEXT_MODEL}")
    print(f"  Voix               : {settings.LLM_VOICE_MODEL}")
    print(f"  Activé              : {settings.DUAL_BRAIN_ENABLED}")
    print(f"  Probe co-résidence  : {'PASS' if settings.DUAL_BRAIN_MARKER.is_file() else 'non validé'}")
    print(f"  Keep-alive voix co. : {settings.DUAL_BRAIN_VOICE_KEEP_ALIVE}")
    print()
    print("Profils :")
    print(f"  Texte ctx/predict   : {settings.LLM_NUM_CTX}/{settings.LLM_NUM_PREDICT}")
    print(f"  Voix ctx/predict    : {settings.LLM_VOICE_NUM_CTX}/{settings.LLM_VOICE_NUM_PREDICT}")
    print(f"  Historique voix     : {settings.LLM_VOICE_MAX_HISTORY_MESSAGES} messages")
    print(f"  Souvenirs voix      : {settings.LLM_VOICE_MEMORY_LIMIT}")
    print(f"  XTTS idle dual      : {settings.DUAL_BRAIN_XTTS_IDLE_SECONDS:.0f}s")
    print()
    print("Fast Speech :")
    print(f"  Progressif          : {settings.FAST_SPEECH_ENABLED}")
    print(f"  Premier chunk       : {settings.FAST_SPEECH_FIRST_CHUNK_CHARS} caractères max")
    print(f"  Chunks suivants     : {settings.FAST_SPEECH_NEXT_CHUNK_CHARS} caractères max")
    print(f"  Nombre max chunks   : {settings.FAST_SPEECH_MAX_CHUNKS}")
    print(f"  Streaming natif     : {settings.FAST_SPEECH_NATIVE_STREAMING} (expérimental)")
    log = settings.LOG_DIR / "aura.log"
    markers = (
        "LLM profile=", "LLM first-token latency:", "LLM total latency:", "LLM metrics profile=",
        "TTS first-audio true:", "TTS synthesis+playback:", "XTTS timing", "XTTS fast-speech", "Guardian before LLM", "Guardian before TTS",
    )
    print(f"\nJournal analysé       : {log}")
    lines = recent(log, markers)
    if not lines:
        print("Aucune métrique récente.")
        return 0
    print("\nDernières métriques :")
    for line in lines: print(line)
    print("\nRepères :")
    print("  load       = chargement Ollama")
    print("  prompt     = évaluation du contexte")
    print("  generation = génération des tokens")
    print("  model_load = chargement XTTS")
    print("  first-audio true = chargement XTTS + synthèse du premier chunk avant lecture")
    print("  first_chunk = temps de synthèse du premier morceau Fast Speech")
    print("  synth       = somme des synthèses de chunks; certaines s'exécutent pendant la lecture")
    return 0
if __name__ == '__main__': raise SystemExit(main())
