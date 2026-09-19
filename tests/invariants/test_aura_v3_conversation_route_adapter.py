from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET = ROOT / "runtime" / "aura_v3_conversation_route_adapter.py"
text = TARGET.read_text(encoding="utf-8")
tree = ast.parse(text)
compile(text, str(TARGET), "exec")

# Isolated compatibility adapter only: no UI, provider HTTP, Fabric construction,
# retry loop, or direct legacy LLM generation.
for forbidden in (
    "ui.main_window",
    "build_production_service(",
    "GatewayService(",
    "execute_with_resilience(",
    "register_eligible_live_adapters(",
    "llm_manager.generate(",
    "llm_manager.generate_stream(",
    "requests.",
    "httpx.",
    "urllib.",
    "socket.",
    "subprocess.",
    "time.sleep(",
    "GroqAFGAdapter",
    "GeminiAFGAdapter",
    "OllamaAFGAdapter",
):
    assert forbidden not in text, forbidden

from runtime import aura_conversation_fabric_bridge as bridge
from runtime.aura_conversation_fabric_bridge import (
    apply_fabric_result_to_profile,
    fabric_metrics_from_result,
)
from runtime.aura_fabric_http_gateway import build_test_service
from runtime.aura_intelligence_gateway_composition_v3 import (
    compose_intelligence_gateway_v3,
)
from runtime.aura_v3_conversation_route_adapter import generate_conversation_v3

class FakeCapabilities:
    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model

    def route_profile(
        self,
        *,
        voice_output,
        user_text="",
        force_local=False,
        preferred_provider=None,
    ):
        provider = preferred_provider or self.provider
        return {
            "available": True,
            "data": {"provider": provider, "model": self.model},
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
        return {"available": True, "data": [{"name": self.model}]}

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

class FakeVoiceEngine:
    def xtts_model_loaded(self):
        return False

class FakeAuraCore:
    pass

service = build_test_service(
    include_failure_route=False,
    retries_per_model=1,
)
entries = tuple(service.catalog.entries())
assert entries
entry = entries[0]
provider_id = str(entry.provider_id)
public_id = str(entry.public_id)
route_slug = str(entry.slug)
assert bool(getattr(entry, "local", False)) is True

caps = FakeCapabilities("local", public_id)
composition = compose_intelligence_gateway_v3(
    capability_service=caps,
    service_provider=lambda: service,
    service_provider_kind="adapter-test",
)

core = FakeAuraCore()
core.intelligence_gateway_v3 = composition.gateway
core.voice_engine = FakeVoiceEngine()

original_get_service = bridge._get_service
original_service_slot = getattr(bridge, "_service", None)
bridge._get_service = lambda: service
try:
    profile = {
        "_aura_fabric_auto": True,
        "name": "adapter-invariant",
        "num_predict": 32,
        "temperature": 0.0,
        "num_ctx": 4096,
        "keep_alive": "5m",
    }
    result = generate_conversation_v3(
        core,
        [{"role": "user", "content": "adapter-v3-test"}],
        profile=profile,
        voice_response=False,
    )
finally:
    bridge._get_service = original_get_service

# The test must not instantiate the production singleton.
assert getattr(bridge, "_service", None) is original_service_slot

assert result["text"]
assert result["provider_id"] == provider_id
assert result["routed_model"] == route_slug
assert result["requested_model"] == route_slug
assert result["finish_reason"]
assert isinstance(result["attempts"], list)
assert result["latency_seconds"] >= 0.0
assert result["_aura_v3_adapter"]["schema"] == "aura.v3.conversation_route_adapter"
assert result["_aura_v3_trace"]["status"] == "completed"

# Existing UI post-processing contract must accept the adapter output unchanged.
legacy_profile = {
    "provider": "local",
    "model": "",
    "num_ctx": 4096,
    "num_predict": 32,
}
apply_fabric_result_to_profile(legacy_profile, result)
assert legacy_profile["model"] == route_slug
metrics = fabric_metrics_from_result(result, legacy_profile)
assert metrics.model == route_slug
assert metrics.output_tokens >= 0
assert metrics.total_seconds >= 0.0

# Session stability state is persisted on AuraCore only after a successful turn.
state = getattr(core, "_aura_v3_model_switch_session_state", None)
assert state is not None
assert state.current is not None
assert state.current.provider == "local"
assert state.turns_on_current == 1

# Second successful same-route turn increments residence counters.
bridge._get_service = lambda: service
try:
    result2 = generate_conversation_v3(
        core,
        [{"role": "user", "content": "adapter-v3-test-two"}],
        profile=profile,
        voice_response=False,
    )
finally:
    bridge._get_service = original_get_service

state2 = getattr(core, "_aura_v3_model_switch_session_state", None)
assert state2.current is not None
assert state2.current.key == state.current.key
assert state2.turns_on_current >= 2
assert state2.turns_since_switch >= 1
assert result2["routed_model"] == route_slug

# Static contract: adapter may reuse bridge helper + singleton seam, but it must
# not own production service construction or import live provider adapters.
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        mod = node.module or ""
        assert not mod.startswith("ui.")
        assert not mod.startswith("runtime.aura_fabric_live_provider_adapters")
        assert not mod.startswith("runtime.aura_fabric_resilience")
        assert not mod.startswith("runtime.aura_fabric_http_gateway")
    elif isinstance(node, ast.Import):
        for alias in node.names:
            assert not alias.name.startswith("ui.")
            assert not alias.name.startswith("runtime.aura_fabric_live_provider_adapters")
            assert not alias.name.startswith("runtime.aura_fabric_resilience")
            assert not alias.name.startswith("runtime.aura_fabric_http_gateway")

print("PASS AURA v3 conversation route adapter isolated invariant")
