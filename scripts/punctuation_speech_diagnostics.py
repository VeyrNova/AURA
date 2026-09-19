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
from voice.text_to_speech import strip_terminal_punctuation_for_synthesis

cases = {
    "Bonsoir.": "Bonsoir",
    "Comment vas-tu ?": "Comment vas-tu",
    "Très bien !": "Très bien",
    "Il fait 32.8.": "Il fait 32.8",
    "Bonsoir. Comment vas-tu ?": "Bonsoir. Comment vas-tu",
}
print(f"AURA {settings.APP_VERSION} — Punctuation Speech Guard")
ok = True
for source, expected in cases.items():
    result = strip_terminal_punctuation_for_synthesis(source)
    passed = result == expected
    ok = ok and passed
    print(f"{'PASS' if passed else 'FAIL'} | {source!r} -> {result!r}")
print("[PASS] La ponctuation terminale reste hors du payload TTS." if ok else "[FAIL] Diagnostic ponctuation.")
raise SystemExit(0 if ok else 1)
