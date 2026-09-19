from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET = ROOT / "runtime" / "aura_intelligence_gateway_v3.py"
text = TARGET.read_text(encoding="utf-8")
tree = ast.parse(text)
compile(text, str(TARGET), "exec")

# Gateway v3 must orchestrate only. Existing Fabric owns all real provider/network
# execution and resilience.
for forbidden in (
    "requests.",
    "httpx.",
    "urllib.",
    "socket.",
    "subprocess.",
    "nvidia-smi",
    "torch.cuda",
    "psutil",
    "GroqProvider",
    "GeminiProvider",
    "OllamaProvider",
    "GroqAFGAdapter",
    "GeminiAFGAdapter",
    "OllamaAFGAdapter",
    "build_production_service(",
    "execute_with_resilience(",
    "prepare_for_llm(",
    "load_model(",
    "unload_model(",
):
    assert forbidden not in text, forbidden

from runtime.aura_eligibility_filter_v3 import RouteCandidateV3
from runtime.aura_intelligence_gateway_v3 import (
    IntelligenceGatewayRequestV3,
    IntelligenceGatewayV3,
)
from runtime.aura_model_policy_engine_v3 import ModelPolicyRequest
from runtime.aura_model_switch_gate_v3 import (
    ModelSwitchSessionStateV3,
    RouteIdentityV3,
)

class FakeCapabilities:
    def __init__(self):
        self.local_models = [{"name": "local-7b"}]

    def route_profile(self, *, voice_output, user_text="", force_local=False, preferred_provider=None):
        if force_local:
            return {"available": True, "data": {"provider": "local", "model": "local-7b"}}
        if preferred_provider == "gemini":
            return {"available": True, "data": {"provider": "gemini", "model": "gemini-1"}}
        return {"available": True, "data": {"provider": "groq", "model": "groq-1"}}

    def provider_availability(self):
        return {
            "available": True,
            "data": {"groq": True, "gemini": True, "any_remote": True},
        }

    def local_model_catalog(self, *, force=False):
        return {"available": True, "data": list(self.local_models)}

    def resource_snapshot(self, *, include_ollama=False, force_gpu=False):
        return {
            "available": True,
            "data": {
                "ram_available_gb": 16.0,
                "vram_used_mb": 1000.0,
                "vram_total_mb": 8192.0,
            },
        }

    def gpu_runtime_snapshot(self):
        return {"available": True, "data": {"topology": "intel-display+nvidia-compute"}}

calls = []
def fake_executor(payload, route):
    calls.append((payload, dict(route)))
    return {
        "ok": True,
        "text": "hello from fabric",
        "provider_id": route["provider"],
        "routed_model": route["model"],
        "latency_ms": 42.0,
        "finish_reason": "stop",
        "failover_count": 0,
        "attempts": [{"route": f"{route['provider']}/{route['model']}", "ok": True}],
    }

caps = FakeCapabilities()
gateway = IntelligenceGatewayV3(
    capability_service=caps,
    fabric_executor=fake_executor,
)

candidates = (
    RouteCandidateV3(
        provider="groq",
        model="groq-1",
        requires_network=True,
        context_window=32768,
        supported_tasks=("chat",),
    ),
    RouteCandidateV3(
        provider="gemini",
        model="gemini-1",
        requires_network=True,
        context_window=32768,
        supported_tasks=("chat",),
    ),
    RouteCandidateV3(
        provider="local",
        model="local-7b",
        uses_local_gpu=True,
        min_vram_mb=4000.0,
        context_window=8192,
        supported_tasks=("chat",),
    ),
)

result = gateway.execute(
    IntelligenceGatewayRequestV3(
        execution_payload={"opaque": "payload"},
        candidates=candidates,
        policy_request=ModelPolicyRequest(
            user_text="bonjour",
            task_type="chat",
            mode="automatic",
        ),
        correlation_id="test-1",
    )
)
assert result.ok is True
assert result.blocked is False
assert result.text == "hello from fabric"
assert result.provider == "groq"
assert len(calls) == 1
assert calls[0][1]["provider"] == "groq"
assert result.trace["status"] == "completed"
stages = [x["stage"] for x in result.trace["events"]]
assert "eligibility" in stages
assert "model_policy" in stages
assert "model_switch_gate" in stages
assert "gateway" in stages

# Local-only hard constraint must never execute a cloud route.
calls.clear()
local = gateway.execute(
    IntelligenceGatewayRequestV3(
        execution_payload={"opaque": "local"},
        candidates=candidates,
        policy_request=ModelPolicyRequest(
            user_text="secret",
            task_type="chat",
            mode="local_only",
            privacy="local_required",
        ),
        correlation_id="test-local",
    )
)
assert local.ok is True
assert calls[0][1]["provider"] == "local"

# Offline request eliminates remote candidates before execution.
calls.clear()
offline = gateway.execute(
    IntelligenceGatewayRequestV3(
        execution_payload={"opaque": "offline"},
        candidates=candidates,
        policy_request=ModelPolicyRequest(
            user_text="offline",
            task_type="chat",
            mode="local_only",
        ),
        network_allowed=False,
    )
)
assert offline.ok is True
assert calls[0][1]["provider"] == "local"

# Insufficient XTTS-safe VRAM blocks local-only request fail-closed.
calls.clear()
blocked = gateway.execute(
    IntelligenceGatewayRequestV3(
        execution_payload={"opaque": "blocked"},
        candidates=(
            RouteCandidateV3(
                provider="local",
                model="local-7b",
                uses_local_gpu=True,
                min_vram_mb=7000.0,
                supported_tasks=("chat",),
            ),
        ),
        policy_request=ModelPolicyRequest(
            user_text="secret",
            task_type="chat",
            mode="local_only",
        ),
        xtts_hot=True,
        xtts_vram_reserve_mb=2500.0,
    )
)
assert blocked.blocked is True
assert blocked.error_code == "NO_ELIGIBLE_CANDIDATES"
assert calls == []

# Explicit user provider preference intentionally overrides route stickiness.
calls.clear()
explicit = gateway.execute(
    IntelligenceGatewayRequestV3(
        execution_payload={"opaque": "explicit"},
        candidates=candidates,
        policy_request=ModelPolicyRequest(
            user_text="use gemini",
            task_type="chat",
            preferred_provider="gemini",
        ),
        session_state=ModelSwitchSessionStateV3(
            current=RouteIdentityV3("groq", "groq-1"),
            turns_on_current=5,
            turns_since_switch=5,
        ),
        switch_advantage_score=0.01,
    )
)
assert explicit.ok is True
assert calls[0][1]["provider"] == "gemini"

# Session stability is tested without an explicit user override.
class FakeCapabilitiesGeminiDefault(FakeCapabilities):
    def route_profile(self, *, voice_output, user_text="", force_local=False, preferred_provider=None):
        if force_local:
            return {"available": True, "data": {"provider": "local", "model": "local-7b"}}
        return {"available": True, "data": {"provider": "gemini", "model": "gemini-1"}}

stable_caps = FakeCapabilitiesGeminiDefault()
stable_gateway = IntelligenceGatewayV3(
    capability_service=stable_caps,
    fabric_executor=fake_executor,
)

calls.clear()
stable = stable_gateway.execute(
    IntelligenceGatewayRequestV3(
        execution_payload={"opaque": "stable"},
        candidates=candidates,
        policy_request=ModelPolicyRequest(
            user_text="stay",
            task_type="chat",
        ),
        session_state=ModelSwitchSessionStateV3(
            current=RouteIdentityV3("groq", "groq-1"),
            turns_on_current=5,
            turns_since_switch=5,
        ),
        switch_advantage_score=0.01,
    )
)
assert stable.ok is True
assert calls[0][1]["provider"] == "groq"

# Executor exception updates health and returns a traced failure.
def failing_executor(payload, route):
    raise TimeoutError("fabric timed out")

gateway_fail = IntelligenceGatewayV3(
    capability_service=caps,
    fabric_executor=failing_executor,
)
failed = gateway_fail.execute(
    IntelligenceGatewayRequestV3(
        execution_payload={"opaque": "fail"},
        candidates=candidates,
        policy_request=ModelPolicyRequest(
            user_text="x",
            task_type="chat",
        ),
    )
)
assert failed.ok is False
assert failed.blocked is False
assert failed.error_code == "timeout"
assert failed.trace["status"] == "failed"
health = gateway_fail.provider_health.snapshot("groq")
assert health.total_failures == 1

# No direct import of existing Fabric execution owner: binding remains separate.
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        mod = node.module or ""
        assert not mod.startswith("runtime.aura_fabric_http_gateway")
        assert not mod.startswith("runtime.aura_fabric_live_provider_adapters")
        assert not mod.startswith("runtime.aura_fabric_resilience")
    elif isinstance(node, ast.Import):
        for alias in node.names:
            assert not alias.name.startswith("runtime.aura_fabric_http_gateway")
            assert not alias.name.startswith("runtime.aura_fabric_live_provider_adapters")
            assert not alias.name.startswith("runtime.aura_fabric_resilience")

print("PASS AURA v3 IntelligenceGatewayV3 isolated invariant")
