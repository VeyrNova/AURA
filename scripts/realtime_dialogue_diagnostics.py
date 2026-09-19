from pathlib import Path
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from config.settings import settings
from tools.internet_manager import InternetToolManager
from voice.realtime_dialogue import RealtimeSentenceBuffer, prepare_sentence_for_realtime_speech


def main() -> int:
    print(f"AURA {settings.APP_VERSION} - Realtime Dialogue diagnostics")
    print(f"enabled={settings.REALTIME_DIALOGUE_ENABLED}")
    print(f"require_coresidence={settings.REALTIME_DIALOGUE_REQUIRE_CORESIDENCE}")
    print(f"max_ram={settings.REALTIME_DIALOGUE_MAX_RAM_PCT:.1f}%")

    buf = RealtimeSentenceBuffer()
    first = buf.feed("Bonjour ! Je commence à écrire pendant que je")
    second = buf.feed(" prépare la suite. Le dialogue reste fluide.")
    print(f"sentence_batch_1={first}")
    print(f"sentence_batch_2={second}")

    fixed = prepare_sentence_for_realtime_speech("Je peux me aider maintenant.")
    print(f"french_safe={fixed.allowed} text={fixed.text!r}")

    implicit = InternetToolManager._extract_weather_location("Quel temps fait-il sur ma position locale ?")
    explicit = InternetToolManager._extract_weather_location("Météo à Vidauban ?")
    print(f"implicit_local_location={implicit!r}")
    print(f"explicit_location={explicit!r}")

    root = Path(__file__).resolve().parents[1]
    source = (root / "ui" / "main_window.py").read_text(encoding="utf-8")
    markers = (
        "class RealtimeTTSWorker",
        "speech_segment = Signal(str)",
        "Realtime dialogue armed",
        "set_aura_stream_text(reply)",
    )
    missing = [marker for marker in markers if marker not in source]
    if missing or not settings.REALTIME_DIALOGUE_ENABLED or implicit or explicit != "Vidauban" or not fixed.allowed:
        print(f"[FAIL] missing={missing}")
        return 1
    print("[PASS] Token streaming + sentence-safe realtime voice pipeline ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
