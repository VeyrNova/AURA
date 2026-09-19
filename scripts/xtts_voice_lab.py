"""Standalone launcher for AURA's XTTS Voice Lab."""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from ai.llm_manager import LLMManager  # noqa: E402
from runtime.resource_guardian import ResourceGuardian, ResourcePressureError  # noqa: E402
from ui.voice_lab_dialog import VoiceLabDialog  # noqa: E402
from voice.errors import VoiceError  # noqa: E402
from voice.voice_engine import VoiceEngine  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AURA XTTS Voice Lab")
    engine = VoiceEngine()
    llm = LLMManager()
    guardian = ResourceGuardian(llm, engine)
    try:
        guardian.prepare_for_tts(strict_test=True)
        speakers = engine.available_xtts_speakers()
    except ResourcePressureError as exc:
        QMessageBox.critical(None, "XTTS Voice Lab — Resource Guardian", str(exc))
        return 2
    except VoiceError as exc:
        QMessageBox.critical(None, "XTTS Voice Lab", str(exc))
        return 2
    except Exception as exc:
        QMessageBox.critical(None, "XTTS Voice Lab", f"Impossible de charger XTTS : {exc}")
        return 3
    if not speakers:
        QMessageBox.warning(None, "XTTS Voice Lab", "Aucun speaker XTTS n'a été détecté.")
        return 4
    try:
        info = engine.xtts_runtime_info()
        if info.device == "cuda":
            print(f"[XTTS] Runtime reel: CUDA · {info.gpu_name or 'GPU'} · VRAM reservee {info.reserved_mb:.0f} MiB", flush=True)
        else:
            print("[XTTS] Runtime reel: CPU", flush=True)
    except Exception as exc:
        print(f"[XTTS] Runtime indisponible: {exc}", flush=True)
    dialog = VoiceLabDialog(engine, engine.profile_store, speakers)
    dialog.profile_selected.connect(engine.reload_tts)
    dialog.exec()
    guardian.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
