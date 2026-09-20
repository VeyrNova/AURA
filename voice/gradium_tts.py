"""Optional Gradium TTS backend for AURA v0.7.1.3.5.

Cloud use is explicit and optional. No Gradium SDK is required: AURA uses the
published WebSocket protocol when the free ``websockets`` package is available,
and falls back to the documented REST endpoint otherwise. Secrets are read only
from settings and are never logged.
"""
from __future__ import annotations

import base64
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from config.settings import settings
from voice.errors import SpeechSynthesisUnavailableError
from voice.text_to_speech import PiperSynthesisMetrics, normalize_french_speech

logger = logging.getLogger("aura.voice.gradium")


@dataclass(frozen=True)
class GradiumVoice:
    voice_id: str
    name: str
    language: str = ""
    description: str = ""


@dataclass(frozen=True)
class GradiumSynthesisMetrics(PiperSynthesisMetrics):
    transport: str = "rest"
    connection_seconds: float = 0.0
    first_packet_seconds: float = 0.0
    connection_reused: bool = False


class GradiumTTS:
    _voices_cache: tuple[float, tuple[GradiumVoice, ...]] = (0.0, ())
    _voices_lock = threading.Lock()

    def __init__(self, profile):
        self.profile = profile
        self._stop_event = threading.Event()
        self._ws = None
        self._ws_lock = threading.Lock()
        self._request_seq = 0

    @property
    def voice_label(self) -> str:
        name = str(getattr(self.profile, "gradium_voice_name", "") or "").strip()
        voice_id = str(getattr(self.profile, "gradium_voice_id", "") or "").strip()
        return f"Gradium · {name or voice_id or 'voix non choisie'}"

    @staticmethod
    def dependency_available() -> bool:
        try:
            import sounddevice  # noqa: F401
            return True
        except Exception:
            return False

    def is_available(self) -> bool:
        return bool(
            settings.GRADIUM_ENABLED
            and settings.GRADIUM_API_KEY
            and str(getattr(self.profile, "gradium_voice_id", "") or "").strip()
            and self.dependency_available()
        )

    def model_ready(self) -> bool:
        return self.is_available()

    def warmup(self) -> None:
        return None

    def update_profile(self, profile) -> None:
        """Update the selected Gradium voice without dropping an idle socket.

        A setup frame is sent for every synthesis request, so the same retained
        WebSocket can safely serve a newly selected voice/model.
        """
        self.profile = profile

    def stop(self) -> None:
        self._stop_event.set()
        self._close_websocket()

    @staticmethod
    def websocket_dependency_available() -> bool:
        try:
            from websockets.sync.client import connect as _connect  # noqa: F401
            return True
        except Exception:
            return False

    def _close_websocket(self) -> None:
        with self._ws_lock:
            ws, self._ws = self._ws, None
        if ws is not None:
            try:
                # Gradium multiplexing docs define an unscoped EOS as the
                # graceful close signal for a reusable socket. The following
                # close() remains the hard fallback if the peer is already gone.
                ws.send(json.dumps({"type": "end_of_stream"}))
            except Exception:
                pass
            try:
                ws.close()
            except Exception:
                logger.debug("Gradium WebSocket close ignored", exc_info=True)

    def _next_request_id(self) -> str:
        self._request_seq += 1
        return f"aura-{self._request_seq:08d}"

    @staticmethod
    def _message_matches_request(msg: dict, request_id: str) -> bool:
        # Gradium echoes client_req_id on multiplexed responses. Accept a
        # missing id only for compatibility with older/fake servers; a
        # different explicit id belongs to another logical request.
        echoed = str(msg.get("client_req_id") or "").strip()
        return not echoed or echoed == request_id

    @staticmethod
    def _safe_detail(raw: bytes | str) -> str:
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        else:
            text = str(raw or "")
        detail = text.strip()
        if detail:
            try:
                payload = json.loads(detail)
                if isinstance(payload, dict):
                    candidate = payload.get("message", payload.get("detail", payload.get("error", "")))
                    if isinstance(candidate, dict):
                        candidate = candidate.get("message") or candidate.get("detail") or candidate.get("code") or ""
                    detail = str(candidate or detail)
            except Exception:
                pass
        secret = str(settings.GRADIUM_API_KEY or "")
        if secret:
            detail = detail.replace(secret, "[REDACTED]")
        return " ".join(detail.split())[:500]

    @classmethod
    def _json_get(cls, path: str, params: dict[str, Any] | None = None) -> Any:
        url = settings.GRADIUM_API_BASE.rstrip("/") + "/" + path.lstrip("/")
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={"x-api-key": settings.GRADIUM_API_KEY, "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=float(settings.GRADIUM_TIMEOUT_SECONDS)) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = b""
            try:
                raw = exc.read(4096)
            except Exception:
                pass
            detail = cls._safe_detail(raw)
            raise SpeechSynthesisUnavailableError(f"Gradium HTTP {exc.code}" + (f" · {detail}" if detail else "")) from exc

    @classmethod
    def list_voices(cls, *, force_refresh: bool = False) -> tuple[GradiumVoice, ...]:
        """List voices available to the authenticated Gradium organisation.

        Gradium defaults ``include_catalog`` to false. AURA explicitly requests
        the public catalog so a fresh account can actually choose a stock voice
        without first creating a custom clone.
        """
        if not settings.GRADIUM_API_KEY:
            raise SpeechSynthesisUnavailableError("Clé Gradium non configurée.")
        now = time.monotonic()
        with cls._voices_lock:
            cached_at, cached = cls._voices_cache
            if cached and not force_refresh and now - cached_at < float(settings.GRADIUM_VOICE_CACHE_SECONDS):
                return cached
        payload = cls._json_get("voices/", {"include_catalog": "true" if settings.GRADIUM_INCLUDE_CATALOG else "false", "limit": 500})
        items: list[Any]
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("voices") or payload.get("items") or payload.get("data") or []
        else:
            items = []
        voices: list[GradiumVoice] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            voice_id = str(item.get("uid") or item.get("voice_id") or item.get("id") or "").strip()
            name = str(item.get("name") or item.get("display_name") or voice_id).strip()
            if not voice_id:
                continue
            voices.append(GradiumVoice(
                voice_id=voice_id,
                name=name or voice_id,
                language=str(item.get("language") or item.get("lang") or ""),
                description=str(item.get("description") or ""),
            ))
        result = tuple(sorted(voices, key=lambda x: (0 if str(x.language).lower().startswith("fr") else 1, x.name.casefold())))
        with cls._voices_lock:
            cls._voices_cache = (time.monotonic(), result)
        logger.info("Gradium voices loaded count=%d include_catalog=%s", len(result), settings.GRADIUM_INCLUDE_CATALOG)
        return result

    def _open_websocket(self):
        try:
            from websockets.sync.client import connect
        except Exception as exc:
            raise ModuleNotFoundError("websockets") from exc
        started = time.perf_counter()
        ws = connect(
            settings.GRADIUM_WS_TTS_URL,
            additional_headers={"x-api-key": settings.GRADIUM_API_KEY},
            open_timeout=float(settings.GRADIUM_TIMEOUT_SECONDS),
            close_timeout=2,
            ping_interval=20,
            ping_timeout=20,
        )
        return ws, time.perf_counter() - started

    def _speak_websocket(self, clean: str) -> GradiumSynthesisMetrics:
        import sounddevice as sd

        voice_id = str(getattr(self.profile, "gradium_voice_id", "") or "").strip()
        started = time.perf_counter()
        first_packet = 0.0
        first_audio = 0.0
        bytes_played = 0
        chunk_count = 0
        connection_seconds = 0.0
        reused = False
        self._stop_event.clear()

        # A single persistent socket avoids paying the TLS/WebSocket handshake on
        # every short AURA reply. Gradium documents sequential requests on a
        # retained socket when close_ws_on_eos is false. Access is serialized.
        with self._ws_lock:
            ws = self._ws
            if ws is None:
                ws, connection_seconds = self._open_websocket()
                self._ws = ws
            else:
                reused = True

            try:
                request_id = self._next_request_id()
                setup = {
                    "type": "setup",
                    "voice_id": voice_id,
                    "model_name": str(getattr(self.profile, "gradium_model", "") or settings.GRADIUM_MODEL),
                    "output_format": "pcm_24000",
                    "close_ws_on_eos": False,
                    "client_req_id": request_id,
                }
                ws.send(json.dumps(setup))
                while True:
                    ready_raw = ws.recv(timeout=float(settings.GRADIUM_TIMEOUT_SECONDS))
                    ready = json.loads(ready_raw)
                    if not isinstance(ready, dict):
                        continue
                    if not self._message_matches_request(ready, request_id):
                        logger.debug("Gradium ignored frame for another request during setup")
                        continue
                    if ready.get("type") == "error":
                        raise SpeechSynthesisUnavailableError("Gradium · " + self._safe_detail(ready.get("message") or ready))
                    if ready.get("type") == "ready":
                        break
                ws.send(json.dumps({"type": "text", "text": clean, "client_req_id": request_id}, ensure_ascii=False))
                ws.send(json.dumps({"type": "end_of_stream", "client_req_id": request_id}))

                with sd.RawOutputStream(samplerate=24000, channels=1, dtype="int16") as stream:
                    while not self._stop_event.is_set():
                        raw = ws.recv(timeout=float(settings.GRADIUM_TIMEOUT_SECONDS))
                        if first_packet <= 0:
                            first_packet = time.perf_counter() - started
                        if isinstance(raw, bytes):
                            # Defensive compatibility; Gradium's documented wire
                            # format is JSON with base64 audio.
                            chunk = raw
                            kind = "audio"
                        else:
                            msg = json.loads(raw)
                            kind = str(msg.get("type") or "") if isinstance(msg, dict) else ""
                            if isinstance(msg, dict) and not self._message_matches_request(msg, request_id):
                                logger.debug("Gradium ignored frame for another request type=%s", kind or "unknown")
                                continue
                            if kind == "audio":
                                chunk = base64.b64decode(str(msg.get("audio") or ""))
                            elif kind == "end_of_stream":
                                break
                            elif kind == "error":
                                raise SpeechSynthesisUnavailableError("Gradium · " + self._safe_detail(msg.get("message") or msg))
                            else:
                                continue
                        if kind != "audio":
                            continue
                        if len(chunk) % 2:
                            chunk = chunk[:-1]
                        if not chunk:
                            continue
                        stream.write(chunk)
                        bytes_played += len(chunk)
                        chunk_count += 1
                        if first_audio <= 0:
                            first_audio = time.perf_counter() - started
            except SpeechSynthesisUnavailableError:
                # Protocol errors may leave unread frames; never reuse that socket.
                bad, self._ws = self._ws, None
                if bad is not None:
                    try:
                        bad.close()
                    except Exception:
                        pass
                raise
            except Exception as exc:
                bad, self._ws = self._ws, None
                if bad is not None:
                    try:
                        bad.close()
                    except Exception:
                        pass
                raise SpeechSynthesisUnavailableError(f"Gradium WebSocket indisponible ({type(exc).__name__}).") from exc

        total = time.perf_counter() - started
        ttfa = first_audio or first_packet or total
        logger.info(
            "Gradium TTS transport=websocket chars=%d connect=%.3fs reused=%s first_packet=%.3fs first_audio=%.3fs total=%.3fs chunks=%d pcm_bytes=%d",
            len(clean), connection_seconds, reused, first_packet or ttfa, ttfa, total, chunk_count, bytes_played,
        )
        return GradiumSynthesisMetrics(
            device="cloud", model_load_seconds=0.0, synthesis_seconds=ttfa,
            playback_seconds=max(0.0, total - ttfa), text_chars=len(clean),
            time_to_audio_seconds=ttfa, chunk_count=max(1, chunk_count), streaming=True,
            transport="websocket", connection_seconds=connection_seconds,
            first_packet_seconds=first_packet or ttfa, connection_reused=reused,
        )

    async def _speak_websocket_async(self, clean: str) -> GradiumSynthesisMetrics:
        """Compatibility shim kept for historical tests/extensions.

        v0.7.1.3.5.3 uses the synchronous persistent client because an asyncio
        connection created inside ``asyncio.run`` cannot be safely retained
        across independent TTS turns.
        """
        return self._speak_websocket(clean)

    def _speak_rest(self, clean: str) -> PiperSynthesisMetrics:
        import sounddevice as sd
        voice_id = str(getattr(self.profile, "gradium_voice_id", "") or "").strip()
        body = {
            "text": clean,
            "voice_id": voice_id,
            "output_format": "pcm_24000",
            "only_audio": True,
        }
        url = settings.GRADIUM_API_BASE.rstrip("/") + "/post/speech/tts"
        req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"x-api-key": settings.GRADIUM_API_KEY, "Content-Type": "application/json", "Accept": "application/octet-stream"}, method="POST")
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=float(settings.GRADIUM_TIMEOUT_SECONDS)) as response:
                pcm = response.read()
        except urllib.error.HTTPError as exc:
            raw = b""
            try: raw = exc.read(4096)
            except Exception: pass
            detail = self._safe_detail(raw)
            raise SpeechSynthesisUnavailableError(f"Gradium HTTP {exc.code}" + (f" · {detail}" if detail else "")) from exc
        if len(pcm) % 2: pcm = pcm[:-1]
        synthesis = time.perf_counter() - started
        if not pcm:
            raise SpeechSynthesisUnavailableError("Gradium n'a retourné aucun audio.")
        sd.play(memoryview(pcm).cast("h"), samplerate=24000, blocking=True)
        total = time.perf_counter() - started
        logger.info("Gradium TTS transport=rest chars=%d first_audio=%.3fs total=%.3fs pcm_bytes=%d", len(clean), synthesis, total, len(pcm))
        return GradiumSynthesisMetrics(device="cloud", model_load_seconds=0.0, synthesis_seconds=synthesis,
            playback_seconds=max(0.0,total-synthesis), text_chars=len(clean), time_to_audio_seconds=synthesis,
            chunk_count=1, streaming=False, transport="rest", connection_seconds=0.0,
            first_packet_seconds=synthesis, connection_reused=False)

    def speak(self, text: str):
        if not self.is_available():
            raise SpeechSynthesisUnavailableError("Gradium n'est pas configuré ou aucune voix n'est sélectionnée.")
        clean = normalize_french_speech(str(text or "").strip())
        if not clean:
            return None
        if len(clean) > int(settings.CLOUD_TTS_MAX_SPEECH_CHARS):
            raise SpeechSynthesisUnavailableError("Réponse trop longue pour le canal cloud concis.")
        if settings.GRADIUM_PREFER_WEBSOCKET:
            try:
                return self._speak_websocket(clean)
            except ModuleNotFoundError:
                logger.info("Gradium WebSocket dependency missing; REST fallback")
            except SpeechSynthesisUnavailableError as exc:
                logger.warning("Gradium WebSocket échec, fallback REST: %s", exc)
        return self._speak_rest(clean)
