from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET = ROOT / "runtime" / "aura_model_policy_engine_v3.py"
text = TARGET.read_text(encoding="utf-8")
tree = ast.parse(text)
compile(text, str(TARGET), "exec")

for forbidden in (
    "nvidia-smi",
    "torch.cuda",
    "psutil",
    "Win32_VideoController",
    "subprocess.run",
    "prepare_for_llm(",
    "prepare_for_tts(",
    "load_model(",
    "unload_model(",
):
    assert forbidden not in text, forbidden

from runtime.aura_model_policy_engine_v3 import ModelPolicyEngineV3, ModelPolicyRequest

class FakeCapabilities:
    def __init__(self, route_provider="groq", route_model="cloud-model", local_models=True):
        self.route_provider = route_provider
        self.route_model = route_model
        self.local_models = local_models
        self.force_local_seen = None
        self.preferred_seen = None

    def route_profile(self, *, voice_output, user_text="", force_local=False, preferred_provider=None):
        self.force_local_seen = force_local
        self.preferred_seen = preferred_provider
        provider = "local" if force_local and self.local_models else self.route_provider
        model = "local-7b" if provider == "local" else self.route_model
        return {"available": True, "data": {"provider": provider, "model": model}}

    def provider_availability(self):
        return {"available": True, "data": {"groq": True, "gemini": False, "any_remote": True}}

    def local_model_catalog(self, *, force=False):
        data = [{"name": "local-7b"}] if self.local_models else []
        return {"available": True, "data": data}

    def resource_snapshot(self, *, include_ollama=False, force_gpu=False):
        return {"available": True, "data": {"ram_available_gb": 12.0, "vram_total_mb": 8192.0}}

    def gpu_runtime_snapshot(self):
        return {"available": True, "data": {"topology": "intel-display+nvidia-compute"}}

caps = FakeCapabilities()
engine = ModelPolicyEngineV3(caps)

auto = engine.decide(ModelPolicyRequest(user_text="bonjour", mode="automatic"))
assert auto.blocked is False
assert auto.primary["provider"] == "groq"
assert "EXISTING_ROUTE_PRESERVED" in auto.reason_codes
assert caps.force_local_seen is False

local = engine.decide(ModelPolicyRequest(user_text="secret", mode="local_only"))
assert local.blocked is False
assert local.primary["provider"] == "local"
assert local.constraints["local_required"] is True
assert local.constraints["cloud_allowed"] is False
assert caps.force_local_seen is True

privacy = engine.decide(ModelPolicyRequest(user_text="privé", privacy="local_required"))
assert privacy.primary["provider"] == "local"
assert privacy.constraints["cloud_allowed"] is False

cloud = engine.decide(ModelPolicyRequest(user_text="vite", mode="cloud_preferred"))
assert cloud.primary["provider"] == "groq"
assert any(item["provider"] == "local" for item in cloud.fallback_chain)

preferred = engine.decide(ModelPolicyRequest(user_text="x", preferred_provider="groq"))
assert preferred.primary["provider"] == "groq"
assert "EXPLICIT_PROVIDER_AVAILABLE" in preferred.reason_codes

no_local_caps = FakeCapabilities(route_provider="groq", route_model="cloud-model", local_models=False)
no_local = ModelPolicyEngineV3(no_local_caps).decide(ModelPolicyRequest(mode="local_only"))
assert no_local.blocked is True
assert no_local.primary["provider"] == "blocked"
assert "NO_LOCAL_MODEL_AVAILABLE" in no_local.reason_codes

# Policy engine must not create runtime authorities or expose mutating APIs.
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ModelPolicyEngineV3")
methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
for name in (
    "prepare_for_llm",
    "load_model",
    "unload_model",
    "start_provider",
    "stop_provider",
):
    assert name not in methods

print("PASS AURA v3 ModelPolicyEngineV3 invariant")
