from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from security.permissions import ACTION_POLICIES
from security.policy_engine import SecurityPolicyEngine
from security.policy_engine_v2 import PolicyDecisionV2, normalize_legacy_decision


def _make_engine():
    return SecurityPolicyEngine(None, granted_permissions=[])


engine = _make_engine()

unknown = engine.authorize("__AURA_V0866_UNKNOWN_ACTION__", {})
normalized = normalize_legacy_decision("__AURA_V0866_UNKNOWN_ACTION__", unknown)
assert normalized.decision == PolicyDecisionV2.DENY, normalized

if "DISABLE_SECURITY" in ACTION_POLICIES:
    critical = engine.authorize("DISABLE_SECURITY", {})
    normalized_critical = normalize_legacy_decision("DISABLE_SECURITY", critical)
    assert normalized_critical.decision != PolicyDecisionV2.ALLOW, normalized_critical

if "DELETE_FILE" in ACTION_POLICIES:
    destructive = engine.authorize("DELETE_FILE", {"path": "__aura_v0866_probe__"})
    normalized_destructive = normalize_legacy_decision("DELETE_FILE", destructive)
    assert normalized_destructive.decision != PolicyDecisionV2.ALLOW, normalized_destructive

import security.policy_engine as pe

_original = pe._SecurityPolicyEngineV1.authorize
try:
    def _boom(self, action, params):
        raise RuntimeError("v0866 injected evaluator failure")

    pe._SecurityPolicyEngineV1.authorize = _boom
    injected = _make_engine().authorize("DISABLE_SECURITY", {})
    normalized_injected = normalize_legacy_decision("DISABLE_SECURITY", injected)
    assert normalized_injected.decision == PolicyDecisionV2.DENY, normalized_injected
finally:
    pe._SecurityPolicyEngineV1.authorize = _original

print("[PASS] SecurityPolicyEngine v2 fail-closed invariant")
raise SystemExit(0)
