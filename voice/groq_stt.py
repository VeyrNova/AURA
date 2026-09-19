"""Groq Whisper speech-to-text backend for AURA v0.7.1.2."""
from __future__ import annotations

import io
import logging
import time
import wave
from urllib.parse import urlparse

import requests

from config.settings import settings
from voice.errors import SpeechRecognitionUnavailableError

logger = logging.getLogger("aura.voice.groq_stt")


class GroqWhisperSTT:
    def __init__(self):
        self.session = requests.Session()
        self._blocked_until = 0.0

    @staticmethod
    def _base_url_valid() -> bool:
        parsed = urlparse(str(settings.GROQ_BASE_URL or ""))
        return bool(parsed.scheme == "https" and parsed.hostname == "api.groq.com")

    @staticmethod
    def configured() -> bool:
        return bool(
            settings.GROQ_ENABLED
            and settings.GROQ_API_KEY
            and settings.GROQ_STT_ENABLED
            and GroqWhisperSTT._base_url_valid()
        )

    def available(self) -> bool:
        return bool(self.configured() and time.monotonic() >= self._blocked_until)

    @staticmethod
    def dependency_available() -> bool:
        return GroqWhisperSTT.configured()

    @staticmethod
    def model_ready() -> bool:
        return GroqWhisperSTT.configured()

    @staticmethod
    def _wav_bytes(audio) -> bytes:
        try:
            import numpy as np
        except Exception as exc:
            raise SpeechRecognitionUnavailableError("NumPy est requis pour préparer l'audio Groq.") from exc
        arr = np.asarray(audio, dtype=np.float32).reshape(-1)
        if arr.size == 0:
            return b""
        pcm = np.clip(arr, -1.0, 1.0)
        pcm = (pcm * 32767.0).astype("<i2", copy=False)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(int(settings.MIC_SAMPLE_RATE))
            wav.writeframes(pcm.tobytes())
        return buffer.getvalue()

    def transcribe(self, audio) -> str:
        if not self.available():
            raise SpeechRecognitionUnavailableError("La transcription Groq n'est pas configurée ou est temporairement indisponible.")
        wav_data = self._wav_bytes(audio)
        if not wav_data:
            return ""
        url = settings.GROQ_BASE_URL.rstrip("/") + "/audio/transcriptions"
        headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
        files = {"file": ("aura.wav", wav_data, "audio/wav")}
        data = {
            "model": settings.GROQ_STT_MODEL,
            "language": settings.STT_LANGUAGE,
            "response_format": "json",
            "temperature": "0",
        }
        started = time.perf_counter()
        try:
            response = self.session.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=(float(settings.GROQ_CONNECT_TIMEOUT), float(settings.GROQ_STT_TIMEOUT_SECONDS)),
                allow_redirects=False,
            )
        except requests.exceptions.Timeout as exc:
            raise SpeechRecognitionUnavailableError("La transcription Groq a dépassé le délai autorisé.") from exc
        except requests.exceptions.RequestException as exc:
            raise SpeechRecognitionUnavailableError("La transcription Groq est momentanément indisponible.") from exc
        if response.status_code == 429:
            try:
                retry = max(1.0, float(response.headers.get("retry-after") or 5.0))
            except (TypeError, ValueError):
                retry = 5.0
            self._blocked_until = time.monotonic() + retry
            raise SpeechRecognitionUnavailableError("Le quota Groq de transcription est momentanément atteint.")
        if response.status_code in {401, 403}:
            self._blocked_until = time.monotonic() + 300.0
            raise SpeechRecognitionUnavailableError("La clé Groq est refusée pour la transcription.")
        if response.status_code >= 500:
            self._blocked_until = time.monotonic() + 3.0
            raise SpeechRecognitionUnavailableError("Groq est momentanément indisponible pour la transcription.")
        if response.status_code >= 400:
            logger.warning("Groq STT HTTP status=%s", response.status_code)
            raise SpeechRecognitionUnavailableError("Groq n'a pas accepté la transcription audio.")
        try:
            text = str((response.json() or {}).get("text") or "").strip()
        except ValueError as exc:
            raise SpeechRecognitionUnavailableError("Groq a renvoyé une transcription invalide.") from exc
        logger.info(
            "Groq STT complete model=%s latency=%.3fs chars=%d bytes=%d",
            settings.GROQ_STT_MODEL,
            time.perf_counter() - started,
            len(text),
            len(wav_data),
        )
        return text
