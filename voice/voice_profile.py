"""Persistent local voice profile for AURA v0.5.2.

The profile contains only non-secret local voice preferences. Reference audio is
copied into AURA's controlled voice directory so runtime TTS never needs an
arbitrary filesystem path.
"""
from __future__ import annotations

import json
import shutil
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

from config.settings import settings

# Female preset speaker names published in the XTTS documentation.
XTTS_FEMALE_PRESETS = (
    "Ana Florence",
    "Claribel Dervla",
    "Daisy Studious",
    "Gracie Wise",
    "Tammie Ema",
    "Alison Dietlinde",
    "Annmarie Nele",
    "Asya Anara",
    "Brenda Stern",
    "Gitta Nikolina",
    "Henriette Usha",
    "Sofia Hellen",
    "Tammy Grit",
    "Tanja Adelina",
    "Nova Hogarth",
    "Maja Ruoho",
    "Camilla Holmström",
    "Alexandra Hisakawa",
    "Alma María",
    "Rosemary Okafor",
)


@dataclass
class VoiceProfile:
    engine: str = "xtts"
    fallback_engine: str = "piper"
    cloud_fallback_engine: str = "gradium"
    xtts_mode: str = "preset"  # preset | custom
    xtts_preset: str = "Ana Florence"
    xtts_language: str = "fr"
    xtts_speaker_id: str = "AURA_CUSTOM"
    xtts_reference_wav: str = ""
    xtts_speed: float = 0.96
    xtts_temperature: float = 0.68
    volume: float = 0.92
    elevenlabs_voice_id: str = ""
    elevenlabs_voice_name: str = ""
    elevenlabs_model: str = "eleven_flash_v2_5"
    elevenlabs_stability: float = 0.50
    elevenlabs_similarity: float = 0.75
    elevenlabs_speed: float = 1.0
    gradium_voice_id: str = ""
    gradium_voice_name: str = ""
    gradium_model: str = "default"
    resemble_voice_uuid: str = ""
    resemble_voice_name: str = ""
    chatterbox_reference_wav: str = ""

    def normalized(self) -> "VoiceProfile":
        self.engine = (self.engine or "xtts").strip().lower()
        if self.engine not in {"xtts", "piper", "elevenlabs", "gradium", "resemble", "chatterbox"}:
            self.engine = "xtts"
        self.fallback_engine = (self.fallback_engine or "piper").strip().lower()
        if self.fallback_engine not in {"xtts", "piper", "none"}:
            self.fallback_engine = "piper"
        self.cloud_fallback_engine = (self.cloud_fallback_engine or settings.XTTS_LOCAL_FIRST_CLOUD_FALLBACK or "none").strip().lower()
        if self.cloud_fallback_engine not in {"gradium", "elevenlabs", "resemble", "none"}:
            self.cloud_fallback_engine = "none"
        self.xtts_mode = (self.xtts_mode or "preset").strip().lower()
        if self.xtts_mode not in {"preset", "custom"}:
            self.xtts_mode = "preset"
        self.xtts_preset = (self.xtts_preset or "Ana Florence").strip()
        if not self.xtts_preset:
            self.xtts_preset = "Ana Florence"
        self.xtts_language = (self.xtts_language or "fr").strip().lower()
        self.xtts_speed = min(1.10, max(0.80, float(self.xtts_speed)))
        self.xtts_temperature = min(0.95, max(0.45, float(self.xtts_temperature)))
        self.volume = min(1.0, max(0.1, float(self.volume)))
        self.elevenlabs_voice_id = str(self.elevenlabs_voice_id or "").strip()
        self.elevenlabs_voice_name = str(self.elevenlabs_voice_name or "").strip()
        self.elevenlabs_model = str(self.elevenlabs_model or settings.ELEVENLABS_MODEL).strip() or settings.ELEVENLABS_MODEL
        self.elevenlabs_stability = min(1.0, max(0.0, float(self.elevenlabs_stability)))
        self.elevenlabs_similarity = min(1.0, max(0.0, float(self.elevenlabs_similarity)))
        self.elevenlabs_speed = min(1.2, max(0.7, float(self.elevenlabs_speed)))
        self.gradium_voice_id = str(self.gradium_voice_id or "").strip()
        self.gradium_voice_name = str(self.gradium_voice_name or "").strip()
        self.gradium_model = str(self.gradium_model or settings.GRADIUM_MODEL).strip() or settings.GRADIUM_MODEL
        self.resemble_voice_uuid = str(self.resemble_voice_uuid or "").strip()
        self.resemble_voice_name = str(self.resemble_voice_name or "").strip()
        self.chatterbox_reference_wav = str(self.chatterbox_reference_wav or "").strip()
        return self


class VoiceProfileStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (settings.CONFIG_DIR / "voice_profile.json")
        self.reference_dir = settings.VOICE_MODEL_DIR / "references"
        self.reference_dir.mkdir(parents=True, exist_ok=True)

    def default_profile(self) -> VoiceProfile:
        return VoiceProfile(
            engine=settings.TTS_ENGINE,
            fallback_engine=settings.TTS_FALLBACK_ENGINE,
            cloud_fallback_engine=settings.XTTS_LOCAL_FIRST_CLOUD_FALLBACK,
            xtts_mode=settings.XTTS_VOICE_MODE,
            xtts_preset=settings.XTTS_PRESET_SPEAKER,
            xtts_language=settings.XTTS_LANGUAGE,
            xtts_speaker_id=settings.XTTS_SPEAKER_ID,
            xtts_reference_wav=settings.XTTS_REFERENCE_WAV,
            xtts_speed=settings.XTTS_SPEED,
            xtts_temperature=settings.XTTS_TEMPERATURE,
            volume=settings.TTS_VOLUME,
            elevenlabs_model=settings.ELEVENLABS_MODEL,
        ).normalized()

    def load(self) -> VoiceProfile:
        if not self.path.is_file():
            return self.default_profile()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = VoiceProfile.__dataclass_fields__.keys()
            profile = VoiceProfile(**{k: v for k, v in data.items() if k in allowed})
            return profile.normalized()
        except Exception:
            return self.default_profile()

    def save(self, profile: VoiceProfile) -> VoiceProfile:
        profile = profile.normalized()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(asdict(profile), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)
        return profile

    def import_reference(self, source: str | Path) -> Path:
        source_path = Path(source).expanduser().resolve()
        if not source_path.is_file():
            raise ValueError("Le fichier de référence n'existe pas.")
        if source_path.suffix.lower() != ".wav":
            raise ValueError("Utilise un fichier WAV pour la référence vocale XTTS.")
        if source_path.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("Le fichier de référence est trop volumineux (50 Mo maximum).")
        # Validate basic WAV readability before copying.
        try:
            with wave.open(str(source_path), "rb") as wav:
                if wav.getnchannels() < 1 or wav.getframerate() < 8000 or wav.getnframes() < 8000:
                    raise ValueError("Le WAV de référence est trop court ou invalide.")
        except wave.Error as exc:
            raise ValueError("Le fichier sélectionné n'est pas un WAV PCM lisible.") from exc

        destination = self.reference_dir / "aura_reference.wav"
        shutil.copy2(source_path, destination)
        return destination
