"""AURA XTTS dependency compatibility check."""
from __future__ import annotations

import sys


def main() -> int:
    print(f"Python       : {sys.version.split()[0]}")
    try:
        import torch
        print(f"PyTorch      : {torch.__version__}")
    except Exception as exc:
        print(f"[FAIL] PyTorch: {exc}")
        return 1

    try:
        import transformers
        print(f"Transformers : {transformers.__version__}")
        from transformers.pytorch_utils import isin_mps_friendly  # noqa: F401
        print("[OK] isin_mps_friendly disponible")
    except Exception as exc:
        print(f"[FAIL] Transformers incompatible: {exc}")
        print("Attendu pour AURA XTTS: transformers==4.57.6")
        return 1

    try:
        import TTS
        from TTS.api import TTS  # noqa: F401
        version = getattr(TTS, "__version__", "unknown")
        print(f"Coqui TTS    : {version}")
    except Exception as exc:
        print(f"[FAIL] Coqui TTS: {exc}")
        return 1

    print("[PASS] Pile XTTS compatible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
