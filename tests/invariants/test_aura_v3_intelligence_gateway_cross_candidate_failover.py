from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_conversation_fabric_bridge import build_canonical_request
from runtime.aura_eligibility_filter_v3 import RouteCandidateV3
from runtime.aura_intelligence_gateway_v3 import (
    IntelligenceGatewayRequestV3,
    IntelligenceGatewayV3,
)
from runtime.aura_model_policy_engine_v3 import ModelPolicyRequest

class Caps:
    def route_profile(self, *, voice_output, user_text="", force_local=False, preferred_provider=None):
        return {"available": True, "data": {"provider": "local", "model": "route-a"}}
    def provider_availability(self):
        return {"available": True, "data": {"groq": False, "gemini": False, "any_remote": False}}
    def local_model_catalog(self, *, force=False):
        return {"available": True, "data": [{"name": "route-a"}, {"name": "route-b"}, {"name": "route-c"}]}
    def resource_snapshot(self, *, include_ollama=False, force_gpu=False):
        return {"available": True, "data": {"ram_available_gb": 32.0, "vram_used_mb": 0.0, "vram_total_mb": 0.0}}
    def gpu_runtime_snapshot(self):
        return {"available": True, "data": {}}

class Policy:
    def decide(self, request):
        return SimpleNamespace(
            primary={
                "provider": "local",
                "model": "route-a",
                "source": "test",
                "reason": "primary",
            },
            fallback_chain=(
                {
                    "provider": "local",
                    "model": "route-b",
                    "source": "test",
                    "reason": "fallback-b",
                },
                {
                    "provider": "local",
                    "model": "route-c",
                    "source": "test",
                    "reason": "fallback-c",
                },
            ),
            reason_codes=("TEST_PRIMARY",),
            blocked=False,
        )

calls = []
def executor(payload, selected_route):
    route = dict(selected_route)
    calls.append(route)
    model = str(route.get("model") or "")
    if model == "route-a":
        raise RuntimeError("first exact route failed")
    if model == "route-b":
        return {
            "ok": True,
            "text": "route-b-ok",
            "provider_id": "local",
            "provider": "local",
            "routed_model": "synthetic-b/route-b",
            "model": "synthetic-b/route-b",
            "requested_model": "synthetic-b/route-b",
            "finish_reason": "stop",
            "input_tokens": 1,
            "output_tokens": 2,
            "attempts": [{"route": "synthetic-b/route-b", "ok": True}],
            "failover_used": False,
            "failover_count": 0,
            "latency_ms": 1.0,
        }
    raise AssertionError(f"unexpected executor route {route}")

candidates = (
    RouteCandidateV3(
        provider="local",
        model="route-a",
        enabled=True,
        requires_network=False,
        uses_local_gpu=False,
        supported_tasks=("chat",),
        metadata={"fabric_route_slug": "synthetic-a/route-a"},
    ),
    RouteCandidateV3(
        provider="local",
        model="route-b",
        enabled=True,
        requires_network=False,
        uses_local_gpu=False,
        supported_tasks=("chat",),
        metadata={"fabric_route_slug": "synthetic-b/route-b"},
    ),
    RouteCandidateV3(
        provider="local",
        model="route-c",
        enabled=True,
        requires_network=False,
        uses_local_gpu=False,
        supported_tasks=("chat",),
        metadata={"fabric_route_slug": "synthetic-c/route-c"},
    ),
)

gateway = IntelligenceGatewayV3(
    capability_service=Caps(),
    fabric_executor=executor,
    model_policy=Policy(),
)

result = gateway.execute(
    IntelligenceGatewayRequestV3(
        execution_payload=build_canonical_request(
            [{"role": "user", "content": "gateway-cross-candidate-fallback"}],
            profile={"num_predict": 8, "temperature": 0.0},
            model="aura-default",
        ),
        candidates=candidates,
        policy_request=ModelPolicyRequest(
            user_text="gateway-cross-candidate-fallback",
            task_type="chat",
            mode="automatic",
            streaming=False,
        ),
        correlation_id="gateway-cross-candidate-fallback",
        network_allowed=True,
    )
)

assert result.ok is True
assert result.blocked is False
assert result.text == "route-b-ok"
assert result.fallback_count == 1
assert len(calls) == 2, calls
assert calls[0]["model"] == "route-a"
assert calls[1]["model"] == "route-b"
assert all(call["model"] != "route-c" for call in calls)

execution = dict(result.execution)
assert execution["gateway_failover_count"] == 1
assert execution["fallback_count"] == 1
assert execution["failover_count"] == 1
assert execution["failover_used"] is True
assert len(execution["gateway_attempts"]) == 2
assert execution["gateway_attempts"][0]["ok"] is False
assert execution["gateway_attempts"][1]["ok"] is True

trace = dict(result.trace)
events = list(trace.get("events") or [])
gateway_attempts = [
    e for e in events
    if e.get("stage") == "gateway"
    and int(dict(e.get("metadata") or {}).get("gateway_attempt") or 0) > 0
]
assert len(gateway_attempts) == 2
assert gateway_attempts[0]["outcome"] == "exception"
assert gateway_attempts[1]["outcome"] == "success"

switch_events = [e for e in events if e.get("stage") == "model_switch_gate"]
assert switch_events
assert switch_events[-1]["selected_model"] == "route-b"
assert "EXECUTION_FAILURE_FALLBACK" in switch_events[-1]["reason_codes"]

gateway_events = [e for e in events if e.get("stage") == "gateway"]
assert gateway_events[-1]["outcome"] == "success"
assert gateway_events[-1]["metadata"]["gateway_fallback_count"] == 1

print("PASS AURA v3 IntelligenceGatewayV3 cross-candidate fallback invariant")
