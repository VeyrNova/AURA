"""Local French speech recognition using faster-whisper (AURA v0.5.2)."""
from __future__ import annotations

import gc
import importlib.util
import logging
import threading
from pathlib import Path
from typing import Any

from config.settings import settings
from voice.errors import SpeechRecognitionUnavailableError

logger = logging.getLogger("aura.voice.stt")


class FasterWhisperSTT:
    def __init__(self):
        self._model: Any = None
        self._load_lock = threading.Lock()

    @staticmethod
    def dependency_available() -> bool:
        return importlib.util.find_spec("faster_whisper") is not None

    def model_path(self) -> Path:
        configured = settings.STT_MODEL_PATH.strip()
        if configured:
            return Path(configured).expanduser().resolve()
        return settings.VOICE_MODEL_DIR / "whisper" / settings.STT_MODEL

    def model_ready(self) -> bool:
        path = self.model_path()
        return path.is_dir() and (path / "model.bin").is_file()

    def is_available(self) -> bool:
        return settings.VOICE_ENABLED and self.dependency_available() and self.model_ready()

    def _load_model(self):
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is not None:
                return self._model
            if not self.dependency_available():
                raise SpeechRecognitionUnavailableError(
                    "La reconnaissance vocale n'est pas installée. Lance INSTALL_VOICE.bat puis redémarre AURA."
                )

            from faster_whisper import WhisperModel

            model_path = self.model_path()
            if model_path.is_dir():
                model_reference = str(model_path)
            elif settings.STT_ALLOW_MODEL_DOWNLOAD:
                model_reference = settings.STT_MODEL
            else:
                raise SpeechRecognitionUnavailableError(
                    "Le modèle vocal local n'est pas installé. Lance INSTALL_VOICE.bat avant d'utiliser le microphone."
                )

            try:
                self._model = WhisperModel(
                    model_reference,
                    device=settings.STT_DEVICE,
                    compute_type=settings.STT_COMPUTE_TYPE,
                    local_files_only=not settings.STT_ALLOW_MODEL_DOWNLOAD,
                    download_root=str(settings.VOICE_MODEL_DIR / "whisper-cache"),
                )
            except Exception as exc:
                logger.exception("Chargement du modele STT impossible")
                raise SpeechRecognitionUnavailableError(
                    "Je n'arrive pas à charger mon modèle de reconnaissance vocale local. Consulte les logs puis relance INSTALL_VOICE.bat si nécessaire."
                ) from exc
            return self._model

    def release_model(self) -> bool:
        """Release the local Whisper model to recover RAM between turns."""
        with self._load_lock:
            model = self._model
            self._model = None
        if model is None:
            return False
        try:
            del model
            gc.collect()
            logger.info("Modele STT libéré de la RAM")
            return True
        except Exception:
            logger.debug("Libération STT incomplète", exc_info=True)
            return False

    def warmup(self) -> None:
        """Load the model before the first push-to-talk to remove first-use lag."""
        if self.is_available():
            self._load_model()
            logger.info("Modele STT precharge")

    def transcribe(self, audio) -> str:
        if audio is None:
            return ""
        model = self._load_model()
        try:
            segments, info = model.transcribe(
                audio,
                language=settings.STT_LANGUAGE,
                beam_size=max(1, settings.STT_BEAM_SIZE),
                vad_filter=bool(settings.STT_VAD_FILTER),
                condition_on_previous_text=False,
                without_timestamps=True,
            )
            text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
            logger.info(
                "Transcription terminee (lang=%s, prob=%.2f, chars=%d, beam=%d, vad=%s)",
                getattr(info, "language", "?"),
                float(getattr(info, "language_probability", 0.0) or 0.0),
                len(text),
                settings.STT_BEAM_SIZE,
                settings.STT_VAD_FILTER,
            )
            return text
        except Exception as exc:
            logger.exception("Transcription vocale impossible")
            raise SpeechRecognitionUnavailableError(
                "Je n'ai pas réussi à comprendre cet enregistrement. Vérifie le microphone avec MIC_TEST.bat puis réessaie."
            ) from exc
