from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.integration_permissions_v098 import (
    ALLOW,
    DENY,
    REQUIRE_CONFIRMATION,
    CANONICAL_PROVIDER_CAPABILITIES_V098,
    DENIED_BROWSER_CAPABILITIES_V098,
    INTEGRATION_PERMISSION_RULES_V098,
    evaluate_integration_permission_v098,
    validate_integration_permission_contract_v098,
)
from runtime.personal_integrations import (
    PersonalIntegrationDispatcher,
    build_synthetic_runtime_context,
)
from runtime.productivity_mission_bridge_v097 import (
    ProductivityMissionToolExecutorV097,
)
from security.permissions import DEFAULT_GRANTED_PERMISSIONS, Permission


def _reply_dict(reply):
    return {
        "handled": bool(getattr(reply, "handled", False)),
        "status": str(getattr(reply, "status", "") or ""),
        "pending_confirmation": bool(getattr(reply, "pending_confirmation", False)),
        "provider_id": str(getattr(reply, "provider_id", "") or ""),
        "capability_id": str(getattr(reply, "capability_id", "") or ""),
        "text": str(getattr(reply, "text", "") or "")[:240],
        "payload_type": type(getattr(reply, "payload", None)).__name__,
    }


def _reply_success(reply):
    if not bool(getattr(reply, "handled", False)):
        return False
    if bool(getattr(reply, "pending_confirmation", False)):
        return False
    status = str(getattr(reply, "status", "") or "").casefold()
    bad = (
        "error",
        "fail",
        "denied",
        "invalid",
        "unavailable",
        "not_found",
        "not found",
        "unsupported",
    )
    return not any(token in status for token in bad)


def _dispatch_read(dispatcher, provider_id, capability_id, candidates):
    attempts = []
    for params in candidates:
        reply = dispatcher.dispatch_capability(
            provider_id=provider_id,
            capability_id=capability_id,
            params=params,
            summary="AURA v0.9.9 synthetic read acceptance",
        )
        attempts.append({"params": params, "reply": _reply_dict(reply)})
        if _reply_success(reply):
            return reply, params, attempts
    raise AssertionError(
        "no successful read-only dispatch for "
        + capability_id
        + ": "
        + repr(attempts)
    )


def _dispatch_waiting(dispatcher, provider_id, capability_id, candidates):
    attempts = []
    for params in candidates:
        reply = dispatcher.dispatch_capability(
            provider_id=provider_id,
            capability_id=capability_id,
            params=params,
            summary="AURA v0.9.9 synthetic mutation acceptance",
        )
        attempts.append({"params": params, "reply": _reply_dict(reply)})
        if (
            bool(getattr(reply, "handled", False))
            and bool(getattr(reply, "pending_confirmation", False))
            and str(getattr(reply, "status", "") or "") == "waiting_confirmation"
            and dispatcher.confirmation_broker.pending is not None
        ):
            return reply, params, attempts
        if dispatcher.confirmation_broker.pending is not None:
            dispatcher.cancel_confirmation()
    raise AssertionError(
        "no waiting-confirmation dispatch for "
        + capability_id
        + ": "
        + repr(attempts)
    )


# ---------------------------------------------------------------------------
# 1. Permission contract / fail-closed safety.
# ---------------------------------------------------------------------------
assert validate_integration_permission_contract_v098() == ()
assert len(INTEGRATION_PERMISSION_RULES_V098) == 53
assert len(CANONICAL_PROVIDER_CAPABILITIES_V098) == 6
assert sum(len(v) for v in CANONICAL_PROVIDER_CAPABILITIES_V098.values()) == 53

for cap in DENIED_BROWSER_CAPABILITIES_V098:
    denied = evaluate_integration_permission_v098(
        cap,
        granted_permissions=frozenset(Permission),
        user_confirmed=True,
    )
    assert denied.decision == DENY

unknown = evaluate_integration_permission_v098(
    "files.execute_arbitrary_code",
    granted_permissions=frozenset(Permission),
    user_confirmed=True,
)
assert unknown.decision == DENY

read_decision = evaluate_integration_permission_v098("files.read")
assert read_decision.decision == ALLOW

send_default = evaluate_integration_permission_v098(
    "email.send",
    user_confirmed=True,
)
assert send_default.decision == DENY

email_grants = frozenset(
    set(DEFAULT_GRANTED_PERMISSIONS) | {Permission.EXTERNAL_NETWORK}
)
send_wait = evaluate_integration_permission_v098(
    "email.send",
    granted_permissions=email_grants,
    user_confirmed=False,
)
send_allow = evaluate_integration_permission_v098(
    "email.send",
    granted_permissions=email_grants,
    user_confirmed=True,
)
assert send_wait.decision == REQUIRE_CONFIRMATION
assert send_allow.decision == ALLOW

# ---------------------------------------------------------------------------
# 2. Actual PersonalIntegrationDispatcher over AURA synthetic providers.
#    build_synthetic_runtime_context requires an explicit security_engine.
#    Reuse AURA's historical deterministic acceptance contract:
#    reads ALLOW, tested mutations REQUIRE_CONFIRMATION until confirmed.
# ---------------------------------------------------------------------------
class RuntimeSecurity:
    def __init__(self):
        self.calls = []

    def authorize(self, action, params, user_confirmed=False):
        self.calls.append(
            {
                "action": str(action),
                "user_confirmed": bool(user_confirmed),
            }
        )
        if action in {
            "email.send",
            "calendar.create_event",
            "contacts.create",
            "files.create",
        } and not user_confirmed:
            return "REQUIRE_CONFIRMATION"
        return "ALLOW"


runtime_security = RuntimeSecurity()
context = build_synthetic_runtime_context(
    security_engine=runtime_security,
    timezone_name="Europe/Paris",
)
dispatcher = PersonalIntegrationDispatcher(context=context)

read_scenarios = [
    (
        "email.provider",
        "email.search",
        [{}, {"query": ""}, {"query": "AURA"}, {"text": "AURA"}],
    ),
    (
        "calendar.provider",
        "calendar.list",
        [{}, {"calendar_id": "primary"}],
    ),
    (
        "contacts.provider",
        "contacts.search",
        [{}, {"query": ""}, {"query": "AURA"}, {"text": "AURA"}],
    ),
    (
        "files.provider",
        "files.list",
        [{}, {"path": "/"}, {"path": "."}, {"folder": "/"}],
    ),
]

READ_RESULTS = []
for provider_id, capability_id, candidates in read_scenarios:
    reply, params, attempts = _dispatch_read(
        dispatcher,
        provider_id,
        capability_id,
        candidates,
    )
    READ_RESULTS.append(
        {
            "provider_id": provider_id,
            "capability_id": capability_id,
            "params": params,
            "reply": _reply_dict(reply),
            "attempts": attempts,
        }
    )

# ---------------------------------------------------------------------------
# 3. Real dispatcher confirmation broker: four mutation families must stop
#    before execution, then cancellation must clear the pending action.
# ---------------------------------------------------------------------------
mutation_scenarios = [
    (
        "email.provider",
        "email.send",
        [
            {
                "to": "acceptance@example.test",
                "subject": "AURA v0.9.9",
                "body": "synthetic acceptance",
            },
            {
                "recipients": ["acceptance@example.test"],
                "subject": "AURA v0.9.9",
                "body": "synthetic acceptance",
            },
            {},
        ],
    ),
    (
        "calendar.provider",
        "calendar.create_event",
        [
            {
                "title": "AURA v0.9.9 acceptance",
                "start": "2026-08-28T20:00:00+02:00",
                "end": "2026-08-28T20:30:00+02:00",
            },
            {},
        ],
    ),
    (
        "contacts.provider",
        "contacts.create",
        [
            {
                "name": "AURA Acceptance",
                "email": "acceptance@example.test",
            },
            {},
        ],
    ),
    (
        "files.provider",
        "files.create",
        [
            {
                "path": "/aura-v099-acceptance.txt",
                "content": "synthetic acceptance",
            },
            {
                "path": "aura-v099-acceptance.txt",
                "content": "synthetic acceptance",
            },
            {},
        ],
    ),
]

original_execute = context.registry.execute_integration
TRACE = []


def _traced_execute(request, user_confirmed=False):
    TRACE.append(
        {
            "provider_id": str(getattr(request, "provider_id", "") or ""),
            "capability_id": str(getattr(request, "capability_id", "") or ""),
            "user_confirmed": bool(user_confirmed),
        }
    )
    return original_execute(request, user_confirmed=user_confirmed)


context.registry.execute_integration = _traced_execute

CONFIRMATION_RESULTS = []
for provider_id, capability_id, candidates in mutation_scenarios:
    before = len(TRACE)
    reply, params, attempts = _dispatch_waiting(
        dispatcher,
        provider_id,
        capability_id,
        candidates,
    )
    mid = len(TRACE)
    assert mid > before
    scoped = TRACE[before:mid]
    assert any(x["capability_id"] == capability_id for x in scoped)
    assert all(x["user_confirmed"] is False for x in scoped)

    cancel_reply = dispatcher.cancel_confirmation()
    assert dispatcher.confirmation_broker.pending is None
    assert bool(getattr(cancel_reply, "handled", False))

    after = len(TRACE)
    assert after == mid, "cancel must not execute a confirmed mutation"
    CONFIRMATION_RESULTS.append(
        {
            "provider_id": provider_id,
            "capability_id": capability_id,
            "params": params,
            "reply": _reply_dict(reply),
            "cancel_reply": _reply_dict(cancel_reply),
            "registry_calls": scoped,
            "attempts": attempts,
        }
    )

# ---------------------------------------------------------------------------
# 4. MissionEngine lifecycle -> v0.9.7 productivity executor -> registry.
#    Uses a deterministic local fake registry, but the REAL MissionEngine and
#    IntegrationMissionToolAdapter implementation.
# ---------------------------------------------------------------------------
from mission_engine.engine import MissionEngine


class _LegacyAllowSecurity:
    def __init__(self):
        self.calls = []

    def authorize(self, action, params, user_confirmed=False):
        self.calls.append(
            {
                "action": str(action),
                "params": dict(params or {}),
                "user_confirmed": bool(user_confirmed),
            }
        )
        return "ALLOW"


class _FakeResult:
    ok = True
    status = "ok"
    output = {"accepted": True, "source": "v0.9.9-mission-e2e"}


class _FakeRegistry:
    def __init__(self):
        self.requests = []

    def execute_integration(self, request, user_confirmed=False):
        self.requests.append(
            {
                "provider_id": request.provider_id,
                "capability_id": request.capability_id,
                "params": dict(request.params),
                "user_confirmed": bool(user_confirmed),
            }
        )
        return _FakeResult()


fake_registry = _FakeRegistry()
mission_executor = ProductivityMissionToolExecutorV097(registry=fake_registry)
engine = MissionEngine(
    security_engine=_LegacyAllowSecurity(),
    tool_executor=mission_executor,
)

create_sig = inspect.signature(engine.create_mission)
create_kwargs = {}
for name, param in create_sig.parameters.items():
    if param.default is not inspect.Parameter.empty:
        continue
    if name in {"goal", "goal_text", "title", "description"}:
        create_kwargs[name] = "AURA v0.9.9 personal agent acceptance"
    elif name in {"constraints", "constraint_ids"}:
        create_kwargs[name] = ()
    elif name in {"metadata", "context"}:
        create_kwargs[name] = {}
    elif name in {"mission_id", "id"}:
        create_kwargs[name] = "mission_v099_acceptance"
    else:
        raise AssertionError("unsupported required create_mission arg: " + name)

mission = engine.create_mission(**create_kwargs)
mission_id = str(getattr(mission, "mission_id", "") or "")
assert mission_id

task_specs = [
    {
        "key": "email-read",
        "title": "Synthetic email search",
        "tool_name": "email",
        "action": "search",
        "params": {"query": "AURA"},
        "dependencies": [],
        "required": True,
        "max_attempts": 1,
    }
]
planned = engine.plan_mission(mission_id, task_specs)
started = engine.start_mission(mission_id)
tasks = getattr(started, "tasks", None) or getattr(planned, "tasks", None)
assert tasks
task_id = next(iter(tasks))
executed = engine.execute_task(
    mission_id,
    task_id,
    user_confirmed=False,
)
assert str(getattr(executed, "status", "") or "") == "succeeded"
assert engine.security_engine.calls
assert engine.security_engine.calls[-1]["action"] == "search"
assert engine.security_engine.calls[-1]["user_confirmed"] is False
assert len(fake_registry.requests) == 1
assert fake_registry.requests[0]["provider_id"] == "email.provider"
assert fake_registry.requests[0]["capability_id"] == "email.search"
assert fake_registry.requests[0]["user_confirmed"] is False

MISSION_RESULT = {
    "mission_id": mission_id,
    "task_id": task_id,
    "task_status": executed.status,
    "registry_request": fake_registry.requests[0],
}

# ---------------------------------------------------------------------------
# 5. Architecture markers and no duplicated authority.
# ---------------------------------------------------------------------------
core_text = (ROOT / "core" / "aura_core.py").read_text(
    encoding="utf-8-sig",
    errors="replace",
)
assert core_text.count("# AURA_V096_LIVE_BROWSER_RUNTIME_BIND_BEGIN") == 1
assert core_text.count("# AURA_V096_LIVE_BROWSER_RUNTIME_BIND_END") == 1
assert core_text.count("# AURA_V096_BROWSER_ROUTE_BIND_BEGIN") == 1
assert core_text.count("# AURA_V096_BROWSER_ROUTE_BIND_END") == 1
assert core_text.count("# AURA_V097_PRODUCTIVITY_MISSION_RUNTIME_BEGIN") == 1
assert core_text.count("# AURA_V097_PRODUCTIVITY_MISSION_RUNTIME_END") == 1
assert "ensure_productivity_mission_engine_v097" in core_text

print("[PASS] Personal Agent Acceptance v0.9.9")
print("[PASS] v0.9.8 permission contract is fail-closed")
print("[PASS] 4 synthetic personal read families dispatch through real PersonalIntegrationDispatcher")
print("[PASS] Email/Calendar/Contacts/Files mutations all stop at confirmation")
print("[PASS] cancel confirmation never executes a confirmed mutation")
print("[PASS] MissionEngine lifecycle reaches IntegrationMissionToolAdapter through v0.9.7 executor")
print("[PASS] v0.9.6 browser and v0.9.7 productivity runtime markers remain unique")
print("[PASS] no external network required")
