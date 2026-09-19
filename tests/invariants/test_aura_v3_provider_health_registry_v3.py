from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET = ROOT / "runtime" / "aura_provider_health_registry_v3.py"
text = TARGET.read_text(encoding="utf-8")
tree = ast.parse(text)
compile(text, str(TARGET), "exec")

for forbidden in (
    "requests.",
    "httpx.",
    "urllib.",
    "socket.",
    "subprocess.",
    "generate(",
    "generate_stream(",
    "prepare_for_llm(",
    "load_model(",
    "unload_model(",
    "sqlite",
    "write_text(",
    "write_bytes(",
):
    assert forbidden not in text, forbidden

from runtime.aura_provider_health_registry_v3 import (
    ProviderHealthPolicyV3,
    ProviderHealthRegistryV3,
)

class Clock:
    def __init__(self):
        self.now = 1000.0
    def __call__(self):
        return self.now
    def advance(self, seconds):
        self.now += float(seconds)

clock = Clock()
registry = ProviderHealthRegistryV3(
    ProviderHealthPolicyV3(
        degraded_after_failures=1,
        cooldown_after_failures=3,
        cooldown_seconds=30,
        rate_limit_cooldown_seconds=60,
        recovery_successes=1,
        max_error_history=3,
    ),
    monotonic_clock=clock,
)

# Unknown providers may be probed.
unknown = registry.snapshot("groq")
assert unknown.state == "unknown"
assert unknown.eligible is True
assert "UNKNOWN_ALLOWED_FOR_PROBE" in unknown.reason_codes

# A successful call establishes healthy state.
healthy = registry.record_success("groq", latency_ms=42.5)
assert healthy.state == "healthy"
assert healthy.eligible is True
assert healthy.last_latency_ms == 42.5

# Transient failure degrades but remains eligible.
degraded = registry.record_failure("groq", error_code="timeout")
assert degraded.state == "degraded"
assert degraded.eligible is True
assert degraded.consecutive_failures == 1

# Repeated transient failures open a cooldown.
registry.record_failure("groq", error_code="server_error")
cooldown = registry.record_failure("groq", error_code="network")
assert cooldown.state == "cooldown"
assert cooldown.eligible is False
assert cooldown.cooldown_remaining_seconds == 30.0

# Expired cooldown becomes degraded, not silently healthy.
clock.advance(31)
expired = registry.snapshot("groq")
assert expired.state == "degraded"
assert expired.eligible is True
assert "BLOCK_EXPIRED_AWAITING_RECOVERY" in expired.reason_codes

# Real success confirms recovery.
recovered = registry.record_success("groq", latency_ms=20)
assert recovered.state == "healthy"
assert recovered.consecutive_failures == 0

# Rate limit uses explicit retry-after and blocks routing.
limited = registry.record_failure(
    "gemini",
    error_code="429",
    retry_after_seconds=12,
    metadata={"authorization": "secret", "region": "eu"},
)
assert limited.state == "rate_limited"
assert limited.eligible is False
assert limited.cooldown_remaining_seconds == 12.0
assert limited.error_history[-1]["metadata"]["authorization"] == "<redacted>"

clock.advance(13)
post_limit = registry.snapshot("gemini")
assert post_limit.state == "degraded"
assert post_limit.eligible is True

# Hard auth/config failures fail closed until explicit recovery/reset.
hard = registry.record_failure("provider-x", error_code="invalid_api_key")
assert hard.state == "unavailable"
assert hard.eligible is False
assert hard.blocked_until_monotonic is None

# Explicit success can recover once credentials/config have been fixed externally.
hard_recovered = registry.record_success("provider-x")
assert hard_recovered.state == "healthy"
assert hard_recovered.eligible is True

# Manual unavailable state is supported without provider execution.
manual = registry.mark_unavailable("provider-y", reason_code="maintenance")
assert manual.state == "unavailable"
assert manual.eligible is False

# Error history is bounded.
for _ in range(6):
    registry.record_failure("history", error_code="timeout")
assert len(registry.snapshot("history").error_history) == 3

# Availability map is neutral health only, not ranking.
availability = registry.availability_map()
assert isinstance(availability["groq"], bool)
assert isinstance(availability["gemini"], bool)

# Registry must not expose selection/scoring/generation/lifecycle methods.
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ProviderHealthRegistryV3")
methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
for forbidden_method in (
    "rank",
    "score",
    "select_provider",
    "generate",
    "load_model",
    "unload_model",
):
    assert forbidden_method not in methods

print("PASS AURA v3 ProviderHealthRegistryV3 invariant")
