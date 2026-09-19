"""Explicit XTTS-v2 installation/model download for AURA v0.5.2."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import settings  # noqa: E402
from voice.xtts_tts import XTTSTTS  # noqa: E402


def main() -> int:
    print("=== AURA v0.5.2 - Installation XTTS-v2 ===")
    print("XTTS-v2 utilise la Coqui Public Model License.")
    print("Cette configuration AURA est prévue pour un usage personnel / non commercial.")
    answer = input("Tape OUI pour confirmer l'usage non commercial et télécharger le modèle : ").strip().upper()
    if answer != "OUI":
        print("Installation annulée.")
        return 2

    os.environ["COQUI_TOS_AGREED"] = "1"
    os.environ["TTS_HOME"] = str(settings.XTTS_HOME)
    settings.XTTS_HOME.mkdir(parents=True, exist_ok=True)

    try:
        import torch
        from TTS.api import TTS
    except Exception as exc:
        print(f"[FAIL] Dépendances XTTS absentes ou invalides: {exc}")
        print("Relance INSTALL_XTTS.bat.")
        return 1

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[INFO] Device détecté: {device}")
    print("[DOWNLOAD] XTTS-v2. Le premier téléchargement peut être volumineux.")
    try:
        api = TTS("tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=True).to(device)
        # Accessing the model is enough to ensure assets are present. Do not synthesize
        # or clone any voice during installation.
        _ = api.speakers
    except Exception as exc:
        print(f"[FAIL] Impossible de préparer XTTS-v2: {exc}")
        return 1

    cache_dir = XTTSTTS.model_cache_dir()
    if cache_dir is None:
        print("[FAIL] XTTS-v2 a été chargé mais le cache local complet n'a pas été détecté.")
        print(r"       Vérifie models\voice\coqui\tts\tts_models--multilingual--multi-dataset--xtts_v2")
        return 1

    marker = settings.VOICE_MODEL_DIR / "xtts" / ".installed"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        f"model=xtts_v2\ndevice={device}\ncache={cache_dir}\n",
        encoding="utf-8",
    )
    print(f"[OK] Cache XTTS-v2 détecté: {cache_dir}")
    print(f"[OK] Marqueur AURA: {marker.relative_to(ROOT)}")
    print("Tu peux maintenant ouvrir AURA, cliquer sur 🎚 Voix et choisir une voix XTTS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
