from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
import json
import os
import socket
import threading
import time
import traceback
import urllib.parse

from runtime.aura_fabric_gateway import (
    FabricRegistry,
    ModelCapabilities,
    ModelDescriptor,
    ProviderDescriptor,
    Protocol,
    RouteRequest,
)
from runtime.aura_fabric_protocols import (
    CanonicalRequest,
    CanonicalResponse,
    PROTOCOL_ANTHROPIC,
    PROTOCOL_AURA_NATIVE,
    PROTOCOL_OPENAI_CHAT,
    PROTOCOL_OPENAI_RESPONSES,
    normalize_request,
    new_id,
    render_response,
    stream_events,
)
from runtime.aura_fabric_model_catalog import ModelCatalog
from runtime.aura_fabric_agent_bridge import public_agent_catalog
from runtime.aura_fabric_resilience import execute_with_resilience
from runtime.aura_repository_context import capability_snapshot as repository_capability_snapshot
from runtime.aura_self_development_governance import capability_snapshot as self_development_capability_snapshot
from runtime.aura_audit_ledger import capability_snapshot as audit_capability_snapshot
from runtime.aura_developer_mode import capability_snapshot as developer_mode_capability_snapshot, state_snapshot as developer_mode_state_snapshot
from runtime.aura_developer_live_bridge import capability_snapshot as developer_live_capability_snapshot, workspace_snapshot as developer_workspace_snapshot, handle_live_developer_input
from runtime.aura_developer_planner import capability_snapshot as planner_capability_snapshot
from runtime.aura_patch_transaction_engine import capability_snapshot as transaction_capability_snapshot
from runtime.aura_terminal_reduction_kernel import default_savings_summary
from runtime.aura_fabric_local_optimizations import capability_snapshot as local_optimization_snapshot
from runtime.aura_fabric_voice_bridge import detect_backends as detect_voice_backends
from runtime.aura_fabric_provider_registry import default_public_provider_snapshot
from runtime.aura_fabric_quota_observatory import default_quota_summary

from runtime.aura_fabric_provider_adapter import (
    AdapterResult,
    EchoProviderAdapter,
    FailingProviderAdapter,
    ProviderAdapter,
)
from runtime.aura_fabric_live_provider_adapters import register_eligible_live_adapters

PROTOCOL_MAP = {
    PROTOCOL_ANTHROPIC: Protocol.ANTHROPIC_MESSAGES,
    PROTOCOL_OPENAI_RESPONSES: Protocol.OPENAI_RESPONSES,
    PROTOCOL_OPENAI_CHAT: Protocol.OPENAI_CHAT,
    PROTOCOL_AURA_NATIVE: Protocol.AURA_NATIVE,
}

@dataclass(frozen=True)
class GatewayConfig:
    host: str = "127.0.0.1"
    port: int = 8766
    request_limit_bytes: int = 16 * 1024 * 1024
    retries_per_model: int = 3
    local_token: str | None = None
    allow_non_loopback: bool = False
    server_name: str = "AURA Fabric Gateway/ADF-B"

    @classmethod
    def from_env(cls) -> "GatewayConfig":
        token = os.environ.get("AURA_FABRIC_LOCAL_TOKEN") or None
        return cls(
            host=os.environ.get("AURA_FABRIC_HOST", "127.0.0.1"),
            port=int(os.environ.get("AURA_FABRIC_PORT", "8766")),
            request_limit_bytes=int(os.environ.get("AURA_FABRIC_REQUEST_LIMIT_BYTES", str(16 * 1024 * 1024))),
            retries_per_model=max(1, int(os.environ.get("AURA_FABRIC_RETRIES_PER_MODEL", "3"))),
            local_token=token,
            allow_non_loopback=os.environ.get("AURA_FABRIC_ALLOW_NON_LOOPBACK", "0") == "1",
        )

def _is_loopback_host(host: str) -> bool:
    return host in {"127.0.0.1", "::1", "localhost"}

class GatewayService:
    def __init__(self, *, retries_per_model: int = 3):
        self.registry = FabricRegistry()
        self.catalog = ModelCatalog()
        self.adapters: dict[str, ProviderAdapter] = {}
        self.retries_per_model = max(1, int(retries_per_model))
        self.started_at = time.monotonic()
        self.requests_total = 0
        self.requests_failed = 0
        self.failovers_total = 0
        self.last_route: dict[str, Any] | None = None
        self._lock = threading.RLock()

    def register_adapter(self, adapter: ProviderAdapter, *, priority: int = 100) -> None:
        entries = adapter.catalog_entries()
        if not entries:
            raise ValueError("adapter must expose at least one catalog entry")
        self.adapters[adapter.provider_id] = adapter
        models = []
        protocols = set()
        for entry in entries:
            self.catalog.register(entry)
            caps = set(entry.capabilities)
            models.append(ModelDescriptor(
                provider_id=entry.provider_id,
                model_id=entry.provider_model_id,
                display_name=entry.display_name,
                capabilities=ModelCapabilities(
                    tools="tools" in caps,
                    reasoning="reasoning" in caps,
                    vision="images" in caps or "vision" in caps,
                    streaming="streaming" in caps,
                    json_mode="json" in caps,
                    max_context_tokens=entry.context_window,
                ),
                input_cost_per_million=entry.input_cost_per_million,
                output_cost_per_million=entry.output_cost_per_million,
                local=entry.local,
                enabled=entry.enabled,
            ))
            protocols.update({
                Protocol.AURA_NATIVE,
                Protocol.OPENAI_RESPONSES,
                Protocol.OPENAI_CHAT,
                Protocol.ANTHROPIC_MESSAGES,
            })
        self.registry.register_provider(ProviderDescriptor(
            provider_id=adapter.provider_id,
            display_name=adapter.provider_id,
            protocols=tuple(sorted(protocols, key=lambda p: p.value)),
            models=tuple(models),
            enabled=True,
            data_boundary="local" if all(e.local for e in entries) else "cloud",
            priority=priority,
        ))

    def set_alias(self, alias: str, public_model_ids: list[str]) -> None:
        self.catalog.set_alias(alias, public_model_ids)
        slugs = self.catalog.route_slugs(alias)
        if slugs:
            self.registry.set_alias(alias, slugs)

    def _route_request(self, request: CanonicalRequest) -> RouteRequest:
        preferred = self.catalog.route_slugs(request.model)
        if not preferred and "/" in request.model:
            preferred = (request.model,)
        return RouteRequest(
            protocol=PROTOCOL_MAP[request.protocol],
            require_tools=bool(request.tools),
            require_reasoning=request.reasoning is not None,
            require_vision=request.has_images,
            require_streaming=request.stream,
            prefer_local=bool(request.metadata.get("prefer_local", False)),
            preferred_models=tuple(preferred),
        )

    def execute(self, request: CanonicalRequest) -> CanonicalResponse:
        return execute_with_resilience(self, request)

    def health_snapshot(self) -> dict[str, Any]:
        models = []
        healthy_count = 0
        for entry in self.catalog.entries():
            state = self.registry.health(entry.slug)
            available = state.available()
            if available:
                healthy_count += 1
            models.append({
                "id": entry.public_id,
                "route_slug": entry.slug,
                "provider_id": entry.provider_id,
                "available": available,
                "healthy": state.healthy,
                "success_ewma": round(state.success_ewma, 5),
                "latency_ms_ewma": None if state.latency_ms_ewma is None else round(state.latency_ms_ewma, 3),
                "consecutive_failures": state.consecutive_failures,
                "circuit_open": not available,
            })
        total = len(models)
        return {
            "schema": "aura.fabric.health.v1",
            "status": "ok" if healthy_count > 0 else ("starting" if total == 0 else "degraded"),
            "ready": healthy_count > 0,
            "uptime_s": round(time.monotonic() - self.started_at, 3),
            "models_total": total,
            "models_available": healthy_count,
            "requests_total": self.requests_total,
            "requests_failed": self.requests_failed,
            "failovers_total": self.failovers_total,
            "models": models,
            "last_route": self.last_route,
        }

    def probe_adapters(self) -> dict[str, Any]:
        results = []
        for provider_id, adapter in sorted(self.adapters.items()):
            started = time.monotonic()
            try:
                item = dict(adapter.probe())
                item.setdefault("ok", True)
            except Exception as exc:
                item = {"ok": False, "provider_id": provider_id, "error": f"{type(exc).__name__}: {exc}"}
            item["elapsed_ms"] = round((time.monotonic() - started) * 1000.0, 3)
            results.append(item)
        return {
            "schema": "aura.fabric.provider-probe.v1",
            "providers": results,
            "all_ok": bool(results) and all(bool(x.get("ok")) for x in results),
        }

def build_test_service(*, include_failure_route: bool = False, retries_per_model: int = 3) -> GatewayService:
    service = GatewayService(retries_per_model=retries_per_model)
    if include_failure_route:
        service.register_adapter(FailingProviderAdapter(), priority=0)
        service.register_adapter(EchoProviderAdapter(), priority=100)
        service.set_alias("aura-resilient-test", ["aura-fail", "aura-echo"])
    else:
        service.register_adapter(EchoProviderAdapter(), priority=10)
        service.set_alias("aura-default", ["aura-echo"])
    return service


def build_production_service(*, retries_per_model: int = 3) -> GatewayService:
    service = GatewayService(retries_per_model=retries_per_model)
    register_eligible_live_adapters(service)

    if os.environ.get("AURA_FABRIC_ENABLE_TEST_PROVIDER", "0") == "1":
        service.register_adapter(EchoProviderAdapter(), priority=9999)
        service.set_alias("aura-test", ["aura-echo"])
        if not getattr(service, "live_adapter_registration", {}).get("registered_count"):
            service.set_alias("aura-default", ["aura-echo"])
    return service


class AuraFabricHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, handler_cls, *, service: GatewayService, config: GatewayConfig):
        super().__init__(server_address, handler_cls)
        self.service = service
        self.config = config

class AuraFabricHandler(BaseHTTPRequestHandler):
    server_version = "AURA-Fabric/ADF-B"
    protocol_version = "HTTP/1.1"

    @property
    def gateway(self) -> AuraFabricHTTPServer:
        return self.server  # type: ignore[return-value]

    def log_message(self, format: str, *args) -> None:
        # Never log headers, bodies, or credentials.
        try:
            message = format % args
        except Exception:
            message = format
        print(f"[AFG] {self.client_address[0]} {message}")

    def _authorized(self) -> bool:
        token = self.gateway.config.local_token
        if not token:
            return True
        auth = self.headers.get("Authorization", "")
        return auth == "Bearer " + token

    def _security_gate(self, *, allow_health: bool = False) -> bool:
        remote = self.client_address[0]
        try:
            is_loopback = remote.startswith("127.") or remote == "::1"
        except Exception:
            is_loopback = False
        if not is_loopback and not self.gateway.config.allow_non_loopback:
            self._json(HTTPStatus.FORBIDDEN, {"error": {"type": "aura_security_error", "message": "non-loopback client denied"}})
            return False
        if allow_health:
            return True
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": {"type": "authentication_error", "message": "invalid local gateway token"}})
            return False
        return True

    def _json(self, status: int, payload: Any, *, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-AURA-Fabric-Version", "ADF-B")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("Content-Length is required")
        length = int(raw_length)
        if length < 0 or length > self.gateway.config.request_limit_bytes:
            raise ValueError("request body exceeds AURA Fabric limit")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8")) if raw else {}
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path in ("/health", "/ready"):
            if not self._security_gate(allow_health=True):
                return
            health = self.gateway.service.health_snapshot()
            if path == "/ready":
                code = HTTPStatus.OK if health["ready"] else HTTPStatus.SERVICE_UNAVAILABLE
                self._json(code, {
                    "schema": "aura.fabric.ready.v1",
                    "ready": health["ready"],
                    "status": health["status"],
                    "models_available": health["models_available"],
                })
            else:
                self._json(HTTPStatus.OK, health)
            return

        if not self._security_gate():
            return
        if path == "/v1/models":
            self._json(HTTPStatus.OK, self.gateway.service.catalog.openai_list())
            return
        if path == "/aura/v1/catalog":
            self._json(HTTPStatus.OK, self.gateway.service.catalog.aura_catalog())
            return
        if path == "/aura/v1/health":
            self._json(HTTPStatus.OK, self.gateway.service.health_snapshot())
            return
        if path == "/aura/v1/agents":
            self._json(HTTPStatus.OK, public_agent_catalog())
            return
        if path == "/aura/v1/developer-workspace":
            self._json(HTTPStatus.OK, {"schema":"aura.fabric.developer-workspace.v1","workspace":developer_workspace_snapshot(),"live_bridge":developer_live_capability_snapshot()})
            return
        if path == "/aura/v1/developer-mode":
            self._json(HTTPStatus.OK, {"schema":"aura.fabric.developer-mode.v1","state":developer_mode_state_snapshot(),"capabilities":developer_mode_capability_snapshot()})
            return
        if path == "/aura/v1/self-development":
            self._json(HTTPStatus.OK, {"schema":"aura.fabric.self-development.v1","governance":self_development_capability_snapshot(),"audit":audit_capability_snapshot()})
            return
        if path == "/aura/v1/developer":
            self._json(HTTPStatus.OK, {"schema": "aura.fabric.developer-capabilities.v1", "repository": repository_capability_snapshot(), "planner": planner_capability_snapshot(), "transaction": transaction_capability_snapshot()})
            return
        if path == "/aura/v1/efficiency":
            self._json(HTTPStatus.OK, {"schema": "aura.fabric.efficiency.v1", "terminal_reduction": default_savings_summary(), "local_optimizations": local_optimization_snapshot()})
            return
        if path == "/aura/v1/voice":
            self._json(HTTPStatus.OK, detect_voice_backends())
            return
        if path == "/aura/v1/providers":
            self._json(HTTPStatus.OK, default_public_provider_snapshot())
            return
        if path == "/aura/v1/quotas":
            self._json(HTTPStatus.OK, default_quota_summary())
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": {"type": "not_found", "message": f"unknown path: {path}"}})

    def _protocol_for_path(self, path: str) -> str | None:
        return {
            "/v1/responses": PROTOCOL_OPENAI_RESPONSES,
            "/v1/chat/completions": PROTOCOL_OPENAI_CHAT,
            "/v1/messages": PROTOCOL_ANTHROPIC,
            "/aura/v1/responses": PROTOCOL_AURA_NATIVE,
        }.get(path)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if not self._security_gate():
            return

        if path == "/aura/v1/developer-mode/command":
            try:
                payload = self._read_json()
                result = handle_live_developer_input(
                    str(payload.get("text") or ""),
                    channel=str(payload.get("channel") or "text"),
                )
                self._json(HTTPStatus.OK, result)
            except Exception as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error":{"type":"developer_mode_command_error","message":str(exc)[:300]}})
            return

        if path == "/aura/v1/health/probe":
            self._json(HTTPStatus.OK, self.gateway.service.probe_adapters())
            return

        protocol = self._protocol_for_path(path)
        if protocol is None:
            self._json(HTTPStatus.NOT_FOUND, {"error": {"type": "not_found", "message": f"unknown path: {path}"}})
            return

        try:
            payload = self._read_json()
            headers = {k.lower(): v for k, v in self.headers.items()}
            request = normalize_request(protocol, payload, headers)
            response = self.gateway.service.execute(request)
            if request.stream:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-store")
                self.send_header("Connection", "close")
                self.send_header("X-Accel-Buffering", "no")
                self.send_header("X-AURA-Fabric-Version", "ADF-B")
                self.end_headers()
                for event in stream_events(protocol, response):
                    self.wfile.write(event)
                    self.wfile.flush()
                self.close_connection = True
            else:
                self._json(HTTPStatus.OK, render_response(protocol, response))
        except LookupError as exc:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "error": {"type": "aura_route_unavailable", "message": str(exc)}
            })
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {
                "error": {"type": "invalid_request_error", "message": str(exc)}
            })
        except Exception as exc:
            self._json(HTTPStatus.BAD_GATEWAY, {
                "error": {
                    "type": "aura_gateway_error",
                    "message": str(exc)[:500],
                }
            })

def create_server(
    *,
    service: GatewayService | None = None,
    config: GatewayConfig | None = None,
    host: str | None = None,
    port: int | None = None,
) -> AuraFabricHTTPServer:
    config = config or GatewayConfig.from_env()
    bind_host = host if host is not None else config.host
    bind_port = int(port if port is not None else config.port)
    if not _is_loopback_host(bind_host) and not config.allow_non_loopback:
        raise PermissionError("AURA Fabric Gateway refuses non-loopback bind without AURA_FABRIC_ALLOW_NON_LOOPBACK=1")
    service = service or build_production_service(retries_per_model=config.retries_per_model)
    return AuraFabricHTTPServer((bind_host, bind_port), AuraFabricHandler, service=service, config=config)

def serve_forever() -> None:
    config = GatewayConfig.from_env()
    server = create_server(config=config)
    host, port = server.server_address[:2]
    print("=" * 72)
    print("AURA Fabric Gateway — ADF-B")
    print(f"Listening: http://{host}:{port}")
    print(f"Ready: {server.service.health_snapshot()['ready']}")
    print("Providers are populated by ADF-C; set AURA_FABRIC_ENABLE_TEST_PROVIDER=1 only for diagnostics.")
    print("=" * 72)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    serve_forever()
