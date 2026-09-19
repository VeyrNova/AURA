"""Read-only Fast Speech diagnostics for AURA v0.6.5."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from config.settings import settings  # noqa: E402


def _recent(path: Path, limit: int = 30) -> list[str]:
    if not path.is_file():
        return []
    markers = ("XTTS fast-speech", "XTTS timing", "TTS first-audio true:", "TTS synthesis+playback:")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [line for line in lines if any(marker in line for marker in markers)][-limit:]


def _latest_progressive_timing(lines: list[str]) -> dict[str, float | int] | None:
    pattern = re.compile(
        r"progressive=True\s+chunks=(?P<chunks>\d+)\s+load=(?P<load>[0-9.]+)s\s+"
        r"synth=(?P<synth>[0-9.]+)s\s+first_chunk=(?P<first>[0-9.]+)s\s+"
        r"first_audio=(?P<audio>[0-9.]+)s\s+playback=(?P<playback>[0-9.]+)s\s+total=(?P<total>[0-9.]+)s"
    )
    for line in reversed(lines):
        match = pattern.search(line)
        if match:
            return {
                "chunks": int(match.group("chunks")),
                "load": float(match.group("load")),
                "synth": float(match.group("synth")),
                "first": float(match.group("first")),
                "audio": float(match.group("audio")),
                "playback": float(match.group("playback")),
                "total": float(match.group("total")),
            }
    return None


def main() -> int:
    print("=== AURA v0.6.5 — FAST SPEECH DIAGNOSTICS ===")
    print("Lecture seule : aucun modèle lourd n'est chargé.")
    print()
    print(f"Fast Speech actif      : {settings.FAST_SPEECH_ENABLED}")
    print(f"Premier chunk max      : {settings.FAST_SPEECH_FIRST_CHUNK_CHARS} caractères")
    print(f"Chunks suivants max    : {settings.FAST_SPEECH_NEXT_CHUNK_CHARS} caractères")
    print(f"Minimum avant découpe  : {settings.FAST_SPEECH_MIN_TEXT_CHARS} caractères")
    print(f"Nombre maximum chunks  : {settings.FAST_SPEECH_MAX_CHUNKS}")
    print(f"Streaming XTTS natif   : {settings.FAST_SPEECH_NATIVE_STREAMING} (expérimental / non utilisé)")
    print(f"Voix XTTS              : {settings.XTTS_PRESET_SPEAKER}")
    print(f"Device XTTS configuré  : {settings.XTTS_DEVICE}")

    log = settings.LOG_DIR / "aura.log"
    lines = _recent(log)
    print(f"\nJournal analysé        : {log}")
    latest = _latest_progressive_timing(lines)
    if latest:
        print("\nDernier tour progressif :")
        print(f"  chunks               : {latest['chunks']}")
        print(f"  chargement XTTS      : {latest['load']:.3f}s")
        print(f"  1er chunk synthèse   : {latest['first']:.3f}s")
        print(f"  vrai premier audio   : {latest['audio']:.3f}s")
        print(f"  synthèse cumulée     : {latest['synth']:.3f}s")
        print(f"  lecture cumulée      : {latest['playback']:.3f}s")
        print(f"  temps mur total      : {latest['total']:.3f}s")
        if latest["load"] < 1.0:
            print("  état                 : XTTS déjà chaud")
        else:
            print("  état                 : chargement XTTS inclus dans ce tour")
    else:
        print("\nAucun tour Fast Speech trouvé. Lance AURA avec Voix ON et fais une réponse de plus de 64 caractères.")

    if lines:
        print("\nDernières lignes utiles :")
        for line in lines[-12:]:
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
