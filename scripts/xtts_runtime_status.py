"""Print the XTTS configuration/runtime device without ambiguous launcher text."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from config.settings import settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-only", action="store_true")
    args = parser.parse_args()

    requested = (settings.XTTS_DEVICE or "cpu").strip().lower()
    print(f"XTTS_DEVICE      : {requested}", flush=True)
    print(f"XTTS_ALLOW_CUDA  : {settings.XTTS_ALLOW_CUDA}", flush=True)
    print(f"XTTS_PREVIEW_FAST: {settings.XTTS_PREVIEW_FAST}", flush=True)

    if requested == "cuda" and settings.XTTS_ALLOW_CUDA:
        print("Configuration    : CUDA/GPU demande explicitement", flush=True)
    elif requested == "cuda":
        print("Configuration    : CUDA demande mais BLOQUE (XTTS_ALLOW_CUDA=false)", flush=True)
        return 2
    else:
        print("Configuration    : CPU", flush=True)

    if args.config_only:
        return 0

    from voice.voice_engine import VoiceEngine
    engine = VoiceEngine()
    info = engine.xtts_runtime_info()
    print(f"Runtime reel     : {info.device}", flush=True)
    if info.device == "cuda":
        print(f"GPU              : {info.gpu_name or 'CUDA'}", flush=True)
        print(f"VRAM allouee     : {info.allocated_mb:.0f} MiB", flush=True)
        print(f"VRAM reservee    : {info.reserved_mb:.0f} MiB", flush=True)
        print(f"VRAM totale      : {info.total_mb:.0f} MiB", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
