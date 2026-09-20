"""Provider-independent local LLM access for AURA v0.6.4."""
from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Iterator
from urllib.parse import urlparse
from dataclasses import dataclass
from pathlib import Path

import requests

from config.settings import settings
from installed_model_policy import select_installed_models
from security.validators import SecurityValidationError, validate_service_url

logger = logging.getLogger("aura.llm")


def _decode_utf8_stream_line(raw_line) -> str:
    """Decode JSON/SSE transport as UTF-8, independently of HTTP charset guesses.

    Groq, Gemini and Ollama stream JSON over UTF-8. Relying on
    requests.iter_lines(decode_unicode=True) makes rendering depend on the
    response charset selected by requests/server headers and can turn French
    accents/punctuation into mojibake (for example ``é`` -> ``Ã©``).
    """
    if isinstance(raw_line, (bytes, bytearray, memoryview)):
        return bytes(raw_line).decode("utf-8", errors="replace")
    return str(raw_line or "")


@dataclass(frozen=True)
class LLMGenerationMetrics:
    total_seconds: float = 0.0
    load_seconds: float = 0.0
    prompt_eval_seconds: float = 0.0
    eval_seconds: float = 0.0
    prompt_tokens: int = 0
    output_tokens: int = 0
    tokens_per_second: float = 0.0
    keep_alive: str = ""
    num_ctx: int = 0
    num_predict: int = 0
    model: str = ""
    done_reason: str = ""


def _ns_to_seconds(value) -> float:
    try:
        return max(0.0, float(value or 0)) / 1_000_000_000.0
    except (TypeError, ValueError):
        return 0.0


class LLMProviderError(Exception):
    """Safe error raised when the configured local LLM provider is unavailable."""


class BaseLLMProvider:
    def generate(self, messages: list, **kwargs) -> str:
        raise NotImplementedError

    def generate_stream(self, messages: list, **kwargs) -> Iterator[str]:
        yield self.generate(messages, **kwargs)

    def warmup(self, **kwargs) -> None:
        return None

    def unload(self, **kwargs) -> bool:
        return False

    def running_model_info(self, **kwargs) -> dict | None:
        return None

    def model_available(self, model: str) -> bool:
        return False


class DisabledLocalProvider(BaseLLMProvider):
    """Compatibility provider used when local generative AI is disabled.

    It deliberately performs no Ollama network probes and allocates no model
    memory. Explicit local/private requests therefore fail closed with a clear
    message instead of silently leaking to a cloud provider.
    """

    def __init__(self, model: str):
        self.model = str(model or "local-disabled")
        self.last_metrics = LLMGenerationMetrics(model=self.model, done_reason="local-disabled")

    @staticmethod
    def _error() -> LLMProviderError:
        return LLMProviderError(
            "Le moteur IA local est désactivé sur cette installation. "
            "Cette demande exige le mode local ; active LOCAL_LLM_ENABLED=true pour utiliser Ollama."
        )

    def generate(self, messages: list, **kwargs) -> str:
        raise self._error()

    def generate_stream(self, messages: list, **kwargs) -> Iterator[str]:
        raise self._error()
        yield ""  # pragma: no cover - keeps Iterator semantics for type checkers

    def warmup(self, **kwargs) -> None:
        logger.info("Local LLM warmup skipped: LOCAL_LLM_ENABLED=false")

    def unload(self, **kwargs) -> bool:
        return True

    def running_model_info(self, **kwargs) -> dict | None:
        return None

    def model_available(self, model: str) -> bool:
        return False

    def model_processor_info(self, *, model: str | None = None) -> dict:
        return {
            "model": str(model or self.model),
            "size": 0,
            "size_vram": 0,
            "gpu_ratio": 0.0,
            "processor": "disabled",
        }

    def running_models(self) -> list[dict]:
        return []

    def running_model_query_ok(self) -> bool:
        return True

    def local_models(self, *, force: bool = False) -> tuple[str, ...]:
        return ()

    def local_model_info(self, model: str) -> dict | None:
        return None

    def local_model_catalog(self, *, force: bool = False) -> tuple[dict, ...]:
        return ()


class OllamaProvider(BaseLLMProvider):
    def __init__(self, host: str, model: str):
        try:
            self.host = validate_service_url(host, allow_remote=settings.ALLOW_REMOTE_LLM)
        except SecurityValidationError as exc:
            raise LLMProviderError(f"Configuration Ollama refusee par la securite : {exc}") from exc
        self.model = model
        self.session = requests.Session()
        self._request_lock = threading.RLock()
        self.last_metrics = LLMGenerationMetrics(model=model)
        self._last_ps_query_ok = False
        self._last_tags_query_ok = False
        self._model_cache: tuple[float, tuple[str, ...]] = (0.0, ())
        self._catalog_cache: tuple[float, tuple[dict, ...]] = (0.0, ())

    @staticmethod
    def _model_matches(requested: str, actual: str) -> bool:
        requested = (requested or "").strip().casefold()
        actual = (actual or "").strip().casefold()
        if not requested or not actual:
            return False
        if requested == actual:
            return True
        # A tagless request such as llama3.1 should match llama3.1:latest. A
        # tagged request must match its tag to avoid confusing 1B and 3B models.
        if ":" not in requested:
            return actual.split(":", 1)[0] == requested
        return False

    def _effective_keep_alive(self):
        if settings.RESOURCE_GUARDIAN_ENABLED:
            return settings.RESOURCE_LLM_KEEP_ALIVE_TEXT
        return settings.LLM_KEEP_ALIVE

    def _payload(
        self,
        messages: list,
        *,
        stream: bool,
        keep_alive=None,
        num_ctx: int | None = None,
        num_predict: int | None = None,
        model: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
    ) -> dict:
        effective_keep_alive = self._effective_keep_alive() if keep_alive is None else keep_alive
        effective_ctx = max(1024, int(settings.LLM_NUM_CTX if num_ctx is None else num_ctx))
        effective_predict = max(32, int(settings.LLM_NUM_PREDICT if num_predict is None else num_predict))
        effective_model = (model or self.model).strip()
        return {
            "model": effective_model,
            "messages": messages,
            "stream": bool(stream),
            "keep_alive": effective_keep_alive,
            "options": {
                "num_ctx": effective_ctx,
                "num_predict": effective_predict,
                "temperature": float(settings.LLM_TEMPERATURE if temperature is None else temperature),
                "top_p": float(settings.LLM_TOP_P if top_p is None else top_p),
            },
        }

    def _capture_metrics(self, data: dict, payload: dict) -> None:
        eval_seconds = _ns_to_seconds(data.get("eval_duration"))
        output_tokens = int(data.get("eval_count") or 0)
        tps = output_tokens / eval_seconds if output_tokens and eval_seconds > 0 else 0.0
        options = payload.get("options") or {}
        self.last_metrics = LLMGenerationMetrics(
            total_seconds=_ns_to_seconds(data.get("total_duration")),
            load_seconds=_ns_to_seconds(data.get("load_duration")),
            prompt_eval_seconds=_ns_to_seconds(data.get("prompt_eval_duration")),
            eval_seconds=eval_seconds,
            prompt_tokens=int(data.get("prompt_eval_count") or 0),
            output_tokens=output_tokens,
            tokens_per_second=tps,
            keep_alive=str(payload.get("keep_alive", "")),
            num_ctx=int(options.get("num_ctx") or 0),
            num_predict=int(options.get("num_predict") or 0),
            model=str(payload.get("model") or self.model),
            done_reason=str(data.get("done_reason") or ""),
        )

    @property
    def _timeout(self) -> tuple[float, float]:
        return (float(settings.LLM_CONNECT_TIMEOUT), float(settings.LLM_READ_TIMEOUT))

    @staticmethod
    def _raise_for_response(response) -> None:
        if 300 <= response.status_code < 400:
            raise LLMProviderError("Le moteur IA local a tente une redirection reseau non autorisee.")
        response.raise_for_status()

    def _safe_request_error(self, exc: Exception) -> LLMProviderError:
        if isinstance(exc, requests.exceptions.ConnectionError):
            return LLMProviderError("Je n'arrive pas à joindre le moteur Ollama local. Vérifie qu'Ollama est démarré.")
        if isinstance(exc, requests.exceptions.Timeout):
            return LLMProviderError("Le moteur IA local met trop de temps à répondre.")
        if isinstance(exc, requests.exceptions.HTTPError):
            logger.warning("Erreur HTTP Ollama: status=%s", getattr(exc.response, "status_code", "?"))
            if getattr(exc.response, "status_code", None) == 404:
                return LLMProviderError("Le modèle Ollama demandé n'est pas installé localement.")
            return LLMProviderError("Le moteur Ollama a renvoyé une erreur.")
        return LLMProviderError("La communication avec le moteur IA local a échoué.")

    def generate_stream(
        self,
        messages: list,
        *,
        keep_alive=None,
        num_ctx: int | None = None,
        num_predict: int | None = None,
        model: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
    ) -> Iterator[str]:
        url = f"{self.host}/api/chat"
        payload = self._payload(
            messages,
            stream=True,
            keep_alive=keep_alive,
            num_ctx=num_ctx,
            num_predict=num_predict,
            model=model,
            temperature=temperature,
            top_p=top_p,
        )
        try:
            with self._request_lock, self.session.post(
                url,
                json=payload,
                timeout=self._timeout,
                allow_redirects=False,
                stream=True,
            ) as response:
                self._raise_for_response(response)
                for raw_line in response.iter_lines(decode_unicode=False):
                    if not raw_line:
                        continue
                    line = _decode_utf8_stream_line(raw_line)
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Fragment Ollama JSON invalide ignore")
                        continue
                    message = data.get("message") or {}
                    chunk = message.get("content") or ""
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        self._capture_metrics(data, payload)
                        break
        except LLMProviderError:
            raise
        except requests.exceptions.RequestException as exc:
            raise self._safe_request_error(exc) from exc

    def generate(
        self,
        messages: list,
        *,
        keep_alive=None,
        num_ctx: int | None = None,
        num_predict: int | None = None,
        model: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        force_non_stream: bool = False,
        read_timeout: float | None = None,
    ) -> str:
        if settings.LLM_STREAM and not force_non_stream:
            content = "".join(
                self.generate_stream(
                    messages,
                    keep_alive=keep_alive,
                    num_ctx=num_ctx,
                    num_predict=num_predict,
                    model=model,
                    temperature=temperature,
                    top_p=top_p,
                )
            ).strip()
            if not content:
                raise LLMProviderError("Le moteur IA local a renvoyé une réponse vide.")
            return content

        url = f"{self.host}/api/chat"
        payload = self._payload(
            messages,
            stream=False,
            keep_alive=keep_alive,
            num_ctx=num_ctx,
            num_predict=num_predict,
            model=model,
            temperature=temperature,
            top_p=top_p,
        )
        try:
            with self._request_lock:
                timeout = self._timeout if read_timeout is None else (
                    float(settings.LLM_CONNECT_TIMEOUT), max(0.5, float(read_timeout))
                )
                response = self.session.post(
                    url,
                    json=payload,
                    timeout=timeout,
                    allow_redirects=False,
                )
                self._raise_for_response(response)
        except LLMProviderError:
            raise
        except requests.exceptions.RequestException as exc:
            raise self._safe_request_error(exc) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError("Le moteur IA local a renvoyé une réponse invalide.") from exc
        self._capture_metrics(data, payload)
        content = (data.get("message") or {}).get("content", "").strip()
        if not content:
            raise LLMProviderError("Le moteur IA local a renvoyé une réponse vide.")
        return content

    def unload(self, *, model: str | None = None) -> bool:
        """Ask Ollama to unload one model immediately (keep_alive=0)."""
        effective_model = (model or self.model).strip()
        url = f"{self.host}/api/chat"
        payload = {
            "model": effective_model,
            "messages": [],
            "stream": False,
            "keep_alive": 0,
        }
        try:
            with self._request_lock:
                response = self.session.post(
                    url,
                    json=payload,
                    timeout=self._timeout,
                    allow_redirects=False,
                )
                self._raise_for_response(response)
            logger.info("Modele Ollama decharge explicitement: %s", effective_model)
            return True
        except Exception as exc:
            logger.warning("Dechargement Ollama impossible model=%s: %s", effective_model, type(exc).__name__)
            return False

    def running_models(self) -> list[dict]:
        """Return /api/ps entries. Query success is tracked separately."""
        url = f"{self.host}/api/ps"
        try:
            with self._request_lock:
                response = self.session.get(url, timeout=self._timeout, allow_redirects=False)
                self._raise_for_response(response)
            data = response.json()
            self._last_ps_query_ok = True
            return [dict(item) for item in (data.get("models") or [])]
        except Exception:
            self._last_ps_query_ok = False
            logger.debug("Lecture /api/ps indisponible", exc_info=True)
            return []

    def running_model_info(self, *, model: str | None = None) -> dict | None:
        """Return one matching /api/ps entry, including size_vram when present."""
        wanted = (model or self.model).strip()
        for item in self.running_models():
            name = str(item.get("name") or item.get("model") or "")
            if self._model_matches(wanted, name):
                return item
        return None

    def model_processor_info(self, *, model: str | None = None) -> dict:
        """Summarize the actual CPU/GPU residency reported by Ollama /api/ps.

        ``size_vram`` is the authoritative API field exposed by Ollama for the
        amount of a running model resident in VRAM. This helper never starts a
        model and therefore is safe to call from ResourceGuardian.
        """
        info = self.running_model_info(model=model) or {}
        size = max(0, int(info.get("size", 0) or 0))
        size_vram = max(0, int(info.get("size_vram", 0) or 0))
        ratio = min(1.0, float(size_vram) / float(size)) if size > 0 else 0.0
        if size <= 0:
            processor = "not-loaded"
        elif size_vram <= 0:
            processor = "100% CPU"
        elif ratio >= 0.995:
            processor = "100% GPU"
        else:
            processor = f"{int(round(ratio * 100.0))}% GPU"
        return {
            "model": str(info.get("name") or info.get("model") or model or self.model),
            "size": size,
            "size_vram": size_vram,
            "gpu_ratio": ratio,
            "processor": processor,
        }

    def running_model_query_ok(self) -> bool:
        return bool(self._last_ps_query_ok)

    def local_model_catalog(self, *, force: bool = False) -> tuple[dict, ...]:
        """Return installed Ollama model metadata without loading any model."""
        now = time.monotonic()
        cached_at, cached = self._catalog_cache
        if not force and cached and now - cached_at < 30.0:
            self._last_tags_query_ok = True
            return tuple(dict(item) for item in cached)

        url = f"{self.host}/api/tags"
        # Startup adaptation must never block AURA for the full generation timeout.
        timeout = (
            min(1.25, float(settings.LLM_CONNECT_TIMEOUT)),
            min(1.50, float(settings.LLM_READ_TIMEOUT)),
        )
        try:
            with self._request_lock:
                response = self.session.get(url, timeout=timeout, allow_redirects=False)
                self._raise_for_response(response)
            data = response.json()
            items = tuple(
                dict(item) for item in (data.get("models") or [])
                if str(item.get("name") or item.get("model") or "").strip()
            )
            names = tuple(
                str(item.get("name") or item.get("model") or "").strip()
                for item in items
            )
            self._last_tags_query_ok = True
            self._catalog_cache = (now, items)
            self._model_cache = (now, names)
            return tuple(dict(item) for item in items)
        except Exception:
            self._last_tags_query_ok = False
            logger.debug("Catalogue /api/tags indisponible pour adaptation", exc_info=True)
            return ()


    def local_models(self, *, force: bool = False) -> tuple[str, ...]:
        """List locally installed Ollama models using /api/tags, cached briefly."""
        now = time.monotonic()
        cached_at, cached = self._model_cache
        if not force and cached and now - cached_at < 30.0:
            self._last_tags_query_ok = True
            return cached
        url = f"{self.host}/api/tags"
        try:
            with self._request_lock:
                response = self.session.get(url, timeout=self._timeout, allow_redirects=False)
                self._raise_for_response(response)
            data = response.json()
            names = tuple(
                str(item.get("name") or item.get("model") or "").strip()
                for item in (data.get("models") or [])
                if str(item.get("name") or item.get("model") or "").strip()
            )
            self._last_tags_query_ok = True
            self._model_cache = (now, names)
            return names
        except Exception:
            self._last_tags_query_ok = False
            logger.debug("Lecture /api/tags indisponible", exc_info=True)
            return ()

    def model_available(self, model: str) -> bool:
        model = (model or "").strip()
        return any(self._model_matches(model, item) for item in self.local_models())

    def local_model_info(self, model: str) -> dict | None:
        """Return read-only metadata for one installed model from /api/tags.

        Unlike /api/ps this does not load the model. The ``size`` field is the
        on-disk model size reported by Ollama and is useful for a conservative
        VRAM-fit preflight before a controlled GPU residency probe.
        """
        wanted = (model or "").strip()
        if not wanted:
            return None
        url = f"{self.host}/api/tags"
        try:
            with self._request_lock:
                response = self.session.get(url, timeout=self._timeout, allow_redirects=False)
                self._raise_for_response(response)
            data = response.json()
            self._last_tags_query_ok = True
            for item in (data.get("models") or []):
                name = str(item.get("name") or item.get("model") or "")
                if self._model_matches(wanted, name):
                    return dict(item)
        except Exception:
            self._last_tags_query_ok = False
            logger.debug("Lecture métadonnées /api/tags indisponible model=%s", wanted, exc_info=True)
        return None

    def warmup(
        self,
        *,
        model: str | None = None,
        keep_alive=None,
        num_ctx: int | None = None,
        force: bool = False,
    ) -> None:
        if not settings.LLM_PRELOAD and not force:
            return
        if settings.RESOURCE_GUARDIAN_ENABLED and not settings.RESOURCE_ALLOW_HEAVY_PRELOAD and not force:
            logger.info("Prechargement Ollama ignore par Resource Guardian")
            return
        effective_model = (model or self.model).strip()
        effective_keep_alive = self._effective_keep_alive() if keep_alive is None else keep_alive
        url = f"{self.host}/api/chat"
        payload = {
            "model": effective_model,
            "messages": [],
            "stream": False,
            "keep_alive": effective_keep_alive,
        }
        if num_ctx is not None:
            payload["options"] = {"num_ctx": max(1024, int(num_ctx))}
        try:
            with self._request_lock:
                response = self.session.post(url, json=payload, timeout=self._timeout, allow_redirects=False)
                self._raise_for_response(response)
            logger.info("Modele Ollama precharge: %s keep_alive=%s", effective_model, effective_keep_alive)
        except Exception as exc:
            logger.info("Prechauffage Ollama ignore model=%s: %s", effective_model, type(exc).__name__)
            if force:
                raise


class GroqProvider(BaseLLMProvider):
    """Minimal OpenAI-compatible Groq provider with rate-limit circuit breaker."""

    def __init__(self, base_url: str, api_key: str):
        parsed = urlparse(str(base_url or ""))
        if parsed.scheme != "https" or parsed.hostname != "api.groq.com":
            raise LLMProviderError("Configuration Groq refusée : seul https://api.groq.com est autorisé.")
        self.base_url = str(base_url).rstrip("/")
        self.api_key = str(api_key or "").strip()
        self.session = requests.Session()
        self._request_lock = threading.RLock()
        self._blocked_until = 0.0
        self.last_metrics = LLMGenerationMetrics()

    def available(self) -> bool:
        return bool(self.api_key and time.monotonic() >= self._blocked_until)

    @property
    def _timeout(self) -> tuple[float, float]:
        return (float(settings.GROQ_CONNECT_TIMEOUT), float(settings.GROQ_READ_TIMEOUT_SECONDS))

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(
        self, messages: list, *, stream: bool, model: str, num_predict: int | None,
        temperature: float | None, top_p: float | None,
    ) -> dict:
        return {
            "model": str(model or settings.GROQ_FAST_MODEL),
            "messages": messages,
            "stream": bool(stream),
            "max_completion_tokens": max(16, int(num_predict or settings.LLM_NUM_PREDICT)),
            "temperature": max(1e-8, float(settings.LLM_TEMPERATURE if temperature is None else temperature)),
            "top_p": float(settings.LLM_TOP_P if top_p is None else top_p),
        }

    def _raise_for_response(self, response) -> None:
        if response.status_code == 429:
            try:
                retry = max(1.0, float(response.headers.get("retry-after") or 5.0))
            except (TypeError, ValueError):
                retry = 5.0
            self._blocked_until = time.monotonic() + retry
            raise LLMProviderError(f"Groq est temporairement limité par quota (réessai dans environ {retry:.0f}s).")
        if response.status_code in {401, 403}:
            self._blocked_until = time.monotonic() + 300.0
            raise LLMProviderError("La clé Groq est absente, invalide ou non autorisée.")
        if response.status_code == 400:
            self._blocked_until = time.monotonic() + 60.0
            raise LLMProviderError("Groq a refusé la requête ou le modèle configuré.")
        if response.status_code >= 500:
            self._blocked_until = time.monotonic() + 3.0
            raise LLMProviderError("Groq est momentanément indisponible.")
        if 300 <= response.status_code < 400:
            raise LLMProviderError("Groq a tenté une redirection réseau refusée.")
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise LLMProviderError("Groq a renvoyé une erreur HTTP.") from exc

    def _capture_nonstream_metrics(self, data: dict, payload: dict, wall: float) -> None:
        usage = data.get("usage") or {}
        completion_time = float(usage.get("completion_time") or 0.0)
        prompt_time = float(usage.get("prompt_time") or 0.0)
        total_time = float(usage.get("total_time") or wall)
        output_tokens = int(usage.get("completion_tokens") or 0)
        tps = output_tokens / completion_time if output_tokens and completion_time > 0 else 0.0
        choices = data.get("choices") or []
        finish_reason = str((choices[0] if choices else {}).get("finish_reason") or "")
        self.last_metrics = LLMGenerationMetrics(
            total_seconds=max(0.0, total_time),
            load_seconds=0.0,
            prompt_eval_seconds=max(0.0, prompt_time),
            eval_seconds=max(0.0, completion_time),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=output_tokens,
            tokens_per_second=tps,
            keep_alive="remote",
            num_ctx=0,
            num_predict=int(payload.get("max_completion_tokens") or 0),
            model=str(data.get("model") or payload.get("model") or ""),
            done_reason=finish_reason,
        )

    def generate_stream(
        self, messages: list, *, keep_alive=None, num_ctx=None, num_predict=None, model=None,
        temperature=None, top_p=None, **_ignored,
    ) -> Iterator[str]:
        del keep_alive, num_ctx
        if not self.available():
            raise LLMProviderError("Groq n'est pas disponible pour le moment.")
        payload = self._payload(
            messages, stream=True, model=str(model or settings.GROQ_FAST_MODEL),
            num_predict=num_predict, temperature=temperature, top_p=top_p,
        )
        url = self.base_url + "/chat/completions"
        started = time.perf_counter()
        finish_reason = ""
        chars = 0
        try:
            with self._request_lock, self.session.post(
                url, headers=self._headers(), json=payload, timeout=self._timeout,
                allow_redirects=False, stream=True,
            ) as response:
                self._raise_for_response(response)
                for raw_line in response.iter_lines(decode_unicode=False):
                    if not raw_line:
                        continue
                    line = _decode_utf8_stream_line(raw_line).strip()
                    if not line.startswith("data:"):
                        continue
                    body = line[5:].strip()
                    if body == "[DONE]":
                        break
                    try:
                        data = json.loads(body)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0] or {}
                    delta = choice.get("delta") or {}
                    chunk = str(delta.get("content") or "")
                    if chunk:
                        chars += len(chunk)
                        yield chunk
                    if choice.get("finish_reason"):
                        finish_reason = str(choice.get("finish_reason"))
        except LLMProviderError:
            raise
        except requests.exceptions.Timeout as exc:
            raise LLMProviderError("Groq met trop de temps à répondre.") from exc
        except requests.exceptions.RequestException as exc:
            raise LLMProviderError("La connexion à Groq a échoué.") from exc
        wall = time.perf_counter() - started
        self.last_metrics = LLMGenerationMetrics(
            total_seconds=wall, eval_seconds=wall, prompt_tokens=0, output_tokens=0,
            tokens_per_second=0.0, keep_alive="remote", num_ctx=0,
            num_predict=int(payload.get("max_completion_tokens") or 0),
            model=str(payload.get("model") or ""), done_reason=finish_reason,
        )
        logger.info("Groq stream complete model=%s latency=%.3fs chars=%d reason=%s", payload["model"], wall, chars, finish_reason or "?")

    def generate(
        self, messages: list, *, keep_alive=None, num_ctx=None, num_predict=None, model=None,
        temperature=None, top_p=None, force_non_stream=False, read_timeout=None, **_ignored,
    ) -> str:
        del keep_alive, num_ctx, force_non_stream
        if not self.available():
            raise LLMProviderError("Groq n'est pas disponible pour le moment.")
        payload = self._payload(
            messages, stream=False, model=str(model or settings.GROQ_FAST_MODEL),
            num_predict=num_predict, temperature=temperature, top_p=top_p,
        )
        url = self.base_url + "/chat/completions"
        timeout = (
            float(settings.GROQ_CONNECT_TIMEOUT),
            max(0.5, float(settings.GROQ_READ_TIMEOUT_SECONDS if read_timeout is None else read_timeout)),
        )
        started = time.perf_counter()
        try:
            with self._request_lock:
                response = self.session.post(
                    url, headers=self._headers(), json=payload, timeout=timeout, allow_redirects=False,
                )
                self._raise_for_response(response)
        except LLMProviderError:
            raise
        except requests.exceptions.Timeout as exc:
            raise LLMProviderError("Groq met trop de temps à répondre.") from exc
        except requests.exceptions.RequestException as exc:
            raise LLMProviderError("La connexion à Groq a échoué.") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError("Groq a renvoyé une réponse invalide.") from exc
        self._capture_nonstream_metrics(data, payload, time.perf_counter() - started)
        choices = data.get("choices") or []
        content = str((((choices[0] if choices else {}).get("message") or {}).get("content")) or "").strip()
        if not content:
            raise LLMProviderError("Groq a renvoyé une réponse vide.")
        logger.info(
            "Groq completion model=%s latency=%.3fs tokens=%d tps=%.1f",
            self.last_metrics.model, self.last_metrics.total_seconds,
            self.last_metrics.output_tokens, self.last_metrics.tokens_per_second,
        )
        return content


class GeminiProvider(BaseLLMProvider):
    """Minimal Gemini REST provider used as AURA's secondary cloud brain.

    It supports normal streamed text generation plus native PDF attachment
    upload through Google's resumable Files API. API keys are sent only in
    request authentication and are never logged.
    """

    def __init__(self, base_url: str, upload_base_url: str, api_key: str):
        parsed = urlparse(str(base_url or ""))
        upload_parsed = urlparse(str(upload_base_url or ""))
        allowed = "generativelanguage.googleapis.com"
        if parsed.scheme != "https" or parsed.hostname != allowed:
            raise LLMProviderError("Configuration Gemini refusée : hôte API non autorisé.")
        if upload_parsed.scheme != "https" or upload_parsed.hostname != allowed:
            raise LLMProviderError("Configuration Gemini Files refusée : hôte API non autorisé.")
        self.base_url = str(base_url).rstrip("/")
        self.upload_base_url = str(upload_base_url).rstrip("/")
        self.api_key = str(api_key or "").strip()
        self.session = requests.Session()
        self._request_lock = threading.RLock()
        self._blocked_until = 0.0
        self.last_metrics = LLMGenerationMetrics()

    def available(self) -> bool:
        return bool(self.api_key and time.monotonic() >= self._blocked_until)

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

    @staticmethod
    def _coalesce_contents(contents: list[dict]) -> list[dict]:
        result: list[dict] = []
        for item in contents:
            role = str(item.get("role") or "user")
            parts = list(item.get("parts") or [])
            if result and result[-1].get("role") == role:
                result[-1].setdefault("parts", []).extend(parts)
            else:
                result.append({"role": role, "parts": parts})
        return result

    def _convert_messages(self, messages: list) -> tuple[list[dict], str]:
        system_parts: list[str] = []
        contents: list[dict] = []
        for raw in list(messages or []):
            role = str((raw or {}).get("role") or "user").casefold()
            text = str((raw or {}).get("content") or "")
            if not text:
                continue
            if role == "system":
                system_parts.append(text)
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": text}]})
        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Réponds brièvement."}]}]
        return self._coalesce_contents(contents), "\n\n".join(system_parts).strip()

    def _payload(
        self,
        messages: list,
        *,
        model: str,
        num_predict: int | None,
        temperature: float | None,
        top_p: float | None,
        file_uri: str = "",
        file_mime: str = "",
        thinking_level: str | None = None,
    ) -> dict:
        contents, system_text = self._convert_messages(messages)
        if file_uri:
            contents[-1].setdefault("parts", []).append({
                "file_data": {"mime_type": str(file_mime or "application/pdf"), "file_uri": str(file_uri)}
            })
        effective_model = str(model or "").casefold()
        generation_config = {
            "maxOutputTokens": max(16, int(num_predict or settings.LLM_NUM_PREDICT)),
        }
        # Patch 26.8.5: Gemini 3.x uses dynamic thinking by default. If we only
        # provide a small maxOutputTokens ceiling, internal reasoning can consume
        # almost all of it and leave only a handful of visible answer tokens.
        # The document fast lane passes thinking_level=low to keep analysis
        # capable while preserving Gemini-like latency. For Gemini 3.x we also
        # keep Google's default sampling values instead of overriding them.
        normalized_thinking = str(thinking_level or "").strip().casefold()
        if effective_model.startswith("gemini-3"):
            if normalized_thinking in {"minimal", "low", "medium", "high"}:
                generation_config["thinkingConfig"] = {"thinkingLevel": normalized_thinking}
        else:
            generation_config["temperature"] = max(
                1e-8, float(settings.LLM_TEMPERATURE if temperature is None else temperature)
            )
            generation_config["topP"] = float(settings.LLM_TOP_P if top_p is None else top_p)
        payload = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        return payload

    def _raise_for_response(self, response) -> None:
        code = int(getattr(response, "status_code", 0) or 0)
        if code == 429:
            self._blocked_until = time.monotonic() + 10.0
            raise LLMProviderError("Gemini est temporairement limité par quota.")
        if code in {401, 403}:
            self._blocked_until = time.monotonic() + 300.0
            raise LLMProviderError("La clé Gemini est absente, invalide ou non autorisée.")
        if code == 400:
            raise LLMProviderError("Gemini a refusé la requête ou son contenu.")
        if code == 404:
            raise LLMProviderError("Le modèle Gemini configuré n'est pas disponible.")
        if code >= 500:
            self._blocked_until = time.monotonic() + 3.0
            raise LLMProviderError("Gemini est momentanément indisponible.")
        if 300 <= code < 400:
            raise LLMProviderError("Gemini a tenté une redirection réseau refusée.")
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise LLMProviderError("Gemini a renvoyé une erreur HTTP.") from exc

    @staticmethod
    def _response_text(data: dict) -> tuple[str, str]:
        candidates = list((data or {}).get("candidates") or [])
        if not candidates:
            return "", ""
        first = candidates[0] or {}
        content = first.get("content") or {}
        parts = content.get("parts") or []
        text = "".join(str((part or {}).get("text") or "") for part in parts)
        return text, str(first.get("finishReason") or first.get("finish_reason") or "")

    def _capture_metrics(self, data: dict, *, model: str, wall: float, num_predict: int) -> None:
        usage = (data or {}).get("usageMetadata") or (data or {}).get("usage_metadata") or {}
        prompt_tokens = int(usage.get("promptTokenCount") or usage.get("prompt_token_count") or 0)
        output_tokens = int(usage.get("candidatesTokenCount") or usage.get("candidates_token_count") or 0)
        thought_tokens = int(usage.get("thoughtsTokenCount") or usage.get("thoughts_token_count") or 0)
        _text, finish = self._response_text(data or {})
        if thought_tokens:
            logger.info("Gemini usage thoughts=%d visible_output=%d prompt=%d", thought_tokens, output_tokens, prompt_tokens)
        self.last_metrics = LLMGenerationMetrics(
            total_seconds=max(0.0, float(wall)), eval_seconds=max(0.0, float(wall)),
            prompt_tokens=prompt_tokens, output_tokens=output_tokens,
            tokens_per_second=(output_tokens / wall if output_tokens and wall > 0 else 0.0),
            keep_alive="remote", num_ctx=0, num_predict=int(num_predict),
            model=str(model), done_reason=finish,
        )

    def _upload_file(self, path: str, mime_type: str) -> tuple[str, str]:
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            raise LLMProviderError("Le document joint n'existe plus sur le disque.")
        size = int(p.stat().st_size)
        if size <= 0:
            raise LLMProviderError("Le document joint est vide.")
        start_url = self.upload_base_url + "/files"
        headers = {
            "x-goog-api-key": self.api_key,
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(size),
            "X-Goog-Upload-Header-Content-Type": str(mime_type or "application/pdf"),
            "Content-Type": "application/json",
        }
        try:
            start = self.session.post(
                start_url,
                headers=headers,
                json={"file": {"display_name": p.name}},
                timeout=(float(settings.GEMINI_CONNECT_TIMEOUT), float(settings.GEMINI_FILE_UPLOAD_TIMEOUT_SECONDS)),
                allow_redirects=False,
            )
            self._raise_for_response(start)
            upload_url = str(start.headers.get("X-Goog-Upload-URL") or "").strip()
            if not upload_url:
                raise LLMProviderError("Gemini n'a pas fourni d'URL d'envoi pour le document.")
            parsed = urlparse(upload_url)
            if parsed.scheme != "https" or not str(parsed.hostname or "").endswith("googleapis.com"):
                raise LLMProviderError("Gemini a renvoyé une URL d'envoi non autorisée.")
            with p.open("rb") as handle:
                uploaded = self.session.post(
                    upload_url,
                    headers={
                        "Content-Length": str(size),
                        "X-Goog-Upload-Offset": "0",
                        "X-Goog-Upload-Command": "upload, finalize",
                    },
                    data=handle,
                    timeout=(float(settings.GEMINI_CONNECT_TIMEOUT), float(settings.GEMINI_FILE_UPLOAD_TIMEOUT_SECONDS)),
                    allow_redirects=False,
                )
            self._raise_for_response(uploaded)
            info = uploaded.json()
        except LLMProviderError:
            raise
        except (requests.exceptions.RequestException, ValueError, OSError) as exc:
            raise LLMProviderError("L'envoi du document vers Gemini a échoué.") from exc
        file_info = (info or {}).get("file") or {}
        uri = str(file_info.get("uri") or "").strip()
        name = str(file_info.get("name") or "").strip()
        if not uri:
            raise LLMProviderError("Gemini n'a pas renvoyé de référence exploitable pour le document.")
        logger.info("Gemini native document upload ready name=%r bytes=%d mime=%s", p.name, size, mime_type)
        return uri, name

    def _delete_uploaded_file(self, file_name: str) -> None:
        name = str(file_name or "").strip().lstrip("/")
        if not name:
            return
        try:
            self.session.delete(
                self.base_url + "/" + name,
                headers={"x-goog-api-key": self.api_key},
                timeout=(float(settings.GEMINI_CONNECT_TIMEOUT), 8.0),
                allow_redirects=False,
            )
            logger.info("Gemini temporary document reference cleanup requested")
        except Exception:
            logger.info("Gemini temporary document cleanup skipped", exc_info=True)

    def generate_stream(
        self, messages: list, *, keep_alive=None, num_ctx=None, num_predict=None, model=None,
        temperature=None, top_p=None, attachment_path=None, attachment_mime=None,
        thinking_level=None, **_ignored,
    ) -> Iterator[str]:
        del keep_alive, num_ctx
        if not self.available():
            raise LLMProviderError("Gemini n'est pas disponible pour le moment.")
        effective_model = str(model or settings.GEMINI_FAST_MODEL)
        file_uri = ""
        file_name = ""
        if attachment_path:
            file_uri, file_name = self._upload_file(str(attachment_path), str(attachment_mime or "application/pdf"))
        payload = self._payload(
            messages, model=effective_model, num_predict=num_predict,
            temperature=temperature, top_p=top_p, file_uri=file_uri, file_mime=str(attachment_mime or ""),
            thinking_level=thinking_level,
        )
        url = f"{self.base_url}/models/{effective_model}:streamGenerateContent"
        started = time.perf_counter()
        chars = 0
        finish_reason = ""
        last_data: dict = {}
        buffered_chunks: list[str] = []
        # Document calls are buffered until Gemini confirms a complete answer.
        # This prevents a 30-60 character MAX_TOKENS fragment from being shown
        # and spoken as if it were a valid finished analysis.
        protected_document_stream = bool(str(thinking_level or "").strip())
        try:
            with self._request_lock, self.session.post(
                url,
                params={"alt": "sse"},
                headers=self._headers(),
                json=payload,
                timeout=(float(settings.GEMINI_CONNECT_TIMEOUT), float(settings.GEMINI_READ_TIMEOUT_SECONDS)),
                allow_redirects=False,
                stream=True,
            ) as response:
                self._raise_for_response(response)
                for raw_line in response.iter_lines(decode_unicode=False):
                    if not raw_line:
                        continue
                    line = _decode_utf8_stream_line(raw_line).strip()
                    if not line.startswith("data:"):
                        continue
                    body = line[5:].strip()
                    try:
                        data = json.loads(body)
                    except json.JSONDecodeError:
                        continue
                    last_data = data
                    chunk, reason = self._response_text(data)
                    if chunk:
                        chars += len(chunk)
                        if protected_document_stream:
                            buffered_chunks.append(chunk)
                        else:
                            yield chunk
                    if reason:
                        finish_reason = reason

            # Safety net: if Gemini still ends on MAX_TOKENS with a tiny visible
            # answer, retry once with a larger ceiling and minimal thinking.
            # The first fragment has not been emitted, so the UI never sees a
            # duplicated/truncated response.
            if protected_document_stream and finish_reason.upper() == "MAX_TOKENS" and chars < 400:
                first_usage = (last_data or {}).get("usageMetadata") or {}
                first_thoughts = int(first_usage.get("thoughtsTokenCount") or 0)
                logger.warning(
                    "Gemini document short MAX_TOKENS recovery chars=%d thoughts=%d configured=%d",
                    chars, first_thoughts, int(num_predict or settings.LLM_NUM_PREDICT),
                )
                retry_payload = dict(payload)
                retry_generation = dict(payload.get("generationConfig") or {})
                retry_generation["maxOutputTokens"] = max(4096, int(num_predict or settings.LLM_NUM_PREDICT) * 2)
                if effective_model.casefold().startswith("gemini-3"):
                    retry_generation["thinkingConfig"] = {"thinkingLevel": "minimal"}
                retry_payload["generationConfig"] = retry_generation
                retry_started = time.perf_counter()
                with self._request_lock:
                    retry_response = self.session.post(
                        f"{self.base_url}/models/{effective_model}:generateContent",
                        headers=self._headers(),
                        json=retry_payload,
                        timeout=(float(settings.GEMINI_CONNECT_TIMEOUT), float(settings.GEMINI_READ_TIMEOUT_SECONDS)),
                        allow_redirects=False,
                    )
                    self._raise_for_response(retry_response)
                retry_data = retry_response.json()
                retry_text, retry_reason = self._response_text(retry_data)
                if retry_text.strip():
                    buffered_chunks = [retry_text]
                    chars = len(retry_text)
                    last_data = retry_data
                    finish_reason = retry_reason
                    logger.info(
                        "Gemini document recovery complete latency=%.3fs chars=%d reason=%s",
                        time.perf_counter() - retry_started, chars, retry_reason or "?",
                    )

            if protected_document_stream:
                for chunk in buffered_chunks:
                    if chunk:
                        yield chunk
        except LLMProviderError:
            raise
        except requests.exceptions.Timeout as exc:
            raise LLMProviderError("Gemini met trop de temps à répondre.") from exc
        except requests.exceptions.RequestException as exc:
            raise LLMProviderError("La connexion à Gemini a échoué.") from exc
        finally:
            if file_name:
                self._delete_uploaded_file(file_name)
        wall = time.perf_counter() - started
        usage = (last_data or {}).get("usageMetadata") or {}
        output_tokens = int(usage.get("candidatesTokenCount") or 0)
        prompt_tokens = int(usage.get("promptTokenCount") or 0)
        thought_tokens = int(usage.get("thoughtsTokenCount") or 0)
        if thought_tokens:
            logger.info("Gemini usage thoughts=%d visible_output=%d prompt=%d", thought_tokens, output_tokens, prompt_tokens)
        self.last_metrics = LLMGenerationMetrics(
            total_seconds=wall, eval_seconds=wall, prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            tokens_per_second=(output_tokens / wall if output_tokens and wall > 0 else 0.0),
            keep_alive="remote", num_ctx=0, num_predict=int(num_predict or settings.LLM_NUM_PREDICT),
            model=effective_model, done_reason=finish_reason,
        )
        logger.info("Gemini stream complete model=%s latency=%.3fs chars=%d reason=%s", effective_model, wall, chars, finish_reason or "?")

    def generate(
        self, messages: list, *, keep_alive=None, num_ctx=None, num_predict=None, model=None,
        temperature=None, top_p=None, force_non_stream=False, read_timeout=None,
        attachment_path=None, attachment_mime=None, thinking_level=None, **_ignored,
    ) -> str:
        del keep_alive, num_ctx, force_non_stream
        if not self.available():
            raise LLMProviderError("Gemini n'est pas disponible pour le moment.")
        effective_model = str(model or settings.GEMINI_FAST_MODEL)
        file_uri = ""
        file_name = ""
        if attachment_path:
            file_uri, file_name = self._upload_file(str(attachment_path), str(attachment_mime or "application/pdf"))
        payload = self._payload(
            messages, model=effective_model, num_predict=num_predict,
            temperature=temperature, top_p=top_p, file_uri=file_uri, file_mime=str(attachment_mime or ""),
            thinking_level=thinking_level,
        )
        url = f"{self.base_url}/models/{effective_model}:generateContent"
        timeout = (
            float(settings.GEMINI_CONNECT_TIMEOUT),
            max(0.5, float(settings.GEMINI_READ_TIMEOUT_SECONDS if read_timeout is None else read_timeout)),
        )
        started = time.perf_counter()
        try:
            with self._request_lock:
                response = self.session.post(
                    url, headers=self._headers(), json=payload, timeout=timeout, allow_redirects=False,
                )
                self._raise_for_response(response)
            data = response.json()
        except LLMProviderError:
            raise
        except requests.exceptions.Timeout as exc:
            raise LLMProviderError("Gemini met trop de temps à répondre.") from exc
        except requests.exceptions.RequestException as exc:
            raise LLMProviderError("La connexion à Gemini a échoué.") from exc
        except ValueError as exc:
            raise LLMProviderError("Gemini a renvoyé une réponse invalide.") from exc
        finally:
            if file_name:
                self._delete_uploaded_file(file_name)
        wall = time.perf_counter() - started
        self._capture_metrics(data, model=effective_model, wall=wall, num_predict=int(num_predict or settings.LLM_NUM_PREDICT))
        content, _finish = self._response_text(data)
        content = content.strip()
        if not content:
            raise LLMProviderError("Gemini a renvoyé une réponse vide.")
        logger.info("Gemini completion model=%s latency=%.3fs chars=%d", effective_model, wall, len(content))
        return content


class LLMManager:
    def __init__(self):
        provider_name = settings.LOCAL_LLM_PROVIDER.lower().strip()
        local_enabled = bool(getattr(settings, "LOCAL_LLM_ENABLED", False))
        self.adaptive_model_selection = {
            "schema": "aura.installed-model-policy.v1",
            "patch": "P0.8.5.3.2",
            "active": False,
            "reason": "local-llm-disabled",
            "requested_text": settings.LLM_TEXT_MODEL,
            "requested_voice": settings.LLM_VOICE_MODEL,
            "selected_text": settings.LLM_TEXT_MODEL,
            "selected_voice": settings.LLM_VOICE_MODEL,
            "changed": False,
            "download_allowed": False,
        }
        if local_enabled:
            if provider_name != "ollama":
                raise LLMProviderError(f"Fournisseur LLM local non supporté : '{provider_name}'.")
            self.local_provider = OllamaProvider(host=settings.OLLAMA_HOST, model=settings.LLM_TEXT_MODEL)
            if bool(getattr(settings, "ADAPTIVE_MODEL_SWITCH_ENABLED", False)):
                catalog = self.local_provider.local_model_catalog(force=True)
                if catalog:
                    selection = select_installed_models(
                        profile_code=str(getattr(settings, "ADAPTIVE_PROFILE_CODE", "P2")),
                        catalog=catalog,
                        requested_text=settings.LLM_TEXT_MODEL,
                        requested_voice=settings.LLM_VOICE_MODEL,
                        explicit_text=bool(getattr(settings, "LLM_TEXT_MODEL_EXPLICIT", False)),
                        explicit_voice=bool(getattr(settings, "LLM_VOICE_MODEL_EXPLICIT", False)),
                    )
                    selection["active"] = True
                    selection["reason"] = "installed-catalog-applied"
                    self.adaptive_model_selection = selection
                    settings.LLM_TEXT_MODEL = str(selection["selected_text"] or settings.LLM_TEXT_MODEL)
                    settings.LLM_VOICE_MODEL = str(selection["selected_voice"] or settings.LLM_VOICE_MODEL)
                    if not bool(getattr(settings, "AGENT_ROUTER_MODEL_EXPLICIT", False)):
                        settings.AGENT_ROUTER_MODEL = settings.LLM_VOICE_MODEL
                    self.local_provider.model = settings.LLM_TEXT_MODEL
                    logger.info(
                        "Adaptive installed-model policy profile=%s text=%s voice=%s changed=%s catalog=%d",
                        getattr(settings, "ADAPTIVE_PROFILE_CODE", "P2"),
                        settings.LLM_TEXT_MODEL, settings.LLM_VOICE_MODEL,
                        bool(selection.get("changed")), int(selection.get("catalog_count") or 0),
                    )
                else:
                    self.adaptive_model_selection = {
                        **self.adaptive_model_selection,
                        "active": False,
                        "reason": "ollama-catalog-unavailable",
                    }
        else:
            self.local_provider = DisabledLocalProvider(settings.LLM_TEXT_MODEL)
        self.provider = self.local_provider  # compatibility for ResourceGuardian/tests
        self.groq_provider = None
        self.gemini_provider = None
        if settings.GROQ_ENABLED and settings.GROQ_API_KEY:
            try:
                self.groq_provider = GroqProvider(settings.GROQ_BASE_URL, settings.GROQ_API_KEY)
            except LLMProviderError:
                logger.warning("Groq désactivé par validation de configuration", exc_info=True)
        if settings.GEMINI_ENABLED and settings.GEMINI_API_KEY:
            try:
                self.gemini_provider = GeminiProvider(
                    settings.GEMINI_BASE_URL, settings.GEMINI_UPLOAD_BASE_URL, settings.GEMINI_API_KEY
                )
            except LLMProviderError:
                logger.warning("Gemini désactivé par validation de configuration", exc_info=True)
        self._last_provider_name = "local"

        local_backend_label = provider_name if local_enabled else "disabled"
        local_text_label = settings.LLM_TEXT_MODEL if local_enabled else "-"
        local_voice_label = settings.LLM_VOICE_MODEL if (local_enabled and settings.DUAL_BRAIN_ENABLED) else "-"
        logger.info(
            "LLMManager initialise runtime=%s local_enabled=%s local_backend=%s local_text=%s local_voice=%s dual=%s groq=%s gemini=%s",
            settings.AURA_RUNTIME_MODE, local_enabled, local_backend_label, local_text_label, local_voice_label,
            bool(settings.DUAL_BRAIN_ENABLED and local_enabled), bool(self.groq_provider), bool(self.gemini_provider),
        )

    def remote_available(self, provider: str | None = None) -> bool:
        name = str(provider or "").strip().casefold()
        groq = bool(self.groq_provider is not None and self.groq_provider.available())
        gemini = bool(self.gemini_provider is not None and self.gemini_provider.available())
        if name == "groq":
            return groq
        if name == "gemini":
            return gemini
        return bool(groq or gemini)

    def _select_provider(self, requested: str | None):
        name = str(requested or "auto").strip().lower()
        if name == "groq":
            if not self.remote_available("groq"):
                raise LLMProviderError("Groq n'est pas configuré ou est temporairement indisponible.")
            self._last_provider_name = "groq"
            return self.groq_provider
        if name == "gemini":
            if not self.remote_available("gemini"):
                raise LLMProviderError("Gemini n'est pas configuré ou est temporairement indisponible.")
            self._last_provider_name = "gemini"
            return self.gemini_provider
        self._last_provider_name = "local"
        return self.local_provider

    def generate(self, messages: list, **kwargs) -> str:
        requested = kwargs.pop("provider", "local")
        provider = self._select_provider(requested)
        return provider.generate(messages, **kwargs)

    def generate_stream(self, messages: list, **kwargs) -> Iterator[str]:
        requested = kwargs.pop("provider", "local")
        provider = self._select_provider(requested)
        if settings.LLM_STREAM:
            yield from provider.generate_stream(messages, **kwargs)
        else:
            yield provider.generate(messages, **kwargs)

    @property
    def last_metrics(self) -> LLMGenerationMetrics:
        if self._last_provider_name == "groq":
            provider = self.groq_provider
        elif self._last_provider_name == "gemini":
            provider = self.gemini_provider
        else:
            provider = self.local_provider
        return getattr(provider, "last_metrics", LLMGenerationMetrics())

    @property
    def last_provider_name(self) -> str:
        return self._last_provider_name

    def warmup(self, **kwargs) -> None:
        self.local_provider.warmup(**kwargs)

    def unload(self, *, model: str | None = None) -> bool:
        return bool(self.local_provider.unload(model=model))

    def running_model_info(self, *, model: str | None = None) -> dict | None:
        return self.local_provider.running_model_info(model=model)

    def model_processor_info(self, *, model: str | None = None) -> dict:
        return self.local_provider.model_processor_info(model=model)

    def running_models(self) -> list[dict]:
        return self.local_provider.running_models()

    def running_model_query_ok(self) -> bool:
        return self.local_provider.running_model_query_ok()

    def model_available(self, model: str) -> bool:
        return self.local_provider.model_available(model)

    def local_models(self, *, force: bool = False) -> tuple[str, ...]:
        return self.local_provider.local_models(force=force)

    def local_model_catalog(self, *, force: bool = False) -> tuple[dict, ...]:
        return self.local_provider.local_model_catalog(force=force)

    def local_model_info(self, model: str) -> dict | None:
        return self.local_provider.local_model_info(model)

