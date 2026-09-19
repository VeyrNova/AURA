"""AURA Runtime v2 deterministic intelligence router.

Policy for v0.7.2.1:
- local deterministic intents/tools stay local;
- Groq is the primary conversational cloud brain;
- Gemini is preferred for documents/vision and the secondary text brain;
- a local generative model is optional, never required for normal startup;
- explicit local/private requests fail closed when local intelligence is disabled.

The legacy ``runtime.hybrid_runtime`` module delegates to this file so existing
callers keep working while routing policy gains a single canonical home.
"""
from __future__ import annotations

from dataclasses import dataclass

from config.settings import settings
from memory.privacy import looks_sensitive


@dataclass(frozen=True)
class IntelligenceRoute:
    provider: str
    model: str
    reason: str
    remote: bool
    available: bool = True


def cloud_mode_enabled() -> bool:
    return str(settings.AURA_RUNTIME_MODE or "cloud").strip().lower() in {
        "cloud", "hybrid", "auto", "cloud-first",
    }


def local_enabled() -> bool:
    return bool(getattr(settings, "LOCAL_LLM_ENABLED", False))


def groq_configured() -> bool:
    return bool(cloud_mode_enabled() and settings.GROQ_ENABLED and settings.GROQ_API_KEY)


def gemini_configured() -> bool:
    return bool(cloud_mode_enabled() and settings.GEMINI_ENABLED and settings.GEMINI_API_KEY)


def cloud_configured() -> bool:
    return bool(groq_configured() or gemini_configured())


def force_local_text(text: str) -> bool:
    raw = str(text or "").strip()
    folded = raw.casefold()
    if any(token in folded for token in settings.HYBRID_LOCAL_ONLY_MARKERS):
        return True
    if settings.HYBRID_PRIVATE_MEMORY_LOCAL_ONLY and looks_sensitive(raw):
        return True
    return False


def _local_model(voice_output: bool) -> str:
    return settings.LLM_VOICE_MODEL if voice_output else settings.LLM_TEXT_MODEL


def _local_route(*, voice_output: bool, reason: str) -> IntelligenceRoute:
    return IntelligenceRoute(
        provider="local",
        model=_local_model(voice_output),
        reason=reason,
        remote=False,
        available=local_enabled(),
    )


def _cloud_route(provider: str, *, voice_output: bool, reason: str) -> IntelligenceRoute:
    provider = str(provider or "").casefold()
    if provider == "groq":
        model = settings.GROQ_FAST_MODEL if voice_output else settings.GROQ_REASONING_MODEL
        return IntelligenceRoute("groq", model, reason, True, groq_configured())
    if provider == "gemini":
        model = settings.GEMINI_FAST_MODEL if voice_output else settings.GEMINI_REASONING_MODEL
        return IntelligenceRoute("gemini", model, reason, True, gemini_configured())
    return _local_route(voice_output=voice_output, reason="unknown-provider")


def choose_llm_route(
    text: str,
    *,
    voice_output: bool,
    force_local: bool = False,
    preferred_provider: str | None = None,
) -> IntelligenceRoute:
    if force_local or force_local_text(text):
        return _local_route(
            voice_output=voice_output,
            reason="forced-local" if force_local else "privacy-local",
        )

    preferred = str(preferred_provider or "auto").strip().casefold()
    if preferred == "local":
        return _local_route(voice_output=voice_output, reason="preferred-local")
    if preferred == "groq":
        if groq_configured():
            return _cloud_route("groq", voice_output=voice_output, reason="preferred-groq")
        if gemini_configured():
            return _cloud_route("gemini", voice_output=voice_output, reason="groq-unavailable-gemini")
        return _local_route(voice_output=voice_output, reason="cloud-unavailable")
    if preferred == "gemini":
        if gemini_configured():
            return _cloud_route("gemini", voice_output=voice_output, reason="preferred-gemini")
        if groq_configured():
            return _cloud_route("groq", voice_output=voice_output, reason="gemini-unavailable-groq")
        return _local_route(voice_output=voice_output, reason="cloud-unavailable")

    # Cloud Intelligence: Groq first for conversation, Gemini second.
    if groq_configured():
        return _cloud_route("groq", voice_output=voice_output, reason="cloud-groq-primary")
    if gemini_configured():
        return _cloud_route("gemini", voice_output=voice_output, reason="cloud-gemini-secondary")
    return _local_route(voice_output=voice_output, reason="cloud-unavailable-local-fallback")


def choose_document_route(
    text: str,
    *,
    preferred_provider: str | None = None,
    gemini_ready: bool | None = None,
    groq_ready: bool | None = None,
) -> IntelligenceRoute:
    if force_local_text(text) or not settings.DOCUMENT_CLOUD_ENABLED:
        return _local_route(voice_output=False, reason="document-local-policy")

    gemini_ok = gemini_configured() if gemini_ready is None else bool(gemini_ready and gemini_configured())
    groq_ok = groq_configured() if groq_ready is None else bool(groq_ready and groq_configured())
    preferred = str(preferred_provider or settings.DOCUMENT_ANALYSIS_PROVIDER or "auto").strip().casefold()

    if preferred == "local":
        return _local_route(voice_output=False, reason="document-preferred-local")
    if preferred == "groq":
        if groq_ok:
            return IntelligenceRoute("groq", settings.GROQ_REASONING_MODEL, "document-groq", True, True)
        if gemini_ok:
            return IntelligenceRoute("gemini", settings.GEMINI_DOCUMENT_MODEL, "document-groq-fallback-gemini", True, True)
        return _local_route(voice_output=False, reason="document-cloud-unavailable")
    # AUTO and explicit Gemini both prefer Gemini for document understanding.
    if gemini_ok:
        return IntelligenceRoute("gemini", settings.GEMINI_DOCUMENT_MODEL, "document-gemini-primary", True, True)
    if groq_ok:
        return IntelligenceRoute("groq", settings.GROQ_REASONING_MODEL, "document-groq-fallback", True, True)
    return _local_route(voice_output=False, reason="document-cloud-unavailable")


def choose_router_route(text: str, *, force_local: bool = False) -> IntelligenceRoute:
    if force_local or force_local_text(text):
        return IntelligenceRoute("local", settings.AGENT_ROUTER_MODEL, "router-local-policy", False, local_enabled())
    if groq_configured():
        return IntelligenceRoute("groq", settings.GROQ_ROUTER_MODEL, "router-groq", True, True)
    if gemini_configured():
        return IntelligenceRoute("gemini", settings.GEMINI_FAST_MODEL, "router-gemini", True, True)
    return IntelligenceRoute("local", settings.AGENT_ROUTER_MODEL, "router-local-fallback", False, local_enabled())


def use_groq_stt() -> bool:
    return bool(groq_configured() and settings.GROQ_STT_ENABLED)
