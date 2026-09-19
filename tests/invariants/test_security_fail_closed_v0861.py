from __future__ import annotations
import sys
from pathlib import Path

def check(root: Path, ui: Path | None, baseline: dict, *, portable: bool = False) -> dict:
    sys.path.insert(0, str(root))
    from security.policy_engine import SecurityPolicyEngine

    empty = SecurityPolicyEngine(granted_permissions=[])
    unknown = empty.authorize("__AURA_CI_UNKNOWN_ACTION__")
    missing = empty.authorize("LIST_MEMORIES")

    default = SecurityPolicyEngine()
    critical = default.authorize("DISABLE_SECURITY", user_confirmed=True)

    params_text = (root / "security" / "policy_engine.py").read_text(encoding="utf-8-sig", errors="replace")
    checks = {
        "unknown_denied": unknown.allowed is False,
        "unknown_fail_closed_reason": "fail closed" in unknown.reason.casefold(),
        "missing_permission_denied": missing.allowed is False,
        "critical_denied_even_confirmed": critical.allowed is False,
        "parameter_aware_debt_still_visible": "del params" in params_text,
    }
    return {
        "name": "security_fail_closed",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "blocking": True,
        "checks": checks,
        "note": "parameter_aware_debt_still_visible is intentionally frozen until v0.8.6.3.",
    }
