"""Safe voice diagnostics for AURA v0.5.2. Does not print .env or secrets."""
from __future__ import annotations

import importlib.metadata
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import settings  # noqa: E402
from voice.voice_engine import VoiceEngine  # noqa: E402


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "NOT INSTALLED"


def main() -> None:
    engine = VoiceEngine()
    status = engine.status()
    profile = engine.profile
    print("=== AURA v0.5.2 VOICE DIAGNOSTICS ===")
    print(f"OS: {platform.platform()}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Architecture: {platform.machine()}")
    print(f"AURA: {settings.APP_VERSION}")
    print()
    for package in ("faster-whisper", "sounddevice", "numpy", "piper-tts", "coqui-tts", "torch", "torchaudio"):
        print(f"{package}: {package_version(package)}")
    print()
    print(f"VOICE_ENABLED: {settings.VOICE_ENABLED}")
    print(f"VOICE_PRELOAD: {settings.VOICE_PRELOAD}")
    print(f"VOICE_AUTO_SPEAK: {settings.VOICE_AUTO_SPEAK}")
    print(f"MIC_DEVICE requested: {settings.MIC_DEVICE or '<auto>'}")
    print(f"Selected input: {status.microphone_device}")
    print(f"Microphone device ready: {status.microphone_device_ready}")
    print(f"STT model: {settings.STT_MODEL}")
    print(f"STT beam/VAD: {settings.STT_BEAM_SIZE}/{settings.STT_VAD_FILTER}")
    print(f"STT device/compute: {settings.STT_DEVICE}/{settings.STT_COMPUTE_TYPE}")
    print(f"STT model ready: {status.stt_model_ready}")
    print()
    print(f"Requested TTS engine: {profile.engine}")
    print(f"Active TTS engine: {status.tts_engine}")
    print(f"Active voice: {status.tts_voice}")
    print(f"Fallback active: {status.fallback_active}")
    print(f"XTTS mode: {profile.xtts_mode}")
    print(f"XTTS preset: {profile.xtts_preset}")
    print(f"XTTS reference: {'CONFIGURED' if profile.xtts_reference_wav else 'NONE'}")
    print(f"XTTS device requested: {settings.XTTS_DEVICE}")
    print(f"XTTS marker ready: {(settings.VOICE_MODEL_DIR / 'xtts' / '.installed').is_file()}")
    print(f"Voice input ready: {status.input_ready}")
    print(f"Voice output ready: {status.output_ready}")
    print(f"Voice fully ready: {status.fully_ready}")
    print()

    try:
        devices = engine.recorder.list_input_devices()
        print("Input devices detected:")
        if not devices:
            print("  NONE")
        for dev in devices:
            marker = "  <== selected" if dev.label == status.microphone_device else ""
            print(f"  {dev.label} channels={dev.channels}{marker}")
    except Exception as exc:
        print(f"Audio device query: FAILED ({type(exc).__name__})")


if __name__ == "__main__":
    main()
