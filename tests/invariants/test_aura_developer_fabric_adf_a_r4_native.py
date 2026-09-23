from pathlib import Path
import sys
import tempfile

ROOT = Path(r"C:\AURA GPT version").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_developer_fabric import DeveloperFabricPolicy, ROADMAP_OVERLAY, build_task_plan, build_workspace_context_pack
from runtime.aura_fabric_gateway import (
    FabricRegistry, GATEWAY_CONTRACT, ModelCapabilities, ModelDescriptor,
    Protocol, ProviderDescriptor, RouteRequest
)

policy = DeveloperFabricPolicy(workspace_root=ROOT)

assert policy.mode == "native_gateway"
assert policy.read_only_default is True
assert policy.require_explicit_apply_approval is True
assert policy.require_transaction_backup is True
assert policy.require_test_before_apply is True
assert policy.provider_calls_require_policy_gate is True
assert policy.can_execute("read") is True
assert policy.can_execute("apply") is False
assert policy.can_execute("apply", explicitly_approved=True) is True
assert policy.can_execute("provider_call") is False
assert policy.can_execute("provider_call", provider_policy_approved=True) is True

inside = ROOT / "runtime" / "aura_fabric_gateway.py"
assert policy.normalize(inside) == inside.resolve()

outside = Path(tempfile.gettempdir()) / "aura-adf-outside-test"
try:
    policy.normalize(outside)
except PermissionError:
    pass
else:
    raise AssertionError("outside-workspace path must be denied")

plan = build_task_plan(task_id="adf-native", objective="verify native fabric gateway", workspace_root=ROOT)
assert plan.mode == "native_gateway"
assert "route_plan" in plan.stages
assert "approval_gate" in plan.stages
assert "rollback_guard" in plan.stages

ctx = build_workspace_context_pack(
    workspace_id="ws_aura_main",
    project_name="AURA v2.0",
    root_path=ROOT,
    last_action="AURA v1.3.0 certified",
    next_action="ADF-A R2 native clean-room gateway",
)
assert ctx["gateway"]["implementation"] == "AURA Fabric Gateway"
assert ctx["gateway"]["clean_room"] is True

r = FabricRegistry()
r.register_provider(ProviderDescriptor(
    provider_id="local",
    display_name="Local Test Provider",
    protocols=(Protocol.AURA_NATIVE, Protocol.OPENAI_RESPONSES),
    models=(ModelDescriptor(
        provider_id="local",
        model_id="coder-local",
        display_name="Coder Local",
        local=True,
        capabilities=ModelCapabilities(
            tools=True, reasoning=True, streaming=True, json_mode=True,
            max_context_tokens=131072
        ),
    ),),
    priority=10,
))
r.register_provider(ProviderDescriptor(
    provider_id="cloud",
    display_name="Cloud Test Provider",
    protocols=(Protocol.AURA_NATIVE, Protocol.OPENAI_RESPONSES),
    models=(ModelDescriptor(
        provider_id="cloud",
        model_id="coder-cloud",
        display_name="Coder Cloud",
        local=False,
        input_cost_per_million=1.0,
        output_cost_per_million=3.0,
        capabilities=ModelCapabilities(
            tools=True, reasoning=True, vision=True, streaming=True, json_mode=True,
            max_context_tokens=200000
        ),
    ),),
    priority=20,
))

decision = r.route(RouteRequest(
    protocol=Protocol.OPENAI_RESPONSES,
    require_tools=True,
    require_reasoning=True,
    prefer_local=True,
    min_context_tokens=100000,
))
assert decision.primary.slug == "local/coder-local"
assert decision.considered == 2

r.record_result("local/coder-local", success=False, latency_ms=5000)
r.record_result("local/coder-local", success=False, latency_ms=5000)
r.record_result("local/coder-local", success=False, latency_ms=5000)

decision2 = r.route(RouteRequest(
    protocol=Protocol.OPENAI_RESPONSES,
    require_tools=True,
    require_reasoning=True,
    prefer_local=True,
    min_context_tokens=100000,
))
assert decision2.primary.slug == "cloud/coder-cloud"

assert GATEWAY_CONTRACT["clean_room"] is True
assert GATEWAY_CONTRACT["external_code_dependency"] is False
assert "/v1/messages" in GATEWAY_CONTRACT["endpoints_planned"]
assert "/v1/responses" in GATEWAY_CONTRACT["endpoints_planned"]
assert ROADMAP_OVERLAY[0][0] == "ADF-A"
assert "v1.3.1" in ROADMAP_OVERLAY[-1][1]

print("[PASS] ADF-A R2 native clean-room Fabric Gateway foundation")
