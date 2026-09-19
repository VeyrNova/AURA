"""Compatibility facade for the AURA Runtime v2 intelligence router.

The project historically imported routing helpers from ``hybrid_runtime``.
v0.7.2.1 keeps those imports stable while moving the actual policy into the
canonical ``runtime.intelligence_router`` module.
"""
from __future__ import annotations

from runtime.intelligence_router import (
    IntelligenceRoute,
    choose_document_route,
    choose_llm_route,
    choose_router_route,
    cloud_configured,
    force_local_text,
    gemini_configured,
    groq_configured,
    local_enabled,
    use_groq_stt,
)

# Backward-compatible type name used by older tests/callers.
HybridLLMRoute = IntelligenceRoute

__all__ = [
    "HybridLLMRoute",
    "IntelligenceRoute",
    "choose_document_route",
    "choose_llm_route",
    "choose_router_route",
    "cloud_configured",
    "force_local_text",
    "gemini_configured",
    "groq_configured",
    "local_enabled",
    "use_groq_stt",
]
