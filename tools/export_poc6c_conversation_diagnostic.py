from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    src = root / "runtime" / "poc6c_conversation_events.jsonl"
    downloads = Path.home() / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = downloads / f"AURA_POC6C_CONVERSATION_EVENTS_{stamp}.jsonl"

    if not src.is_file():
        print("[INFO] Aucun journal POC6C n'existe encore.")
        print("[INFO] Envoie au moins un message depuis la vue Conversation.")
        return 10

    shutil.copy2(src, dst)
    print("[OK] Diagnostic exporte:")
    print(dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
