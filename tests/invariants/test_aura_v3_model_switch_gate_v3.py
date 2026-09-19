from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET = ROOT / "runtime" / "aura_model_switch_gate_v3.py"
text = TARGET.read_text(encoding="utf-8")
tree = ast.parse(text)
compile(text, str(TARGET), "exec")

# The switch gate is pure policy. It must not perform probing, I/O, generation,
# provider calls, model lifecycle operations, or session persistence.
for forbidden in (
    "nvidia-smi",
    "torch.cuda",
    "psutil",
    "requests.",
    "httpx.",
    "subprocess.",
    "open(",
    "prepare_for_llm(",
    "load_model(",
    "unload_model(",
    "generate(",
    "generate_stream(",
):
    assert forbidden not in text, forbidden

from runtime.aura_model_switch_gate_v3 import (
    ModelSwitchGateV3,
    ModelSwitchPolicyV3,
    ModelSwitchRequestV3,
    ModelSwitchSessionStateV3,
    RouteIdentityV3,
)

gate = ModelSwitchGateV3()
groq = RouteIdentityV3("groq", "g1")
gemini = RouteIdentityV3("gemini", "g2")
local = RouteIdentityV3("local", "l7b")

# No active route -> proposed route is accepted.
first = gate.evaluate(
    ModelSwitchSessionStateV3(),
    ModelSwitchRequestV3(proposed=groq),
)
assert first.allow_switch is True
assert first.selected.key == groq.key
assert "NO_CURRENT_ROUTE" in first.reason_codes

# Same route -> stable, no switch event.
same = gate.evaluate(
    ModelSwitchSessionStateV3(current=groq, turns_on_current=5, turns_since_switch=5),
    ModelSwitchRequestV3(proposed=groq, advantage_score=1.0),
)
assert same.allow_switch is False
assert same.selected.key == groq.key
assert "SAME_ROUTE" in same.reason_codes

# Proposed ineligible route can never replace current.
bad = gate.evaluate(
    ModelSwitchSessionStateV3(current=groq, turns_on_current=5, turns_since_switch=5),
    ModelSwitchRequestV3(proposed=gemini, proposed_eligible=False, advantage_score=10.0),
)
assert bad.allow_switch is False
assert "PROPOSED_ROUTE_INELIGIBLE" in bad.reason_codes

# Current route becoming ineligible overrides stickiness immediately.
privacy = gate.evaluate(
    ModelSwitchSessionStateV3(current=groq, turns_on_current=1, turns_since_switch=0),
    ModelSwitchRequestV3(
        proposed=local,
        current_eligible=False,
        proposed_eligible=True,
        hard_constraint_requires_switch=True,
    ),
)
assert privacy.allow_switch is True
assert privacy.selected.key == local.key
assert "CURRENT_ROUTE_INELIGIBLE" in privacy.reason_codes

# Provider health failure also overrides stickiness.
health = gate.evaluate(
    ModelSwitchSessionStateV3(current=groq, turns_on_current=1, turns_since_switch=0),
    ModelSwitchRequestV3(proposed=gemini, current_unhealthy=True),
)
assert health.allow_switch is True
assert "CURRENT_ROUTE_UNHEALTHY" in health.reason_codes

# Explicit user preference is respected.
explicit = gate.evaluate(
    ModelSwitchSessionStateV3(current=groq, turns_on_current=1, turns_since_switch=0),
    ModelSwitchRequestV3(proposed=local, explicit_user_preference=True),
)
assert explicit.allow_switch is True
assert "EXPLICIT_USER_PREFERENCE" in explicit.reason_codes

# Recent switch + small advantage => keep current.
cooldown = gate.evaluate(
    ModelSwitchSessionStateV3(current=groq, turns_on_current=4, turns_since_switch=0),
    ModelSwitchRequestV3(proposed=gemini, advantage_score=0.50),
    ModelSwitchPolicyV3(
        min_turns_on_current=2,
        min_turns_between_switches=2,
        min_effective_advantage=0.15,
        emergency_advantage=0.90,
    ),
)
assert cooldown.allow_switch is False
assert cooldown.selected.key == groq.key
assert "SWITCH_COOLDOWN_ACTIVE" in cooldown.reason_codes

# New route residence period blocks ordinary oscillation.
residence = gate.evaluate(
    ModelSwitchSessionStateV3(current=groq, turns_on_current=1, turns_since_switch=4),
    ModelSwitchRequestV3(proposed=gemini, advantage_score=0.50),
)
assert residence.allow_switch is False
assert "MINIMUM_ROUTE_RESIDENCE" in residence.reason_codes

# Once stable, insufficient benefit keeps current.
small = gate.evaluate(
    ModelSwitchSessionStateV3(current=groq, turns_on_current=5, turns_since_switch=5),
    ModelSwitchRequestV3(
        proposed=gemini,
        advantage_score=0.20,
        switch_penalty=0.10,
    ),
)
assert small.allow_switch is False
assert "ADVANTAGE_TOO_SMALL" in small.reason_codes

# Warm candidate bonus can justify a switch without the gate inventing quality.
warm = gate.evaluate(
    ModelSwitchSessionStateV3(current=groq, turns_on_current=5, turns_since_switch=5),
    ModelSwitchRequestV3(
        proposed=local,
        advantage_score=0.10,
        switch_penalty=0.02,
        proposed_warm=True,
        warm_bonus=0.10,
    ),
)
assert warm.allow_switch is True
assert "ADVANTAGE_THRESHOLD_MET" in warm.reason_codes
assert "PROPOSED_ROUTE_WARM" in warm.reason_codes

# Exceptional externally supplied gain may override cooldown.
emergency = gate.evaluate(
    ModelSwitchSessionStateV3(current=groq, turns_on_current=0, turns_since_switch=0),
    ModelSwitchRequestV3(proposed=local, advantage_score=1.0),
)
assert emergency.allow_switch is True
assert "ADVANTAGE_THRESHOLD_MET" in emergency.reason_codes

# Gate must not contain scoring/routing/provider execution APIs.
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ModelSwitchGateV3")
methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
for forbidden_method in (
    "score",
    "rank",
    "route",
    "generate",
    "prepare_for_llm",
    "load_model",
    "unload_model",
    "save_session",
):
    assert forbidden_method not in methods

print("PASS AURA v3 ModelSwitchGateV3 invariant")
