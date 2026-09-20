"""AURA ADF-H R7.2.6 — AFG Live Adapter Pack 1.

AURA-owned clean-room ProviderAdapter implementations for Groq, Gemini and
Ollama. These adapters do not use ai.llm_manager and never own retry/failover;
those remain AFG responsibilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
import json
import os
import threading
import time
import urllib.parse
import uuid

import requests

from config.settings import settings
from runtime.aura_fabric_model_catalog import CatalogEntry
from runtime.aura_fabric_protocols import CanonicalMessage, CanonicalRequest
from runtime.aura_fabric_provider_adapter import AdapterResult, ProviderAdapter
from runtime.aura_fabric_provider_registry import ProviderRegistry, load_default_registry
from security.validators import SecurityValidationError, validate_service_url

PACK_ID = "ADF-H-R7.2.6-AFG-LIVE-ADAPTER-PACK-1"
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
_DEFAULT_TIMEOUT = 45.0


class AFGProviderHTTPError(RuntimeError):
    def __init__(self, provider_id: str, status_code: int, message: str, *, retry_after: float | None = None):
        self.provider_id = str(provider_id)
        self.status_code = int(status_code)
        self.retry_after = retry_after
        super().__init__(f"{self.provider_id} HTTP {self.status_code}: {str(message)[:300]}")


def _setting(*names: str, default: Any = None) -> Any:
    for name in names:
        if hasattr(settings, name):
            value = getattr(settings, name)
            if value not in (None, ""):
                return value
    return default


def _bool_setting(*names: str, default: bool = False) -> bool:
    value = _setting(*names, default=default)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _provider_seed_item(provider_id: str, registry: ProviderRegistry | None = None) -> dict[str, Any]:
    registry = registry or load_default_registry()
    try:
        return registry.get(provider_id)
    except Exception:
        return {}


def _credential_env_names(provider_id: str, registry: ProviderRegistry | None = None) -> tuple[str, ...]:
    item = _provider_seed_item(provider_id, registry)
    return tuple(str(x) for x in (item.get("credential_env_names") or ()) if str(x).strip())


def _first_env(names: tuple[str, ...]) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return ""


def _retry_after(response: Any) -> float | None:
    try:
        raw = response.headers.get("Retry-After")
    except Exception:
        raw = None
    try:
        return float(raw) if raw not in (None, "") else None
    except Exception:
        return None


def _response_json(provider_id: str, response: Any) -> dict[str, Any]:
    status = int(getattr(response, "status_code", 0) or 0)
    if status < 200 or status >= 300:
        detail = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                err = payload.get("error")
                if isinstance(err, dict):
                    detail = str(err.get("message") or err.get("status") or "")
                elif err:
                    detail = str(err)
        except Exception:
            pass
        if not detail:
            detail = str(getattr(response, "text", "") or "provider request failed")
        raise AFGProviderHTTPError(provider_id, status or 502, detail, retry_after=_retry_after(response))
    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"{provider_id} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{provider_id} returned non-object JSON")
    return payload


def _json_obj(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _json_string(value: Any) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if raw:
            try:
                parsed = json.loads(raw)
            except Exception:
                return raw
            return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
        return "{}"
    try:
        return json.dumps(value if value is not None else {}, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return "{}"


def _text_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        for key in ("text", "content", "output", "result"):
            if key in value and isinstance(value[key], (str, int, float, bool)):
                return str(value[key])
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        chunks: list[str] = []
        for item in value:
            if isinstance(item, dict) and str(item.get("type") or "").casefold() in {"text", "input_text", "output_text"}:
                chunks.append(str(item.get("text") or ""))
            else:
                chunks.append(_text_content(item))
        return "\n".join(x for x in chunks if x)
    return str(value)


def _system_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(_text_content(x) for x in value if _text_content(x))
    return _text_content(value)


def _call_name_lookup(messages: tuple[CanonicalMessage, ...]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for message in messages:
        for raw in tuple(getattr(message, "tool_calls", ()) or ()):
            if not isinstance(raw, dict):
                continue
            call_id = str(raw.get("id") or raw.get("call_id") or "")
            name = str(raw.get("name") or "")
            if call_id and name:
                lookup[call_id] = name
    return lookup


def _canonical_tools_to_openai(tools: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    out = []
    for tool in tools:
        if not isinstance(tool, dict) or str(tool.get("type") or "function") != "function":
            continue
        name = str(tool.get("name") or "").strip()
        if not name:
            continue
        parameters = tool.get("parameters")
        if not isinstance(parameters, dict):
            parameters = {}
        out.append({
            "type": "function",
            "function": {
                "name": name,
                "description": str(tool.get("description") or ""),
                "parameters": dict(parameters),
            },
        })
    return out


def _canonical_tool_choice_to_openai(choice: Any) -> Any:
    if choice is None or isinstance(choice, str):
        return choice
    if isinstance(choice, dict) and choice.get("type") == "function" and choice.get("name"):
        return {"type": "function", "function": {"name": str(choice["name"])}}
    return choice


def _openai_messages(request: CanonicalRequest) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    has_system = any(m.role in {"system", "developer"} for m in request.messages)
    if request.system and not has_system:
        messages.append({"role": "system", "content": _system_text(request.system)})
    for message in request.messages:
        role = "system" if message.role == "developer" else message.role
        item: dict[str, Any] = {
            "role": role,
            "content": _text_content(message.content) if message.content is not None else None,
        }
        if role == "assistant" and message.tool_calls:
            item["tool_calls"] = []
            for raw in message.tool_calls:
                item["tool_calls"].append({
                    "id": str(raw.get("id") or raw.get("call_id") or f"call_{uuid.uuid4().hex[:16]}"),
                    "type": "function",
                    "function": {
                        "name": str(raw.get("name") or ""),
                        "arguments": _json_string(raw.get("arguments")),
                    },
                })
        if role == "tool":
            item["tool_call_id"] = str(message.tool_call_id or "")
            if message.name:
                item["name"] = str(message.name)
        messages.append(item)
    return messages


def _adapter_tool_calls_from_openai(message: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    out = []
    for raw in message.get("tool_calls") or []:
        if not isinstance(raw, dict):
            continue
        function = raw.get("function") if isinstance(raw.get("function"), dict) else {}
        name = str(function.get("name") or "").strip()
        if not name:
            continue
        out.append({
            "id": str(raw.get("id") or f"call_{uuid.uuid4().hex[:16]}"),
            "name": name,
            "arguments": _json_string(function.get("arguments")),
        })
    return tuple(out)


def _catalog_entry(*, provider_id: str, model: str, display_name: str, local: bool, tools: bool,
                   context_window: int | None, max_output_tokens: int | None,
                   aliases: tuple[str, ...], tos_status: str) -> CatalogEntry:
    caps = ["text", "streaming", "json"]
    if tools:
        caps.append("tools")
    return CatalogEntry(
        public_id=f"{provider_id}/{model}",
        provider_id=provider_id,
        provider_model_id=model,
        display_name=display_name,
        capabilities=tuple(caps),
        context_window=context_window,
        max_output_tokens=max_output_tokens,
        aliases=aliases,
        local=local,
        enabled=True,
        tos_status=tos_status,
        free_tier=False,
        input_cost_per_million=None,
        output_cost_per_million=None,
        metadata={"adapter_pack": PACK_ID},
    )


class _BaseLiveAdapter(ProviderAdapter):
    provider_id = "abstract-live"

    def __init__(self, *, model: str, session: Any | None = None, timeout_s: float = _DEFAULT_TIMEOUT):
        self.model = str(model).strip()
        if not self.model:
            raise ValueError(f"{self.provider_id} model is required")
        self.session = session or requests.Session()
        self.timeout_s = max(1.0, min(float(timeout_s), 180.0))

    def configured(self) -> bool:
        raise NotImplementedError

    def safe_public_config(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model": self.model,
            "configured": self.configured(),
            "adapter_pack": PACK_ID,
            "credential_env_names": list(_credential_env_names(self.provider_id)),
        }

    def _route_model(self, route_slug: str) -> str:
        prefix = self.provider_id + "/"
        if not str(route_slug).startswith(prefix):
            raise ValueError(f"route does not belong to {self.provider_id}: {route_slug}")
        model = str(route_slug)[len(prefix):].strip()
        if not model:
            raise ValueError("provider model id missing from route")
        return model

    def probe(self) -> dict[str, Any]:
        return {
            "ok": self.configured(),
            "provider_id": self.provider_id,
            "configured": self.configured(),
            "mode": "passive",
            "model": self.model,
        }


class GroqAFGAdapter(_BaseLiveAdapter):
    provider_id = "groq"

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        session: Any | None = None,
        timeout_s: float = _DEFAULT_TIMEOUT,
    ):
        # R7.2.12 R5 R12 — AFG-only migration from legacy Groq route.
        explicit_afg_model = model or os.environ.get("AURA_FABRIC_GROQ_MODEL")
        selected_model = explicit_afg_model or _setting(
            "GROQ_MODEL",
            "GROQ_TEXT_MODEL",
            default="qwen/qwen3.6-27b",
        )

        # Preserve explicit AFG overrides, but migrate the inherited legacy
        # setting/default which is no longer usable on the current Groq route.
        if (
            not explicit_afg_model
            and str(selected_model or "").strip() == "llama-3.1-8b-instant"
        ):
            selected_model = "qwen/qwen3.6-27b"

        super().__init__(
            model=str(selected_model),
            session=session,
            timeout_s=timeout_s,
        )
        self._credential_names = _credential_env_names(self.provider_id)
        self._api_key = str(
            api_key or _first_env(self._credential_names) or ""
        )


    def configured(self) -> bool:
        return os.environ.get("AURA_FABRIC_DISABLE_GROQ", "0") != "1" and bool(self._api_key and self.model)

    def catalog_entries(self) -> tuple[CatalogEntry, ...]:
        item = _provider_seed_item(self.provider_id)
        return (_catalog_entry(
            provider_id=self.provider_id, model=self.model, display_name=f"Groq · {self.model}",
            local=False, tools=True, context_window=131072, max_output_tokens=32768,
            aliases=("groq-code",), tos_status=str(item.get("tos_status") or "reference_allowed"),
        ),)

    def generate(self, request: CanonicalRequest, route_slug: str) -> AdapterResult:
        if not self.configured():
            raise RuntimeError("Groq AFG adapter is not configured")
        model = self._route_model(route_slug)
        payload: dict[str, Any] = {"model": model, "messages": _openai_messages(request), "stream": False}
        if request.max_output_tokens is not None:
            payload["max_tokens"] = max(1, int(request.max_output_tokens))
            if str(model).startswith("qwen/qwen3."):
                payload["reasoning_effort"] = "none"
        tools = _canonical_tools_to_openai(request.tools)
        if tools:
            payload["tools"] = tools
            choice = _canonical_tool_choice_to_openai(request.tool_choice)
            if choice is not None:
                payload["tool_choice"] = choice
        if request.temperature is not None:
            payload["temperature"] = float(request.temperature)
        if request.max_output_tokens:
            payload["max_completion_tokens"] = int(request.max_output_tokens)
        response = self.session.post(
            GROQ_ENDPOINT,
            headers={"Authorization": "Bearer " + self._api_key, "Content-Type": "application/json"},
            json=payload, timeout=self.timeout_s,
        )
        data = _response_json(self.provider_id, response)
        choices = data.get("choices") or []
        if not choices or not isinstance(choices[0], dict):
            raise RuntimeError("Groq response has no choices")
        choice = choices[0]
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        tool_calls = _adapter_tool_calls_from_openai(message)
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return AdapterResult(
            text=str(message.get("content") or ""),
            finish_reason="tool_calls" if tool_calls else str(choice.get("finish_reason") or "stop"),
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            tool_calls=tool_calls,
            metadata={"provider_native_protocol": "openai_chat", "provider_model": model,
                      "tool_translation": bool(request.tools)},
        )


class GeminiAFGAdapter(_BaseLiveAdapter):
    provider_id = "gemini"

    def __init__(self, *, model: str | None = None, api_key: str | None = None,
                 session: Any | None = None, timeout_s: float = _DEFAULT_TIMEOUT):
        model = model or os.environ.get("AURA_FABRIC_GEMINI_MODEL") or _setting(
            "GEMINI_MODEL", "GEMINI_TEXT_MODEL", default="gemini-3.6-flash"
        )
        super().__init__(model=str(model), session=session, timeout_s=timeout_s)
        self._credential_names = _credential_env_names(self.provider_id)
        self._api_key = str(api_key or _first_env(self._credential_names) or "")
        self._call_context: dict[str, dict[str, Any]] = {}
        self._context_lock = threading.RLock()

    def configured(self) -> bool:
        return os.environ.get("AURA_FABRIC_DISABLE_GEMINI", "0") != "1" and bool(self._api_key and self.model)

    def catalog_entries(self) -> tuple[CatalogEntry, ...]:
        item = _provider_seed_item(self.provider_id)
        return (_catalog_entry(
            provider_id=self.provider_id, model=self.model, display_name=f"Gemini · {self.model}",
            local=False, tools=True, context_window=1048576, max_output_tokens=65536,
            aliases=("gemini-code",), tos_status=str(item.get("tos_status") or "reference_allowed"),
        ),)

    @staticmethod
    def _gemini_tools(tools: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
        declarations = []
        for tool in tools:
            if not isinstance(tool, dict) or str(tool.get("type") or "function") != "function":
                continue
            name = str(tool.get("name") or "").strip()
            if not name:
                continue
            parameters = tool.get("parameters") if isinstance(tool.get("parameters"), dict) else {}
            declarations.append({"name": name, "description": str(tool.get("description") or ""),
                                 "parameters": dict(parameters)})
        return [{"functionDeclarations": declarations}] if declarations else []

    @staticmethod
    def _gemini_tool_config(choice: Any) -> dict[str, Any] | None:
        if choice is None or choice == "auto":
            return {"functionCallingConfig": {"mode": "AUTO"}}
        if choice == "none":
            return {"functionCallingConfig": {"mode": "NONE"}}
        if choice == "required":
            return {"functionCallingConfig": {"mode": "ANY"}}
        if isinstance(choice, dict) and choice.get("type") == "function" and choice.get("name"):
            return {"functionCallingConfig": {"mode": "ANY", "allowedFunctionNames": [str(choice["name"])]}}
        return None

    def _gemini_contents(self, request: CanonicalRequest) -> tuple[list[dict[str, Any]], str]:
        lookup = _call_name_lookup(request.messages)
        system_chunks: list[str] = []
        if request.system:
            system_chunks.append(_system_text(request.system))
        contents: list[dict[str, Any]] = []

        for message in request.messages:
            if message.role in {"system", "developer"}:
                system_chunks.append(_text_content(message.content))
                continue
            if message.role == "tool":
                call_id = str(message.tool_call_id or "")
                name = lookup.get(call_id) or str(message.name or "tool")
                response_obj = _json_obj(message.content) or {"result": _text_content(message.content)}
                contents.append({"role": "user", "parts": [{"functionResponse": {
                    "id": call_id, "name": name, "response": response_obj
                }}]})
                continue

            role = "model" if message.role == "assistant" else "user"
            parts: list[dict[str, Any]] = []
            text = _text_content(message.content)
            if text:
                parts.append({"text": text})
            for raw in tuple(message.tool_calls or ()):
                call_id = str(raw.get("id") or raw.get("call_id") or f"call_{uuid.uuid4().hex[:16]}")
                part: dict[str, Any] = {"functionCall": {
                    "id": call_id, "name": str(raw.get("name") or ""),
                    "args": _json_obj(raw.get("arguments")),
                }}
                with self._context_lock:
                    cached = self._call_context.get(call_id)
                if cached and cached.get("thoughtSignature"):
                    part["thoughtSignature"] = cached["thoughtSignature"]
                parts.append(part)
            if parts:
                contents.append({"role": role, "parts": parts})
        return contents, "\n".join(x for x in system_chunks if x)

    def generate(self, request: CanonicalRequest, route_slug: str) -> AdapterResult:
        if not self.configured():
            raise RuntimeError("Gemini AFG adapter is not configured")
        model = self._route_model(route_slug)
        contents, system_text = self._gemini_contents(request)
        payload: dict[str, Any] = {"contents": contents}
        if request.max_output_tokens is not None:
            generation_config = dict(payload.get("generationConfig") or {})
            generation_config["maxOutputTokens"] = max(1, int(request.max_output_tokens))
            payload["generationConfig"] = generation_config
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        tools = self._gemini_tools(request.tools)
        if tools:
            payload["tools"] = tools
            tool_config = self._gemini_tool_config(request.tool_choice)
            if tool_config:
                payload["toolConfig"] = tool_config
        generation_config: dict[str, Any] = {}
        if request.temperature is not None:
            generation_config["temperature"] = float(request.temperature)
        if request.max_output_tokens:
            generation_config["maxOutputTokens"] = int(request.max_output_tokens)
        if generation_config:
            payload["generationConfig"] = generation_config

        endpoint = GEMINI_BASE + "/models/" + urllib.parse.quote(model, safe="-._") + ":generateContent"
        response = self.session.post(
            endpoint, headers={"x-goog-api-key": self._api_key, "Content-Type": "application/json"},
            json=payload, timeout=self.timeout_s,
        )
        data = _response_json(self.provider_id, response)
        candidates = data.get("candidates") or []
        if not candidates or not isinstance(candidates[0], dict):
            raise RuntimeError("Gemini response has no candidates")
        candidate = candidates[0]
        content = candidate.get("content") if isinstance(candidate.get("content"), dict) else {}
        parts = content.get("parts") if isinstance(content.get("parts"), list) else []
        text_chunks: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            if isinstance(part.get("text"), str):
                text_chunks.append(part["text"])
            call = part.get("functionCall") if isinstance(part.get("functionCall"), dict) else None
            if call:
                call_id = str(call.get("id") or f"call_gemini_{uuid.uuid4().hex[:16]}")
                name = str(call.get("name") or "")
                if not name:
                    continue
                tool_calls.append({"id": call_id, "name": name, "arguments": _json_string(call.get("args"))})
                if part.get("thoughtSignature"):
                    with self._context_lock:
                        self._call_context[call_id] = {
                            "thoughtSignature": part["thoughtSignature"], "stored_at": time.monotonic()
                        }
        usage = data.get("usageMetadata") if isinstance(data.get("usageMetadata"), dict) else {}
        return AdapterResult(
            text="".join(text_chunks),
            finish_reason="tool_calls" if tool_calls else str(candidate.get("finishReason") or "stop").casefold(),
            input_tokens=int(usage.get("promptTokenCount") or 0),
            output_tokens=int(usage.get("candidatesTokenCount") or 0),
            tool_calls=tuple(tool_calls),
            metadata={"provider_native_protocol": "gemini_generate_content", "provider_model": model,
                      "tool_translation": bool(request.tools),
                      "thought_signature_cache": bool(self._call_context)},
        )


class OllamaAFGAdapter(_BaseLiveAdapter):
    provider_id = "ollama"

    def __init__(self, *, model: str | None = None, host: str | None = None,
                 tools_enabled: bool | None = None, session: Any | None = None,
                 timeout_s: float = _DEFAULT_TIMEOUT, force_configured: bool | None = None):
        model = model or os.environ.get("AURA_FABRIC_OLLAMA_MODEL") or _setting(
            "OLLAMA_MODEL", "LOCAL_LLM_MODEL", "LLM_MODEL", default="llama3.1"
        )
        super().__init__(model=str(model), session=session, timeout_s=timeout_s)
        raw_host = host or os.environ.get("AURA_FABRIC_OLLAMA_HOST") or _setting(
            "OLLAMA_HOST", "OLLAMA_BASE_URL", default="http://127.0.0.1:11434"
        )
        try:
            self.host = validate_service_url(
                str(raw_host), allow_remote=bool(_setting("ALLOW_REMOTE_LLM", default=False))
            ).rstrip("/")
        except SecurityValidationError as exc:
            raise ValueError(f"Ollama AFG host refused by security policy: {exc}") from exc
        self.tools_enabled = bool(tools_enabled) if tools_enabled is not None else (
            os.environ.get("AURA_FABRIC_OLLAMA_TOOLS", "0") == "1"
        )
        self._force_configured = force_configured

    def configured(self) -> bool:
        if os.environ.get("AURA_FABRIC_DISABLE_OLLAMA", "0") == "1":
            return False
        if self._force_configured is not None:
            return bool(self._force_configured)
        return bool(self.model and _bool_setting("LOCAL_LLM_ENABLED", "OLLAMA_ENABLED", default=False))

    def catalog_entries(self) -> tuple[CatalogEntry, ...]:
        item = _provider_seed_item(self.provider_id)
        return (_catalog_entry(
            provider_id=self.provider_id, model=self.model, display_name=f"Ollama · {self.model}",
            local=True, tools=self.tools_enabled, context_window=None, max_output_tokens=None,
            aliases=("ollama-code",), tos_status=str(item.get("tos_status") or "local"),
        ),)

    def _ollama_messages(self, request: CanonicalRequest) -> list[dict[str, Any]]:
        lookup = _call_name_lookup(request.messages)
        out: list[dict[str, Any]] = []
        has_system = any(m.role in {"system", "developer"} for m in request.messages)
        if request.system and not has_system:
            out.append({"role": "system", "content": _system_text(request.system)})
        for message in request.messages:
            role = "system" if message.role == "developer" else message.role
            item: dict[str, Any] = {"role": role, "content": _text_content(message.content)}
            if role == "assistant" and message.tool_calls:
                item["tool_calls"] = []
                for index, raw in enumerate(message.tool_calls):
                    item["tool_calls"].append({"type": "function", "function": {
                        "index": index, "name": str(raw.get("name") or ""),
                        "arguments": _json_obj(raw.get("arguments")),
                    }})
            if role == "tool":
                item["tool_name"] = lookup.get(str(message.tool_call_id or "")) or str(message.name or "tool")
            out.append(item)
        return out

    def generate(self, request: CanonicalRequest, route_slug: str) -> AdapterResult:
        if not self.configured():
            raise RuntimeError("Ollama AFG adapter is not configured")
        model = self._route_model(route_slug)
        payload: dict[str, Any] = {"model": model, "messages": self._ollama_messages(request), "stream": False}
        if request.tools:
            if not self.tools_enabled:
                raise ValueError(
                    "Ollama tools are not enabled for this model; set AURA_FABRIC_OLLAMA_TOOLS=1 only for a tool-capable model."
                )
            payload["tools"] = _canonical_tools_to_openai(request.tools)
        options: dict[str, Any] = {}
        if request.temperature is not None:
            options["temperature"] = float(request.temperature)
        if request.max_output_tokens:
            options["num_predict"] = int(request.max_output_tokens)
        if options:
            payload["options"] = options
        response = self.session.post(
            self.host + "/api/chat", headers={"Content-Type": "application/json"},
            json=payload, timeout=self.timeout_s,
        )
        data = _response_json(self.provider_id, response)
        message = data.get("message") if isinstance(data.get("message"), dict) else {}
        tool_calls: list[dict[str, Any]] = []
        for raw in message.get("tool_calls") or []:
            if not isinstance(raw, dict):
                continue
            function = raw.get("function") if isinstance(raw.get("function"), dict) else {}
            name = str(function.get("name") or "").strip()
            if not name:
                continue
            tool_calls.append({
                "id": str(raw.get("id") or f"call_ollama_{uuid.uuid4().hex[:16]}"),
                "name": name, "arguments": _json_string(function.get("arguments")),
            })
        return AdapterResult(
            text=str(message.get("content") or ""),
            finish_reason="tool_calls" if tool_calls else str(data.get("done_reason") or "stop"),
            input_tokens=int(data.get("prompt_eval_count") or 0),
            output_tokens=int(data.get("eval_count") or 0),
            tool_calls=tuple(tool_calls),
            metadata={"provider_native_protocol": "ollama_chat", "provider_model": model,
                      "tool_translation": bool(request.tools)},
        )


@dataclass(frozen=True)
class LiveAdapterRegistration:
    provider_id: str
    configured: bool
    eligible: bool
    policy_state: str
    registered: bool
    public_model_ids: tuple[str, ...]

    def public_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id, "configured": self.configured,
            "eligible": self.eligible, "policy_state": self.policy_state,
            "registered": self.registered, "public_model_ids": list(self.public_model_ids),
        }


def _default_factories() -> tuple[tuple[str, int, Callable[[], ProviderAdapter]], ...]:
    return (
        ("ollama", 10, lambda: OllamaAFGAdapter()),
        ("groq", 20, lambda: GroqAFGAdapter()),
        ("gemini", 30, lambda: GeminiAFGAdapter()),
    )


def register_eligible_live_adapters(
    service: Any, *, registry: ProviderRegistry | None = None,
    factories: tuple[tuple[str, int, Callable[[], ProviderAdapter]], ...] | None = None,
) -> dict[str, Any]:
    registry = registry or load_default_registry()
    factories = factories or _default_factories()
    reports: list[LiveAdapterRegistration] = []
    registered_public_ids: list[str] = []

    for provider_id, priority, factory in factories:
        if provider_id not in registry.ids():
            reports.append(LiveAdapterRegistration(provider_id, False, False, "not_in_adf_c_registry", False, ()))
            continue
        try:
            adapter = factory()
            configured_fn = getattr(adapter, "configured", None)
            configured = bool(configured_fn()) if callable(configured_fn) else True
        except Exception:
            reports.append(LiveAdapterRegistration(provider_id, False, False, "adapter_initialization_failed", False, ()))
            continue

        decision = registry.evaluate(provider_id, configured=configured)
        public_ids = tuple(entry.public_id for entry in adapter.catalog_entries())
        if not configured:
            reports.append(LiveAdapterRegistration(
                provider_id, False, bool(decision.eligible), str(decision.state), False, public_ids
            ))
            continue
        if not decision.eligible:
            reports.append(LiveAdapterRegistration(provider_id, True, False, str(decision.state), False, public_ids))
            continue

        service.register_adapter(adapter, priority=int(priority))
        registered_public_ids.extend(public_ids)
        reports.append(LiveAdapterRegistration(provider_id, True, True, str(decision.state), True, public_ids))

    if registered_public_ids:
        service.set_alias("aura-code", registered_public_ids)
        service.set_alias("aura-default", registered_public_ids)

    snapshot = {
        "schema": "aura.fabric.live-adapter-pack-1.registration.v1",
        "pack_id": PACK_ID,
        "registered_count": sum(1 for x in reports if x.registered),
        "registered_provider_ids": [x.provider_id for x in reports if x.registered],
        "providers": [x.public_dict() for x in reports],
        "aliases_created": ["aura-code", "aura-default"] if registered_public_ids else [],
        "secrets_in_snapshot": False,
    }
    setattr(service, "live_adapter_registration", snapshot)
    return snapshot


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": "aura.fabric.live-adapter-pack-1.capabilities.v1",
        "pack_id": PACK_ID,
        "providers": {
            "groq": {"transport": "openai_chat", "tools": True, "multi_turn_tool_history": True},
            "gemini": {"transport": "gemini_generate_content", "tools": True,
                       "multi_turn_tool_history": True, "thought_signature_memory_cache": True},
            "ollama": {"transport": "ollama_chat", "tools": "opt_in_per_local_model",
                       "multi_turn_tool_history": True},
        },
        "provider_registry_policy_gate": True,
        "configured_gate": True,
        "secrets_serialized": False,
        "conversation_llm_manager_dependency": False,
        "network_calls_during_import": False,
        "provider_specific_retry_loops": False,
        "resilience_owner": "AURA Fabric Gateway",
    }
