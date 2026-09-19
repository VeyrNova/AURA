from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET = ROOT / "runtime" / "aura_intelligence_gateway_composition_v3.py"
text = TARGET.read_text(encoding="utf-8")
tree = ast.parse(text)
compile(text, str(TARGET), "exec")

# Composition must not own Fabric construction/execution internals.
for forbidden in (
    "build_production_service(",
    "GatewayService(",
    "execute_with_resilience(",
    "register_eligible_live_adapters(",
    "requests.",
    "httpx.",
    "urllib.",
    "socket.",
    "subprocess.",
    "nvidia-smi",
    "torch.cuda",
    "psutil",
    "GroqAFGAdapter",
    "GeminiAFGAdapter",
    "OllamaAFGAdapter",
):
    assert forbidden not in text, forbidden

from runtime.aura_conversation_fabric_bridge import build_canonical_request
from runtime.aura_eligibility_filter_v3 import RouteCandidateV3
from runtime.aura_fabric_http_gateway import build_test_service
from runtime.aura_intelligence_gateway_composition_v3 import (
    build_production_intelligence_gateway_v3,
    compose_intelligence_gateway_v3,
)
from runtime.aura_intelligence_gateway_v3 import IntelligenceGatewayRequestV3
from runtime.aura_model_policy_engine_v3 import ModelPolicyRequest

class FakeCapabilities:
    def __init__(self, provider, model):
        self.provider = provider
        self.model = model

    def route_profile(self, *, voice_output, user_text="", force_local=False, preferred_provider=None):
        return {
            "available": True,
            "data": {"provider": self.provider, "model": self.model},
        }

    def provider_availability(self):
        return {
            "available": True,
            "data": {
                "groq": False,
                "gemini": False,
                "any_remote": False,
            },
        }

    def local_model_catalog(self, *, force=False):
        return {"available": True, "data": []}

    def resource_snapshot(self, *, include_ollama=False, force_gpu=False):
        return {
            "available": True,
            "data": {
                "ram_available_gb": 16.0,
                "vram_used_mb": 0.0,
                "vram_total_mb": 0.0,
            },
        }

    def gpu_runtime_snapshot(self):
        return {"available": True, "data": {}}

class CountingService:
    def __init__(self, inner):
        self.inner = inner
        self.execute_calls = 0
        self.last_request = None

    def execute(self, request):
        self.execute_calls += 1
        self.last_request = request
        return self.inner.execute(request)

# ----- injected composition path -----
test_service = build_test_service(include_failure_route=False, retries_per_model=1)
entry = tuple(test_service.catalog.entries())[0]
provider_id = str(entry.provider_id)
public_id = str(entry.public_id)
route_slug = str(entry.slug)

caps = FakeCapabilities(provider_id, public_id)
counting = CountingService(test_service)
provider_calls = {"count": 0}

def injected_provider():
    provider_calls["count"] += 1
    return counting

composition = compose_intelligence_gateway_v3(
    capability_service=caps,
    service_provider=injected_provider,
    service_provider_kind="test",
)

# Factory construction must be lazy.
assert provider_calls["count"] == 0
assert composition.service_provider_kind == "test"
assert composition.gateway.fabric_executor is composition.binding

request = build_canonical_request(
    [{"role": "user", "content": "composition-v3-test"}],
    profile={"num_predict": 24, "temperature": 0.0},
    model="unused-before-binding",
)

candidate = RouteCandidateV3(
    provider=provider_id,
    model=public_id,
    requires_network=False,
    supported_tasks=("chat",),
    metadata={"fabric_route_slug": route_slug},
)

result = composition.gateway.execute(
    IntelligenceGatewayRequestV3(
        execution_payload=request,
        candidates=(candidate,),
        policy_request=ModelPolicyRequest(
            user_text="composition-v3-test",
            task_type="chat",
            mode="automatic",
        ),
        correlation_id="composition-test",
    )
)

assert result.ok is True
assert result.blocked is False
assert result.provider == provider_id
assert result.model == route_slug
assert provider_calls["count"] == 1
assert counting.execute_calls == 1
assert counting.last_request.model == route_slug
assert request.model == "unused-before-binding"

# ----- production factory seam, monkeypatched to test service -----
from runtime import aura_conversation_fabric_bridge as bridge

# Fresh invariant process must not have instantiated the production singleton.
original_slot = getattr(bridge, "_service", None)
assert original_slot is None

original_get_service = bridge._get_service
counting2 = CountingService(
    build_test_service(include_failure_route=False, retries_per_model=1)
)
patched_calls = {"count": 0}

def patched_get_service():
    patched_calls["count"] += 1
    return counting2

bridge._get_service = patched_get_service
try:
    production_composition = build_production_intelligence_gateway_v3(
        capability_service=caps,
    )

    # Production composition must remain lazy and must not alter bridge._service.
    assert patched_calls["count"] == 0
    assert getattr(bridge, "_service", None) is None
    assert production_composition.service_provider_kind == "conversation_fabric_singleton"

    result2 = production_composition.gateway.execute(
        IntelligenceGatewayRequestV3(
            execution_payload=request,
            candidates=(candidate,),
            policy_request=ModelPolicyRequest(
                user_text="production-seam-test",
                task_type="chat",
                mode="automatic",
            ),
            correlation_id="production-seam-test",
        )
    )
    assert result2.ok is True
    assert patched_calls["count"] == 1
    assert counting2.execute_calls == 1
    assert getattr(bridge, "_service", None) is None
finally:
    bridge._get_service = original_get_service

# Static contract: only conversation_fabric_service_provider may reference the
# bridge, and no constructor call for a Fabric GatewayService is allowed.
functions = {}
class V(ast.NodeVisitor):
    def __init__(self):
        self.stack = []
    def visit_ClassDef(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()
    def visit_FunctionDef(self, node):
        functions[".".join(self.stack + [node.name])] = node
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()
V().visit(tree)

for name, node in functions.items():
    segment = ast.get_source_segment(text, node) or ""
    if "aura_conversation_fabric_bridge" in segment:
        assert name == "conversation_fabric_service_provider"

print("PASS AURA v3 IntelligenceGatewayCompositionV3 invariant")
