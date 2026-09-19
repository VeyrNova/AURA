from __future__ import annotations

from dataclasses import dataclass
import ast
from pathlib import Path
import sys

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET = ROOT / "runtime" / "aura_hardware_capability_service_v3.py"
text = TARGET.read_text(encoding="utf-8")
tree = ast.parse(text)
compile(text, str(TARGET), "exec")

# No duplicated low-level hardware probes are allowed in the adapter.
for forbidden in (
    "nvidia-smi",
    "torch.cuda",
    "psutil",
    "Win32_VideoController",
    "GlobalMemoryStatusEx",
    "subprocess.run",
):
    assert forbidden not in text, forbidden

assert "class HardwareCapabilityServiceV3" in text
assert "ResourceGuardian.sample" in text
assert "SystemService.snapshot" in text
assert "LLMManager.local_model_catalog" in text
assert "adaptive_profile" in text

from runtime.aura_hardware_capability_service_v3 import HardwareCapabilityServiceV3

@dataclass
class FakeResourceSnapshot:
    ram_used_pct: float = 41.0
    ram_total_gb: float = 32.0
    ram_available_gb: float = 18.5
    vram_used_mb: float = 1200.0
    vram_total_mb: float = 8192.0
    gpu_name: str = "Fake GPU"

class FakeGuardian:
    def __init__(self):
        self.sample_calls = 0
        self.profile_calls = 0
        self.prepare_calls = 0

    def sample(self, *, include_ollama=False, force_gpu=False, ollama_model=None):
        self.sample_calls += 1
        return FakeResourceSnapshot()

    def llm_request_profile(self, *, voice_output, user_text="", force_local=False, preferred_provider=None):
        self.profile_calls += 1
        return {
            "provider": preferred_provider or ("local" if force_local else "groq"),
            "model": "fake-model",
            "voice_output": bool(voice_output),
        }

    def prepare_for_llm(self, profile=None):
        self.prepare_calls += 1
        raise AssertionError("read-only adapter must never call prepare_for_llm")

    def xtts_local_first_hot(self):
        return True

    def realtime_dialogue_ready(self, profile=None):
        return bool(profile)

class FakeSystem:
    def snapshot(self):
        return {"cpu_percent": 12.0, "ram_percent": 41.0}

class FakeLLM:
    def local_model_catalog(self, *, force=False):
        return (
            {"name": "llama3.2:3b", "details": {"parameter_size": "3.2B"}},
            {"name": "qwen2.5:7b", "details": {"parameter_size": "7.0B"}},
        )

    def remote_available(self, provider=None):
        if provider == "groq":
            return True
        if provider == "gemini":
            return False
        return True

class FakeHardwareRuntime:
    def diagnostics(self):
        return {
            "gl_renderer": "Intel Iris Xe",
            "compute_gpu": "NVIDIA Fake",
            "compute_vram_total_mb": 8192.0,
            "topology": "intel-display+nvidia-compute",
        }

guardian = FakeGuardian()
service = HardwareCapabilityServiceV3(
    resource_guardian=guardian,
    system_service=FakeSystem(),
    llm_manager=FakeLLM(),
    hardware_runtime=FakeHardwareRuntime(),
)

basic = service.snapshot()
assert basic["schema"] == "aura.hardware_capability_service.v3"
assert basic["read_only_adapter"] is True
assert basic["resource"]["available"] is True
assert basic["resource"]["data"]["ram_total_gb"] == 32.0
assert basic["system"]["available"] is True
assert basic["gpu_runtime"]["data"]["topology"] == "intel-display+nvidia-compute"
assert guardian.sample_calls == 1
assert guardian.profile_calls == 0
assert guardian.prepare_calls == 0

full = service.snapshot(
    include_route_profile=True,
    include_local_models=True,
    include_provider_availability=True,
    include_voice_residency=True,
    user_text="bonjour aura",
    preferred_provider="groq",
)
assert full["route_profile"]["data"]["provider"] == "groq"
assert len(full["local_models"]["data"]) == 2
assert full["providers"]["data"]["groq"] is True
assert full["providers"]["data"]["gemini"] is False
assert full["voice_residency"]["data"]["xtts_local_first_hot"] is True
assert full["voice_residency"]["data"]["realtime_dialogue_ready"] is True
assert guardian.prepare_calls == 0

# Public adapter must not expose destructive residency/model-preparation methods.
public_names = {
    n.name for n in tree.body
    if isinstance(n, ast.ClassDef) and n.name == "HardwareCapabilityServiceV3"
    for n in n.body if isinstance(n, ast.FunctionDef)
}
for forbidden_method in (
    "prepare_for_llm",
    "prepare_for_tts",
    "controlled_xtts_cuda_trial",
    "conditional_xtts_prewarm",
    "unload_model",
    "load_model",
):
    assert forbidden_method not in public_names, forbidden_method

print("PASS AURA v3 HardwareCapabilityServiceV3 invariant")
