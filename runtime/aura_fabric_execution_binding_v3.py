from __future__ import annotations

"""AURA Fabric Execution Binding v3.

Small adapter between IntelligenceGatewayV3 and the existing AURA Fabric
GatewayService contract.

Responsibilities are intentionally narrow:
- accept an existing frozen CanonicalRequest execution payload;
- require an exact Fabric model id / route slug from selected_route metadata;
- clone the request with that exact model using dataclasses.replace();
- obtain the already-owned GatewayService through an injected service provider;
- call GatewayService.execute() exactly once;
- normalize CanonicalResponse into the mapping expected by IntelligenceGatewayV3.

This binding does NOT own:
- provider HTTP/SDK code,
- retries/backoff/fallbacks,
- provider health scoring,
- model routing,
- hardware probing,
- production service singleton ownership.
"""

from dataclasses import replace
import time
from typing import Any, Callable, Mapping

from runtime.aura_fabric_protocols import CanonicalRequest

SCHEMA = "aura.fabric_execution_binding.v3"
VERSION = "3.0.0"


class AuraFabricExecutionBindingV3:
    def __init__(
        self,
        *,
        service_provider: Callable[[], Any],
    ) -> None:
        if not callable(service_provider):
            raise TypeError("service_provider must be callable")
        self._service_provider = service_provider

    def __call__(
        self,
        execution_payload: Any,
        selected_route: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self.execute(execution_payload, selected_route)

    def execute(
        self,
        execution_payload: Any,
        selected_route: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(execution_payload, CanonicalRequest):
            raise TypeError("execution_payload must be CanonicalRequest")
        if not isinstance(selected_route, Mapping):
            raise TypeError("selected_route must be a mapping")

        exact_model = self._exact_fabric_model(selected_route)

        # CanonicalRequest is frozen in the existing Fabric protocol contract.
        # Rebuild it immutably rather than mutating the caller-owned payload.
        request = replace(execution_payload, model=exact_model)

        service = self._service_provider()
        if service is None:
            raise RuntimeError("Fabric service provider returned None")
        execute = getattr(service, "execute", None)
        if not callable(execute):
            raise TypeError("Fabric service does not expose callable execute()")

        started = time.perf_counter()
        response = execute(request)  # exactly one delegation; Fabric owns retries/fallbacks
        elapsed_ms = max(0.0, (time.perf_counter() - started) * 1000.0)

        metadata = dict(getattr(response, "metadata", {}) or {})
        attempts = list(metadata.get("attempts") or ())
        failover_count = int(metadata.get("failover_count", 0) or 0)

        provider_id = str(getattr(response, "provider_id", "") or "")
        routed_model = str(getattr(response, "routed_model", "") or "")
        requested_model = str(
            getattr(response, "requested_model", exact_model) or exact_model
        )

        return {
            "ok": True,
            "text": str(getattr(response, "text", "") or ""),
            "provider_id": provider_id,
            "provider": provider_id,
            "routed_model": routed_model,
            "model": routed_model,
            "requested_model": requested_model,
            "finish_reason": str(getattr(response, "finish_reason", "") or ""),
            "input_tokens": int(getattr(response, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(response, "output_tokens", 0) or 0),
            "tool_calls": tuple(getattr(response, "tool_calls", ()) or ()),
            "attempts": attempts,
            "failover_used": bool(metadata.get("failover_used", False)),
            "failover_count": failover_count,
            "latency_ms": elapsed_ms,
            "metadata": metadata,
            "binding": {
                "schema": SCHEMA,
                "version": VERSION,
                "exact_fabric_model": exact_model,
            },
        }

    @staticmethod
    def _exact_fabric_model(selected_route: Mapping[str, Any]) -> str:
        metadata = selected_route.get("metadata")
        metadata = dict(metadata) if isinstance(metadata, Mapping) else {}

        # Exact Fabric routing identifier. We deliberately do not infer one from
        # provider name because that would duplicate ModelCatalog/Fabric routing.
        value = (
            metadata.get("fabric_route_slug")
            or metadata.get("route_slug")
            or metadata.get("fabric_model_id")
            or selected_route.get("fabric_route_slug")
            or selected_route.get("route_slug")
            or selected_route.get("fabric_model_id")
        )
        exact = str(value or "").strip()
        if not exact:
            raise ValueError(
                "selected_route must contain an exact Fabric route/model id "
                "(fabric_route_slug, route_slug or fabric_model_id)"
            )
        return exact
