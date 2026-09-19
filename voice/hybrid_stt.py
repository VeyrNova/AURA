"""Hybrid Groq/local STT facade for AURA v0.7.1.2."""
from __future__ import annotations

import logging

from config.settings import settings
from runtime.hybrid_runtime import use_groq_stt
from voice.errors import SpeechRecognitionUnavailableError
from voice.groq_stt import GroqWhisperSTT
from voice.speech_to_text import FasterWhisperSTT

logger = logging.getLogger("aura.voice.hybrid_stt")


class HybridSpeechToText:
    def __init__(self):
        self.local = FasterWhisperSTT()
        self.groq = GroqWhisperSTT()
        self.last_provider = ""

    def dependency_available(self) -> bool:
        return bool(use_groq_stt() or self.local.dependency_available())

    def model_ready(self) -> bool:
        return bool(use_groq_stt() or self.local.model_ready())

    def is_available(self) -> bool:
        return bool(settings.VOICE_ENABLED and self.dependency_available() and self.model_ready())

    def warmup(self) -> None:
        # Remote Whisper has no local model to preload. Keep the local fallback
        # cold in hybrid mode so RAM is reserved for XTTS.
        if use_groq_stt():
            logger.info("Hybrid STT warmup skipped: Groq Whisper primary, local fallback cold")
            return
        self.local.warmup()

    def release_model(self) -> bool:
        return self.local.release_model()

    def transcribe(self, audio) -> str:
        if use_groq_stt() and self.groq.available():
            try:
                text = self.groq.transcribe(audio)
                self.last_provider = "groq"
                return text
            except SpeechRecognitionUnavailableError as exc:
                if not settings.HYBRID_LOCAL_FALLBACK:
                    raise
                logger.warning("Groq STT fallback local reason=%s", exc)
        if not self.local.is_available():
            raise SpeechRecognitionUnavailableError(
                "La reconnaissance vocale n'est pas disponible : Groq est indisponible et le modèle Whisper local n'est pas prêt."
            )
        text = self.local.transcribe(audio)
        self.last_provider = "local"
        return text
