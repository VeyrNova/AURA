from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET = ROOT / "runtime" / "aura_eligibility_filter_v3.py"
text = TARGET.read_text(encoding="utf-8")
tree = ast.parse(text)
compile(text, str(TARGET), "exec")

# This layer may only consume supplied facts. It must not probe or mutate runtime.
for forbidden in (
    "nvidia-smi",
    "torch.cuda",
    "psutil",
    "Win32_",
    "subprocess.run",
    "requests.",
    "httpx.",
    "prepare_for_llm(",
    "load_model(",
    "unload_model(",
    "generate(",
    "generate_stream(",
):
    assert forbidden not in text, forbidden

from runtime.aura_eligibility_filter_v3 import (
    EligibilityFilterV3,
    EligibilityRequestV3,
    RouteCandidateV3,
)

f = EligibilityFilterV3()

candidates = [
    RouteCandidateV3(
        provider="groq",
        model="cloud-a",
        requires_network=True,
        context_window=32768,
        supported_tasks=("chat", "code"),
    ),
    RouteCandidateV3(
        provider="gemini",
        model="cloud-b",
        requires_network=True,
        context_window=65536,
        supported_tasks=("chat",),
    ),
    RouteCandidateV3(
        provider="local",
        model="local-7b",
        uses_local_gpu=True,
        context_window=8192,
        min_ram_gb=4.0,
        min_vram_mb=5000.0,
        supported_tasks=("chat", "code"),
    ),
]

resource = {
    "available": True,
    "data": {
        "ram_available_gb": 12.0,
        "vram_used_mb": 1000.0,
        "vram_total_mb": 8192.0,
    },
}
providers = {
    "available": True,
    "data": {"groq": True, "gemini": False, "any_remote": True},
}

# Automatic mode: preserve input order among survivors, no scoring.
auto = f.filter(
    candidates,
    EligibilityRequestV3(task_type="chat"),
    resource_snapshot=resource,
    provider_availability=providers,
    installed_local_models=("local-7b",),
)
assert [x.provider for x in auto.eligible] == ["groq", "local"]
assert auto.fail_closed is False
assert any(
    r.provider == "gemini" and "PROVIDER_UNAVAILABLE" in r.reason_codes
    for r in auto.rejected
)

# Local-only is fail-closed with respect to cloud.
local = f.filter(
    candidates,
    EligibilityRequestV3(task_type="chat", mode="local_only"),
    resource_snapshot=resource,
    provider_availability=providers,
    installed_local_models=("local-7b",),
)
assert [x.provider for x in local.eligible] == ["local"]
assert all(x.provider == "local" for x in local.eligible)
assert any(
    r.provider == "groq" and "LOCAL_REQUIRED" in r.reason_codes
    for r in local.rejected
)

# Network disabled removes remote candidates.
offline = f.filter(
    candidates,
    EligibilityRequestV3(task_type="chat", network_allowed=False),
    resource_snapshot=resource,
    provider_availability=providers,
    installed_local_models=("local-7b",),
)
assert [x.provider for x in offline.eligible] == ["local"]

# Context is a hard constraint.
context = f.filter(
    candidates,
    EligibilityRequestV3(task_type="chat", required_context_tokens=16000),
    resource_snapshot=resource,
    provider_availability=providers,
    installed_local_models=("local-7b",),
)
assert any(
    r.provider == "local" and "CONTEXT_WINDOW_TOO_SMALL" in r.reason_codes
    for r in context.rejected
)

# XTTS reserve can make an otherwise fitting GPU model ineligible.
xtts = f.filter(
    candidates,
    EligibilityRequestV3(
        task_type="chat",
        mode="local_only",
        xtts_hot=True,
        preserve_xtts=True,
        xtts_vram_reserve_mb=2500.0,
    ),
    resource_snapshot=resource,
    provider_availability=providers,
    installed_local_models=("local-7b",),
)
assert xtts.fail_closed is True
assert xtts.error_code == "NO_ELIGIBLE_CANDIDATES"
assert any(
    r.provider == "local" and "INSUFFICIENT_VRAM_HEADROOM" in r.reason_codes
    for r in xtts.rejected
)

# Known local catalog is authoritative when supplied.
missing_model = f.filter(
    [RouteCandidateV3(provider="local", model="missing-9b")],
    EligibilityRequestV3(mode="local_only"),
    installed_local_models=("local-7b",),
)
assert missing_model.fail_closed is True
assert "LOCAL_MODEL_NOT_INSTALLED" in missing_model.rejected[0].reason_codes

# Unsupported task is rejected.
task = f.filter(
    [RouteCandidateV3(provider="local", model="local-7b", supported_tasks=("chat",))],
    EligibilityRequestV3(task_type="code", mode="local_only"),
    installed_local_models=("local-7b",),
)
assert task.fail_closed is True
assert "TASK_UNSUPPORTED" in task.rejected[0].reason_codes

# No hidden score/rank method: this component only filters.
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "EligibilityFilterV3")
methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
for forbidden_method in ("score", "rank", "select_best", "generate", "prepare_for_llm"):
    assert forbidden_method not in methods

print("PASS AURA v3 EligibilityFilterV3 invariant")
