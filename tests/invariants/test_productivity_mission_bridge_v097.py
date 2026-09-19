from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.productivity_mission_bridge_v097 import (
    ProductivityMissionToolExecutorV097,
    resolve_productivity_target_v097,
    resolve_existing_security_engine_v097,
    build_productivity_mission_engine_v097,
    ensure_productivity_mission_engine_v097,
)


def _tc(tool_name="", action="", params=None):
    return SimpleNamespace(
        tool_name=tool_name,
        action=action,
        params=dict(params or {}),
    )


assert resolve_productivity_target_v097(_tc("email", "search")) == (
    "email.provider",
    "email.search",
)
assert resolve_productivity_target_v097(_tc("calendar.provider", "create_event")) == (
    "calendar.provider",
    "calendar.create_event",
)
assert resolve_productivity_target_v097(_tc("contacts.search", "")) == (
    "contacts.provider",
    "contacts.search",
)
assert resolve_productivity_target_v097(_tc("files", "read")) == (
    "files.provider",
    "files.read",
)
assert resolve_productivity_target_v097(_tc("notifications", "list")) == (
    "notifications.provider",
    "notifications.list",
)
assert resolve_productivity_target_v097(_tc("browser", "search")) == (
    "browser.provider",
    "browser.search",
)
assert resolve_productivity_target_v097(_tc("browser", "captcha_bypass")) is None
assert resolve_productivity_target_v097(_tc("unknown", "run")) is None


class FakeResult:
    ok = True
    status = "ok"
    output = {"accepted": True}


class FakeRegistry:
    def __init__(self):
        self.requests = []

    def execute_integration(self, request, user_confirmed=False):
        self.requests.append((request, bool(user_confirmed)))
        return FakeResult()


security = object()
registry = FakeRegistry()
context = SimpleNamespace(registry=registry)
dispatcher = SimpleNamespace(context=context)
core = SimpleNamespace(security_engine=security)

assert resolve_existing_security_engine_v097(core, dispatcher) is security

executor = ProductivityMissionToolExecutorV097(registry=registry)
result = executor(_tc("email", "search", {"query": {"text": "AURA"}}))
assert result == {"accepted": True}
assert len(registry.requests) == 1
request, confirmed = registry.requests[0]
assert request.provider_id == "email.provider"
assert request.capability_id == "email.search"
assert confirmed is False

engine = build_productivity_mission_engine_v097(
    security_engine=security,
    registry=registry,
)
assert engine.security_engine is security
assert engine.tool_executor is not None
assert type(engine.tool_executor).__name__ == "ProductivityMissionToolExecutorV097"

engine2 = ensure_productivity_mission_engine_v097(core, dispatcher)
assert engine2.security_engine is security
assert core._productivity_mission_engine_v097 is engine2
assert ensure_productivity_mission_engine_v097(core, dispatcher) is engine2

registry.requests.clear()
result2 = engine2.tool_executor(_tc("calendar", "free_busy", {"start": "2026-08-28"}))
assert isinstance(result2, dict)
assert result2.get("accepted") is True
assert len(registry.requests) == 1
request2, confirmed2 = registry.requests[0]
assert request2.provider_id == "calendar.provider"
assert request2.capability_id == "calendar.free_busy"
assert confirmed2 is False

print("[PASS] Productivity Mission bridge v0.9.7")
print("[PASS] productivity capability targets normalize deterministically")
print("[PASS] unsafe non-certified browser capabilities fail closed")
print("[PASS] existing security engine identity is reused")
print("[PASS] IntegrationMissionToolAdapter remains execution authority")
print("[PASS] MissionEngine is composed with the productivity executor")
print("[PASS] user_confirmed is never forced true by the bridge")
print("[PASS] no provider/network/security backend is duplicated")
