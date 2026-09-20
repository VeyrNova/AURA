from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
import time

from runtime.aura_fabric_protocols import CanonicalRequest, estimate_tokens
from runtime.aura_fabric_model_catalog import CatalogEntry

@dataclass(frozen=True)
class AdapterResult:
    text: str
    finish_reason: str = "stop"
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

class ProviderAdapter:
    provider_id: str = "abstract"

    def catalog_entries(self) -> tuple[CatalogEntry, ...]:
        raise NotImplementedError

    def generate(self, request: CanonicalRequest, route_slug: str) -> AdapterResult:
        raise NotImplementedError

    def probe(self) -> dict[str, Any]:
        return {"ok": True, "provider_id": self.provider_id, "latency_ms": 0.0}

    def safe_public_config(self) -> dict[str, Any]:
        return {"provider_id": self.provider_id}

class EchoProviderAdapter(ProviderAdapter):
    provider_id = "aura-echo"

    def __init__(self, *, prefix: str = "AURA Fabric Gateway test echo: "):
        self.prefix = prefix

    def catalog_entries(self) -> tuple[CatalogEntry, ...]:
        return (
            CatalogEntry(
                public_id="aura-echo",
                provider_id=self.provider_id,
                provider_model_id="echo-v1",
                display_name="AURA Internal Echo",
                capabilities=("text", "streaming", "tools", "reasoning", "images", "json"),
                context_window=1000000,
                max_output_tokens=131072,
                aliases=("aura/test", "aura/echo-fast"),
                local=True,
                enabled=True,
                tos_status="internal",
                free_tier=True,
                input_cost_per_million=0.0,
                output_cost_per_million=0.0,
            ),
        )

    def generate(self, request: CanonicalRequest, route_slug: str) -> AdapterResult:
        prompt = request.prompt_text.strip() or "(empty input)"
        text = self.prefix + prompt
        return AdapterResult(
            text=text,
            input_tokens=estimate_tokens(prompt),
            output_tokens=estimate_tokens(text),
            metadata={
                "test_provider": True,
                "tools_preserved": bool(request.tools),
                "reasoning_preserved": request.reasoning is not None,
                "images_preserved": request.has_images,
            },
        )

class FailingProviderAdapter(ProviderAdapter):
    provider_id = "aura-fail"

    def catalog_entries(self) -> tuple[CatalogEntry, ...]:
        return (
            CatalogEntry(
                public_id="aura-fail",
                provider_id=self.provider_id,
                provider_model_id="fail-v1",
                display_name="AURA Internal Failure Simulator",
                capabilities=("text", "streaming", "tools", "reasoning", "images"),
                context_window=1000000,
                aliases=("aura/fail",),
                local=True,
                enabled=True,
                tos_status="internal",
                free_tier=True,
                input_cost_per_million=0.0,
                output_cost_per_million=0.0,
            ),
        )

    def generate(self, request: CanonicalRequest, route_slug: str) -> AdapterResult:
        raise RuntimeError("intentional AURA test-provider failure")

    def probe(self) -> dict[str, Any]:
        return {"ok": False, "provider_id": self.provider_id, "latency_ms": 0.0, "reason": "intentional-test-failure"}
