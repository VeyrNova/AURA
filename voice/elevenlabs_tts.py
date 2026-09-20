"""Optional ElevenLabs low-latency TTS backend for AURA v0.7.1.3.4.6.

No SDK dependency is required: the backend uses urllib from the standard
library and streams raw PCM directly to sounddevice. The API key is read only
through config.settings and is never logged or persisted by this module.
"""
from __future__ import annotations

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

logger = logging.getLogger("aura.voice.elevenlabs")


@dataclass(frozen=True)
class ElevenLabsVoice:
    voice_id: str
    name: str
    category: str = ""
    description: str = ""


class ElevenLabsTTS:
    _voices_cache: tuple[float, tuple[ElevenLabsVoice, ...]] = (0.0, ())
    _voices_lock = threading.Lock()
    _quota_cache: tuple[float, dict[str, Any]] = (0.0, {})
    _quota_lock = threading.Lock()

    def __init__(self, profile):
        self.profile = profile
        self._stop_event = threading.Event()

    @property
    def voice_label(self) -> str:
        name = str(getattr(self.profile, "elevenlabs_voice_name", "") or "").strip()
        voice_id = str(getattr(self.profile, "elevenlabs_voice_id", "") or "").strip()
        return f"ElevenLabs · {name or voice_id or 'voix non choisie'}"

    @staticmethod
    def dependency_available() -> bool:
        # urllib is part of Python; sounddevice is already an AURA voice dependency.
        try:
            import sounddevice  # noqa: F401
            return True
        except Exception:
            return False

    def model_ready(self) -> bool:
        return bool(self.is_available())

    def is_available(self) -> bool:
        return bool(
            settings.ELEVENLABS_ENABLED
            and settings.ELEVENLABS_API_KEY
            and str(getattr(self.profile, "elevenlabs_voice_id", "") or "").strip()
            and self.dependency_available()
        )

    def warmup(self) -> None:
        # Never spend cloud quota for a warmup. Availability is checked lazily.
        return None

    def stop(self) -> None:
        self._stop_event.set()

    @staticmethod
    def _safe_http_error_detail(exc: urllib.error.HTTPError) -> str:
        """Extract a short provider error without ever exposing the API key."""
        raw = b""
        try:
            raw = exc.read(4096) or b""
        except Exception:
            raw = b""
        text = raw.decode("utf-8", errors="replace").strip()
        detail = ""
        if text:
            try:
                payload = json.loads(text)
                candidate = payload.get("detail", payload.get("message", payload.get("error", ""))) if isinstance(payload, dict) else ""
                if isinstance(candidate, dict):
                    status = str(candidate.get("status") or candidate.get("code") or "").strip()
                    message = str(candidate.get("message") or candidate.get("detail") or "").strip()
                    detail = " · ".join(part for part in (status, message) if part)
                else:
                    detail = str(candidate or "").strip()
            except Exception:
                detail = text
        # Provider messages should never contain the secret, but fail closed if they do.
        secret = str(settings.ELEVENLABS_API_KEY or "")
        if secret and detail:
            detail = detail.replace(secret, "[REDACTED]")
        detail = " ".join(detail.split())[:500]
        return detail

    @classmethod
    def _json_get(cls, url: str) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            headers={"xi-api-key": settings.ELEVENLABS_API_KEY, "Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=float(settings.ELEVENLABS_TIMEOUT_SECONDS)) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def api_diagnostics(cls) -> dict[str, dict[str, Any]]:
        """Read-only API diagnostics. No TTS generation and therefore no voice credits."""
        if not settings.ELEVENLABS_API_KEY:
            raise SpeechSynthesisUnavailableError("Clé ElevenLabs non configurée.")
        base = settings.ELEVENLABS_API_BASE.rstrip('/')
        checks = {
            "user": f"{base}/v1/user",
            "quota": f"{base}/v1/user/subscription",
            "voices": f"{base}/v2/voices?page_size=1",
        }
        result: dict[str, dict[str, Any]] = {}
        for name, url in checks.items():
            try:
                cls._json_get(url)
                result[name] = {"ok": True, "http": 200, "detail": ""}
            except urllib.error.HTTPError as exc:
                detail = cls._safe_http_error_detail(exc)
                result[name] = {"ok": False, "http": int(exc.code), "detail": detail}
                logger.warning("ElevenLabs diagnostic endpoint=%s http=%s detail=%s", name, exc.code, detail or "none")
            except Exception as exc:
                result[name] = {"ok": False, "http": 0, "detail": type(exc).__name__}
                logger.warning("ElevenLabs diagnostic endpoint=%s transport_error=%s", name, type(exc).__name__)
        return result

    @classmethod
    def list_voices(cls, *, force_refresh: bool = False) -> tuple[ElevenLabsVoice, ...]:
        if not settings.ELEVENLABS_API_KEY:
            raise SpeechSynthesisUnavailableError("Clé ElevenLabs non configurée.")
        now = time.monotonic()
        ttl = max(30.0, float(settings.ELEVENLABS_VOICE_CACHE_SECONDS))
        with cls._voices_lock:
            cached_at, cached = cls._voices_cache
            if cached and not force_refresh and now - cached_at < ttl:
                return cached

        base = settings.ELEVENLABS_API_BASE.rstrip('/')
        # Current endpoint first. Some accounts/proxies have returned HTTP 400
        # for optional sorting parameters, so retry with a minimal query before
        # falling back to ElevenLabs' still-supported deprecated v1 list route.
        urls = [
            f"{base}/v2/voices?{urllib.parse.urlencode({'page_size': 100, 'sort': 'name', 'sort_direction': 'asc'})}",
            f"{base}/v2/voices?{urllib.parse.urlencode({'page_size': 100})}",
            f"{base}/v1/voices",
        ]
        payload: dict[str, Any] | None = None
        last_http: tuple[int, str] | None = None
        for attempt, url in enumerate(urls, start=1):
            try:
                payload = cls._json_get(url)
                if attempt > 1:
                    logger.info("ElevenLabs voices compatibility path PASS attempt=%d endpoint=%s", attempt, urllib.parse.urlparse(url).path)
                break
            except urllib.error.HTTPError as exc:
                detail = cls._safe_http_error_detail(exc)
                last_http = (int(exc.code), detail)
                logger.warning(
                    "ElevenLabs voices request failed attempt=%d http=%s endpoint=%s detail=%s",
                    attempt, exc.code, urllib.parse.urlparse(url).path, detail or "none",
                )
                if exc.code in {401, 403}:
                    suffix = f" · {detail}" if detail else ""
                    raise SpeechSynthesisUnavailableError(f"Clé ElevenLabs refusée (HTTP {exc.code}){suffix}") from exc
                if exc.code == 429:
                    suffix = f" · {detail}" if detail else ""
                    raise SpeechSynthesisUnavailableError(f"Quota ElevenLabs indisponible ou épuisé (HTTP 429){suffix}") from exc
                # Only compatibility-retry client-side request errors. Other
                # classes are surfaced immediately to avoid masking outages.
                if exc.code not in {400, 404, 422}:
                    suffix = f" · {detail}" if detail else ""
                    raise SpeechSynthesisUnavailableError(f"ElevenLabs HTTP {exc.code}{suffix}") from exc
            except Exception as exc:
                raise SpeechSynthesisUnavailableError("Impossible de récupérer les voix ElevenLabs.") from exc

        if payload is None:
            code, detail = last_http or (0, "")
            suffix = f" · {detail}" if detail else ""
            raise SpeechSynthesisUnavailableError(f"Liste des voix ElevenLabs refusée (HTTP {code}){suffix}")

        voices: list[ElevenLabsVoice] = []
        for item in payload.get("voices") or []:
            voice_id = str(item.get("voice_id") or "").strip()
            name = str(item.get("name") or "").strip()
            if not voice_id or not name:
                continue
            voices.append(
                ElevenLabsVoice(
                    voice_id=voice_id,
                    name=name,
                    category=str(item.get("category") or ""),
                    description=str(item.get("description") or ""),
                )
            )
        voices.sort(key=lambda voice: voice.name.casefold())
        result = tuple(voices)
        with cls._voices_lock:
            cls._voices_cache = (time.monotonic(), result)
        logger.info("ElevenLabs voices loaded count=%d cache=%s", len(result), False)
        return result

    @classmethod
    def quota_status(cls, *, force_refresh: bool = False) -> dict[str, Any]:
        if not settings.ELEVENLABS_API_KEY:
            raise SpeechSynthesisUnavailableError("Clé ElevenLabs non configurée.")
        now = time.monotonic()
        ttl = max(10.0, float(settings.ELEVENLABS_QUOTA_CACHE_SECONDS))
        with cls._quota_lock:
            cached_at, cached = cls._quota_cache
            if cached and not force_refresh and now - cached_at < ttl:
                return dict(cached)
        req = urllib.request.Request(
            f"{settings.ELEVENLABS_API_BASE.rstrip('/')}/v1/user/subscription",
            headers={"xi-api-key": settings.ELEVENLABS_API_KEY, "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=float(settings.ELEVENLABS_TIMEOUT_SECONDS)) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = cls._safe_http_error_detail(exc)
            logger.warning("ElevenLabs quota request failed http=%s detail=%s", exc.code, detail or "none")
            suffix = f" · {detail}" if detail else ""
            if exc.code in {401, 403}:
                raise SpeechSynthesisUnavailableError(f"Clé ElevenLabs refusée (HTTP {exc.code}){suffix}") from exc
            raise SpeechSynthesisUnavailableError(f"Quota ElevenLabs invérifiable (HTTP {exc.code}){suffix}") from exc
        except Exception as exc:
            raise SpeechSynthesisUnavailableError("Quota ElevenLabs invérifiable. Piper prend le relais.") from exc
        status = {
            "tier": str(payload.get("tier") or ""),
            "status": str(payload.get("status") or ""),
            "character_count": int(payload.get("character_count") or 0),
            "character_limit": int(payload.get("character_limit") or 0),
            "max_credit_limit_extension": payload.get("max_credit_limit_extension", 0),
            "current_overage": payload.get("current_overage") or {},
            "next_character_count_reset_unix": payload.get("next_character_count_reset_unix"),
            "has_open_invoices": bool(payload.get("has_open_invoices", False)),
        }
        with cls._quota_lock:
            cls._quota_cache = (time.monotonic(), dict(status))
        return status

    @classmethod
    def ensure_included_quota(cls, text_chars: int) -> dict[str, Any]:
        if not settings.ELEVENLABS_REQUIRE_QUOTA_CHECK:
            return {}
        status = cls.quota_status()
        used = int(status.get("character_count") or 0)
        limit = int(status.get("character_limit") or 0)
        if limit <= 0:
            raise SpeechSynthesisUnavailableError("Quota ElevenLabs inclus non mesurable. Piper prend le relais.")
        request_chars = max(0, int(text_chars))
        if used + request_chars > limit:
            raise SpeechSynthesisUnavailableError("Quota ElevenLabs inclus atteint. Piper prend le relais sans dépassement payant.")
        remaining = max(0, limit - used)
        remaining_ratio = (remaining / limit) if limit > 0 else 0.0
        critical_ratio = float(settings.ELEVENLABS_CRITICAL_QUOTA_RATIO)
        low_ratio = max(critical_ratio, float(settings.ELEVENLABS_LOW_QUOTA_RATIO))
        if remaining_ratio <= critical_ratio:
            raise SpeechSynthesisUnavailableError(
                "Budget ElevenLabs critique. Piper prend le relais pour préserver le quota gratuit."
            )
        if remaining_ratio <= low_ratio and request_chars > int(settings.ELEVENLABS_LOW_QUOTA_MAX_CHARS):
            raise SpeechSynthesisUnavailableError(
                "Budget ElevenLabs bas : cette phrase est trop longue pour le canal cloud économique. Piper prend le relais."
            )
        overage = status.get("current_overage") or {}
        try:
            overage_amount = float(overage.get("amount") or 0)
        except Exception:
            overage_amount = 0.0
        if overage_amount > 0:
            raise SpeechSynthesisUnavailableError("ElevenLabs signale déjà un dépassement facturé. Piper prend le relais.")
        subscription_status = str(status.get("status") or "").strip().lower()
        if subscription_status and subscription_status not in {"active", "free", "trial"}:
            raise SpeechSynthesisUnavailableError(
                f"Abonnement ElevenLabs indisponible ({subscription_status}). Piper prend le relais."
            )
        if bool(status.get("has_open_invoices")):
            raise SpeechSynthesisUnavailableError("ElevenLabs signale une facture ouverte. Piper prend le relais.")
        return status

    def speak(self, text: str):
        if not self.is_available():
            raise SpeechSynthesisUnavailableError("ElevenLabs n'est pas configuré ou aucune voix n'est sélectionnée.")
        clean = normalize_french_speech(str(text or "").strip())
        if not clean:
            return None
        if len(clean) > int(settings.ELEVENLABS_MAX_SPEECH_CHARS):
            raise SpeechSynthesisUnavailableError("Réponse trop longue pour le canal ElevenLabs concis.")
        quota = self.ensure_included_quota(len(clean))
        if quota:
            used = int(quota.get("character_count") or 0)
            limit = int(quota.get("character_limit") or 0)
            remaining = max(0, limit - used)
            logger.info(
                "ElevenLabs included quota gate PASS used=%d limit=%d remaining=%d request_chars=%d",
                used, limit, remaining, len(clean),
            )

        voice_id = str(getattr(self.profile, "elevenlabs_voice_id", "") or "").strip()
        model_id = str(getattr(self.profile, "elevenlabs_model", "") or settings.ELEVENLABS_MODEL).strip()
        body: dict[str, Any] = {
            "text": clean,
            "model_id": model_id,
            "language_code": "fr",
            "voice_settings": {
                "stability": float(getattr(self.profile, "elevenlabs_stability", 0.5)),
                "similarity_boost": float(getattr(self.profile, "elevenlabs_similarity", 0.75)),
                "style": 0.0,
                "use_speaker_boost": bool(settings.ELEVENLABS_SPEAKER_BOOST),
                "speed": float(getattr(self.profile, "elevenlabs_speed", 1.0)),
            },
        }
        query = urllib.parse.urlencode({
            "output_format": "pcm_24000",
            # ElevenLabs still accepts this compatibility latency knob on the
            # streaming endpoint. It is configurable so AURA can disable it
            # immediately if the provider removes the deprecated parameter.
            "optimize_streaming_latency": int(settings.ELEVENLABS_OPTIMIZE_STREAMING_LATENCY),
        })
        url = (
            f"{settings.ELEVENLABS_API_BASE.rstrip('/')}/v1/text-to-speech/"
            f"{urllib.parse.quote(voice_id)}/stream?{query}"
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "xi-api-key": settings.ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/pcm",
            },
            method="POST",
        )

        import sounddevice as sd

        self._stop_event.clear()
        started = time.perf_counter()
        first_audio = 0.0
        bytes_played = 0
        try:
            with urllib.request.urlopen(req, timeout=float(settings.ELEVENLABS_TIMEOUT_SECONDS)) as response:
                with sd.RawOutputStream(samplerate=24000, channels=1, dtype="int16") as stream:
                    while not self._stop_event.is_set():
                        chunk = response.read(max(2048, int(settings.ELEVENLABS_STREAM_CHUNK_BYTES)))
                        if not chunk:
                            break
                        if len(chunk) % 2:
                            chunk = chunk[:-1]
                        if not chunk:
                            continue
                        stream.write(chunk)
                        bytes_played += len(chunk)
                        if first_audio <= 0.0:
                            first_audio = time.perf_counter() - started
                    try:
                        stream.stop()
                    except Exception:
                        pass
        except urllib.error.HTTPError as exc:
            detail = self._safe_http_error_detail(exc)
            logger.warning(
                "ElevenLabs TTS request failed http=%s detail=%s",
                exc.code, detail or "none",
            )
            # Never trust a cached quota snapshot after a provider billing error.
            if exc.code == 402:
                with type(self)._quota_lock:
                    type(self)._quota_cache = (0.0, {})
                suffix = f" · {detail}" if detail else ""
                raise SpeechSynthesisUnavailableError(
                    f"ElevenLabs refuse la génération (HTTP 402 · paiement/crédits requis){suffix}. Piper prend le relais."
                ) from exc
            if exc.code in {401, 403}:
                suffix = f" · {detail}" if detail else ""
                raise SpeechSynthesisUnavailableError(f"Clé ou permission ElevenLabs refusée (HTTP {exc.code}){suffix}") from exc
            if exc.code == 429:
                suffix = f" · {detail}" if detail else ""
                raise SpeechSynthesisUnavailableError(
                    f"ElevenLabs est limité temporairement (HTTP 429){suffix}. Piper prend le relais."
                ) from exc
            suffix = f" · {detail}" if detail else ""
            raise SpeechSynthesisUnavailableError(f"ElevenLabs HTTP {exc.code}{suffix}. Piper prend le relais.") from exc
        except SpeechSynthesisUnavailableError:
            raise
        except Exception as exc:
            raise SpeechSynthesisUnavailableError("Synthèse ElevenLabs indisponible.") from exc

        total = time.perf_counter() - started
        ttfa = first_audio if first_audio > 0 else total
        # Network synthesis and playback overlap. Keep the common metric shape:
        # synthesis=TTFA, playback=remaining elapsed wall time.
        playback = max(0.0, total - ttfa)
        logger.info(
            "ElevenLabs TTS voice=%s model=%s chars=%d ttfa=%.3fs total=%.3fs pcm_bytes=%d",
            getattr(self.profile, "elevenlabs_voice_name", "") or voice_id,
            model_id,
            len(clean),
            ttfa,
            total,
            bytes_played,
        )
        return PiperSynthesisMetrics(
            device="cloud",
            model_load_seconds=0.0,
            synthesis_seconds=ttfa,
            playback_seconds=playback,
            text_chars=len(clean),
            time_to_audio_seconds=ttfa,
            chunk_count=1,
            streaming=True,
        )
