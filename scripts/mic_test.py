"""Interactive RAM-only microphone test for AURA v0.5.1.1."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import settings  # noqa: E402
from voice.microphone import MicrophoneRecorder  # noqa: E402


def main() -> int:
    recorder = MicrophoneRecorder(
        sample_rate=settings.MIC_SAMPLE_RATE,
        channels=settings.MIC_CHANNELS,
        max_seconds=8,
        min_seconds=0.1,
        requested_device=settings.MIC_DEVICE,
    )
    print("=== AURA v0.5.1.1 MICROPHONE TEST ===")
    devices = recorder.list_input_devices()
    if not devices:
        print("[FAIL] Aucun périphérique d'entrée audio détecté.")
        print("Vérifie Windows > Paramètres > Confidentialité et sécurité > Microphone.")
        return 2
    print("Microphones détectés:")
    for dev in devices:
        print(f"  {dev.label} channels={dev.channels}")
    chosen = recorder.resolve_input_device()
    if chosen is None:
        print(f"[FAIL] MIC_DEVICE='{settings.MIC_DEVICE}' ne correspond à aucun microphone utilisable.")
        return 3
    print(f"\nSélection AURA: {chosen.label}")
    print("Parle normalement pendant 4 secondes...")
    try:
        recorder.start()
        time.sleep(4.0)
        audio = recorder.stop()
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 4
    if audio is None or getattr(audio, "size", 0) == 0:
        print("[FAIL] Aucun signal audio reçu.")
        return 5

    import numpy as np

    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(np.square(audio))))
    duration = audio.shape[0] / float(settings.MIC_SAMPLE_RATE)
    print(f"Durée: {duration:.2f}s | Peak: {peak:.4f} | RMS: {rms:.4f}")
    if peak < 0.003 or rms < 0.0005:
        print("[FAIL] Signal quasi silencieux. Le mauvais micro est probablement sélectionné ou le niveau Windows est trop bas.")
        print("Configure MIC_DEVICE dans .env avec l'index ou une partie du nom affiché ci-dessus.")
        return 6
    if peak < 0.03:
        print("[WARN] Signal faible, mais AURA appliquera automatiquement un gain logiciel modéré.")
    else:
        print("[PASS] La voix arrive correctement dans AURA.")
    print("Aucun fichier audio n'a été conservé.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
