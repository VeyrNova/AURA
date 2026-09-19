"""Explicit one-time download of AURA voice models.

Run only when the user intentionally launches INSTALL_VOICE.bat. Runtime voice
code is configured to stay local and not auto-download models by default.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import settings  # noqa: E402


def file_md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(
    url: str,
    destination: Path,
    *,
    expected_size: int | None = None,
    expected_md5: str | None = None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        size_ok = expected_size is None or destination.stat().st_size == expected_size
        md5_ok = expected_md5 is None or file_md5(destination) == expected_md5
        if size_ok and md5_ok:
            print(f"[OK] Deja present et verifie: {destination.relative_to(ROOT)}")
            return
        print(f"[WARN] Fichier local invalide, nouveau telechargement: {destination.name}")
    temp = destination.with_suffix(destination.suffix + ".part")
    print(f"[DOWNLOAD] {destination.name}")
    req = Request(url, headers={"User-Agent": "AURA-Voice-Setup/0.5.1"})
    with urlopen(req, timeout=60) as response, temp.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    temp.replace(destination)
    if expected_size is not None and destination.stat().st_size != expected_size:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Taille inattendue pour {destination.name}")
    if expected_md5 is not None and file_md5(destination) != expected_md5:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Empreinte MD5 inattendue pour {destination.name}")
    print(f"[OK] {destination.relative_to(ROOT)} ({destination.stat().st_size / 1024 / 1024:.1f} MB)")


def install_piper_voice() -> None:
    voice = settings.TTS_VOICE
    if voice != "fr_FR-siwis-medium":
        raise RuntimeError(
            "Le script v0.5.1 telecharge uniquement fr_FR-siwis-medium par securite. "
            "Pour une autre voix, installe les fichiers ONNX/JSON manuellement et configure TTS_MODEL_PATH."
        )
    base = "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium"
    model_dir = settings.VOICE_MODEL_DIR / "piper"
    # Values published in the official rhasspy/piper-voices voices.json.
    download(
        f"{base}/{voice}.onnx",
        model_dir / f"{voice}.onnx",
        expected_size=63_201_294,
        expected_md5="20e876e8c839e9b11a26085858f2300c",
    )
    download(
        f"{base}/{voice}.onnx.json",
        model_dir / f"{voice}.onnx.json",
        expected_size=4_875,
        expected_md5="a407e7e6901feb79c2ea2a5466076cce",
    )


def install_whisper_model() -> None:
    from faster_whisper import download_model

    output_dir = settings.VOICE_MODEL_DIR / "whisper" / settings.STT_MODEL
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[DOWNLOAD] faster-whisper {settings.STT_MODEL} -> {output_dir.relative_to(ROOT)}")
    download_model(settings.STT_MODEL, output_dir=str(output_dir), local_files_only=False)
    if not (output_dir / "model.bin").is_file():
        raise RuntimeError("Le modele Whisper n'a pas ete telecharge correctement.")
    digest = hashlib.sha256((output_dir / "model.bin").read_bytes()[:1024 * 1024]).hexdigest()
    print(f"[OK] Whisper installe (empreinte partielle SHA256: {digest[:16]}...)")


def main() -> int:
    print("=== AURA v0.5.1 - Installation vocale locale ===")
    print("Cette operation telecharge explicitement les modeles STT/TTS puis AURA les utilisera localement.")
    install_piper_voice()
    install_whisper_model()
    print("\n[TERMINE] Voix locale installee. Tu peux lancer RUN_AURA.bat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
