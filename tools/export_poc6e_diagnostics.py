from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    runtime = root / "runtime"
    downloads = Path.home() / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    sources = [
        runtime / "poc6c_conversation_events.jsonl",
        runtime / "poc6e_direct_text_contract.jsonl",
        runtime / "poc6b_headless_core_status.json",
    ]

    copied = 0
    for src in sources:
        if not src.is_file():
            continue
        dst = downloads / f"AURA_POC6E_{stamp}_{src.name}"
        shutil.copy2(src, dst)
        print("[OK]", dst)
        copied += 1

    if copied == 0:
        print("[INFO] Aucun diagnostic POC6E n'existe encore.")
        return 10
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
