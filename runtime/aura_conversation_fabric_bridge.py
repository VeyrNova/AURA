from __future__ import annotations

# AURA I18N R5 — canonical conversation language authority
def _aura_i18n_r5_locale() -> str:
    try:
        import json as _json
        from pathlib import Path as _Path
        _base = os.environ.get("APPDATA") or str(_Path.home() / "AppData" / "Roaming")
        _p = _Path(_base) / "AURA" / "config" / "locale.json"
        if _p.is_file():
            _raw = _json.loads(_p.read_text(encoding="utf-8"))
            _loc = str(_raw.get("locale") or "").strip()
            if _loc in {"fr-FR", "en-US"}:
                return _loc
    except Exception:
        pass
    _raw = str(os.environ.get("AURA_LOCALE") or "fr-FR").strip().lower()
    return "en-US" if _raw.startswith("en") else "fr-FR"

def _aura_i18n_r5_language_directive() -> str:
    if _aura_i18n_r5_locale() == "en-US":
        return ("ACTIVE LANGUAGE: ENGLISH. Answer in natural English. All normal assistant prose, "
                "confirmations, explanations and spoken response text must be English unless the user explicitly requests another language.")
    return ("LANGUE ACTIVE : FRANÇAIS. Réponds en français naturel. Tout le texte normal de l'assistante "
            "doit être en français sauf demande explicite de l'utilisateur.")


import os
import re
import threading
import time
import uuid
from types import SimpleNamespace
from typing import Any

from runtime.aura_fabric_http_gateway import PROTOCOL_MAP, build_production_service
from runtime.aura_fabric_protocols import CanonicalMessage, CanonicalRequest

AUTO_ALIAS = "aura-default"

_EXPLICIT_PROVIDER_RE = re.compile(
    r"(?i)\b(?:utilise|utiliser|use|using|avec|via|force|forcer)\s+"
    r"(?:gemini|groq|ollama|local)\b|"
    r"\b(?:gemini|groq|ollama|local)\s+(?:uniquement|only)\b"
)
_PRIVATE_LOCAL_RE = re.compile(
    r"(?i)\b(?:en\s+local|mode\s+local|hors[- ]ligne|offline|sans\s+cloud|"
    r"ne\s+pas\s+utiliser\s+(?:internet|le\s+cloud)|privacy[- ]local)\b"
)

_service = None
_service_lock = threading.RLock()


def should_use_conversation_fabric_auto(
    profile: dict[str, Any],
    user_text: str = "",
) -> bool:
    """Return True only for ordinary auto-routed conversation turns."""
    if str(os.environ.get("AURA_CONVERSATION_FABRIC_AUTO", "1")).strip().casefold() in {
        "0", "false", "off", "no"
    }:
        return False

    if bool(profile.get("native_document")) or bool(profile.get("document_context")):
        return False

    provider = str(profile.get("provider") or "local").strip().casefold()
    if provider not in {"gemini", "groq", "local"}:
        return False

    raw_text = str(user_text or "")
    if _EXPLICIT_PROVIDER_RE.search(raw_text) or _PRIVATE_LOCAL_RE.search(raw_text):
        return False

    provenance = " ".join(
        str(profile.get(k) or "")
        for k in (
            "reason",
            "route_reason",
            "selection_reason",
            "provider_reason",
            "preferred_provider",
            "requested_provider",
            "provider_source",
            "name",
        )
    ).casefold()

    strict_markers = (
        "preferred-gemini",
        "preferred-groq",
        "preferred-local",
        "forced-local",
        "privacy-local",
        "explicit-gemini",
        "explicit-groq",
        "explicit-local",
        "document-",
    )
    if any(marker in provenance for marker in strict_markers):
        return False

    return True


def _default_protocol_key() -> Any:
    # GatewayService indexes PROTOCOL_MAP with request.protocol. Prefer its
    # AURA-native key without hard-coding the exact enum/string representation.
    for key in PROTOCOL_MAP:
        low = str(key).casefold()
        if "aura" in low and "native" in low:
            return key
    for key in PROTOCOL_MAP:
        low = str(key).casefold()
        if "openai" in low and "chat" in low:
            return key
    return next(iter(PROTOCOL_MAP))


def build_canonical_request(
    messages: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    profile: dict[str, Any] | None = None,
    model: str = AUTO_ALIAS,
) -> CanonicalRequest:
    profile = dict(profile or {})
    _aura_messages = [dict(item) for item in messages]
    _aura_directive = _aura_i18n_r5_language_directive()
    _aura_system_index = next((i for i,item in enumerate(_aura_messages) if str(item.get("role") or "").casefold()=="system"), None)
    if _aura_system_index is None:
        _aura_messages.insert(0, {"role":"system","content":_aura_directive,"name":"aura_locale"})
    else:
        _aura_messages[_aura_system_index]["content"] = str(_aura_messages[_aura_system_index].get("content") or "").rstrip() + "\n\n" + _aura_directive
    canonical_messages = tuple(
        CanonicalMessage(
            role=str(item.get("role") or "user"),
            content=str(item.get("content") or ""),
            name=(str(item.get("name")) if item.get("name") else None),
        )
        for item in _aura_messages
    )

    return CanonicalRequest(
        request_id="aura-auto-" + uuid.uuid4().hex,
        protocol=_default_protocol_key(),
        model=str(model or AUTO_ALIAS),
        messages=canonical_messages,
        stream=False,
        max_output_tokens=int(profile.get("num_predict") or 512),
        temperature=float(profile.get("temperature", 0.45)),
        metadata={
            "source": "aura-conversation-auto",
            "prefer_local": bool(profile.get("prefer_local", False)),
            "voice_response": bool(profile.get("voice_response", False)),
        },
    )


def _get_service():
    global _service
    with _service_lock:
        if _service is None:
            _service = build_production_service()
        return _service


def generate_conversation_fabric(
    messages: list[dict[str, Any]],
    *,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    service = _get_service()
    request = build_canonical_request(messages, profile=profile, model=AUTO_ALIAS)

    before_failovers = int(getattr(service, "failovers_total", 0) or 0)
    started = time.perf_counter()
    response = service.execute(request)
    elapsed = time.perf_counter() - started
    after_failovers = int(getattr(service, "failovers_total", before_failovers) or 0)
    failover_count = max(0, after_failovers - before_failovers)

    metadata = dict(getattr(response, "metadata", {}) or {})
    last_route = dict(getattr(service, "last_route", {}) or {})
    attempts = list(
        metadata.get("attempts")
        or last_route.get("attempts")
        or last_route.get("routes")
        or ()
    )

    return {
        "text": str(getattr(response, "text", "") or ""),
        "provider_id": str(getattr(response, "provider_id", "") or ""),
        "routed_model": str(getattr(response, "routed_model", "") or ""),
        "requested_model": str(
            getattr(response, "requested_model", AUTO_ALIAS) or AUTO_ALIAS
        ),
        "finish_reason": str(getattr(response, "finish_reason", "") or ""),
        "input_tokens": int(getattr(response, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(response, "output_tokens", 0) or 0),
        "attempts": attempts,
        "failover_used": bool(
            metadata.get("failover_used")
            or failover_count > 0
            or last_route.get("failover_used")
        ),
        "failover_count": int(
            metadata.get("failover_count", failover_count) or failover_count
        ),
        "latency_seconds": float(elapsed),
        "metadata": metadata,
        "last_route": last_route,
    }


def fabric_metrics_from_result(
    result: dict[str, Any],
    profile: dict[str, Any],
) -> Any:
    elapsed = float(result.get("latency_seconds", 0.0) or 0.0)
    output_tokens = int(result.get("output_tokens", 0) or 0)
    if output_tokens <= 0:
        output_tokens = max(1, len(str(result.get("text") or "")) // 4)
    input_tokens = int(result.get("input_tokens", 0) or 0)

    return SimpleNamespace(
        model=str(result.get("routed_model") or AUTO_ALIAS),
        load_seconds=0.0,
        prompt_eval_seconds=0.0,
        prompt_tokens=input_tokens,
        eval_seconds=elapsed,
        output_tokens=output_tokens,
        tokens_per_second=(output_tokens / elapsed) if elapsed > 0 else 0.0,
        total_seconds=elapsed,
        keep_alive="fabric",
        num_ctx=int(profile.get("num_ctx") or 0),
        num_predict=int(profile.get("num_predict") or 0),
        done_reason=str(result.get("finish_reason") or "fabric"),
    )


def apply_fabric_result_to_profile(
    profile: dict[str, Any],
    result: dict[str, Any],
) -> None:
    provider_id = str(result.get("provider_id") or "").casefold()
    routed_model = str(result.get("routed_model") or AUTO_ALIAS)

    # Downstream completion helpers expect the legacy provider vocabulary.
    profile["provider"] = (
        "local"
        if provider_id == "ollama"
        else (provider_id or profile.get("provider", "local"))
    )
    profile["model"] = routed_model
    profile["_aura_fabric_provider_id"] = provider_id
    profile["_aura_fabric_routed_model"] = routed_model
