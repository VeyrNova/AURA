from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET = ROOT / "runtime" / "aura_fabric_execution_binding_v3.py"
text = TARGET.read_text(encoding="utf-8")
tree = ast.parse(text)
compile(text, str(TARGET), "exec")

# The binding is orchestration glue only.
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
    "register_eligible_live_adapters(",
    "time.sleep(",
    "prepare_for_llm(",
    "load_model(",
    "unload_model(",
):
    assert forbidden not in text, forbidden

from runtime.aura_conversation_fabric_bridge import build_canonical_request
from runtime.aura_fabric_execution_binding_v3 import AuraFabricExecutionBindingV3
from runtime.aura_fabric_http_gateway import build_test_service

# Existing in-process Fabric test service: EchoProviderAdapter only, no live
# provider registration and therefore no external network.
service = build_test_service(include_failure_route=False, retries_per_model=2)
entries = tuple(service.catalog.entries())
assert entries, "build_test_service must expose at least one catalog entry"

entry = entries[0]
route_slug = str(getattr(entry, "slug", "") or "")
provider_id = str(getattr(entry, "provider_id", "") or "")
assert route_slug and "/" in route_slug
assert provider_id

class CountingService:
    def __init__(self, inner):
        self.inner = inner
        self.execute_calls = 0
        self.last_request = None

    def execute(self, request):
        self.execute_calls += 1
        self.last_request = request
        return self.inner.execute(request)

counting = CountingService(service)
binding = AuraFabricExecutionBindingV3(service_provider=lambda: counting)

original = build_canonical_request(
    [{"role": "user", "content": "binding-v3-test"}],
    profile={"num_predict": 32, "temperature": 0.0},
    model="aura-test-original",
)
original_model = original.model

result = binding(
    original,
    {
        "provider": provider_id,
        "model": "ignored-by-binding",
        "metadata": {"fabric_route_slug": route_slug},
    },
)

assert counting.execute_calls == 1
assert counting.last_request is not original
assert original.model == original_model
assert counting.last_request.model == route_slug
assert result["ok"] is True
assert result["provider_id"] == provider_id
assert result["routed_model"] == route_slug
assert result["requested_model"] == route_slug
assert result["binding"]["exact_fabric_model"] == route_slug
assert isinstance(result["attempts"], list)
assert result["failover_count"] >= 0
assert result["latency_ms"] >= 0.0

# CanonicalRequest is genuinely frozen; the binding must clone, not mutate.
try:
    original.model = route_slug
    raise AssertionError("CanonicalRequest must be frozen")
except (FrozenInstanceError, AttributeError):
    pass

# No route guessing from provider/model display values is allowed.
try:
    binding(
        original,
        {"provider": provider_id, "model": route_slug},
    )
    raise AssertionError("exact Fabric metadata must be required")
except ValueError:
    pass

# Alternate exact-id key is accepted.
counting2 = CountingService(build_test_service(include_failure_route=False, retries_per_model=1))
binding2 = AuraFabricExecutionBindingV3(service_provider=lambda: counting2)
result2 = binding2(
    original,
    {
        "provider": provider_id,
        "metadata": {"fabric_model_id": route_slug},
    },
)
assert counting2.execute_calls == 1
assert result2["routed_model"] == route_slug

# Service provider must be injected; binding does not own/create production service.
try:
    AuraFabricExecutionBindingV3(service_provider=None)
    raise AssertionError("non-callable service provider must fail")
except TypeError:
    pass

# No direct imports of production owner/resilience/live adapters in binding.
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        mod = node.module or ""
        assert not mod.startswith("runtime.aura_fabric_http_gateway")
        assert not mod.startswith("runtime.aura_fabric_resilience")
        assert not mod.startswith("runtime.aura_fabric_live_provider_adapters")
    elif isinstance(node, ast.Import):
        for alias in node.names:
            assert not alias.name.startswith("runtime.aura_fabric_http_gateway")
            assert not alias.name.startswith("runtime.aura_fabric_resilience")
            assert not alias.name.startswith("runtime.aura_fabric_live_provider_adapters")

print("PASS AURA v3 FabricExecutionBindingV3 isolated invariant")
