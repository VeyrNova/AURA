from __future__ import annotations

from typing import Any


_PROVIDER_BY_PREFIX = {
    "email": "email.provider",
    "calendar": "calendar.provider",
    "contacts": "contacts.provider",
    "files": "files.provider",
    "notifications": "notifications.provider",
    "browser": "browser.provider",
}

_CERTIFIED_BROWSER_CAPABILITIES = frozenset({
    "browser.open",
    "browser.navigate",
    "browser.read",
    "browser.extract",
    "browser.search",
    "browser.click",
    "browser.fill",
    "browser.submit",
    "browser.download",
    "browser.workflow",
})

_SECURITY_ATTRS = (
    "security_engine",
    "_security_engine",
    "policy_engine_v2",
    "_policy_engine_v2",
    "policy_engine",
    "_policy_engine",
)


def resolve_productivity_target_v097(tool_call: Any):
    tool_name = str(getattr(tool_call, "tool_name", "") or "").strip()
    action = str(getattr(tool_call, "action", "") or "").strip()

    capability_id = ""
    if "." in action:
        capability_id = action
    elif "." in tool_name and not tool_name.endswith(".provider"):
        capability_id = tool_name
    else:
        prefix = tool_name[:-9] if tool_name.endswith(".provider") else tool_name
        prefix = prefix.strip().casefold()
        if prefix and action:
            capability_id = prefix + "." + action

    capability_id = capability_id.strip()
    if "." not in capability_id:
        return None

    prefix = capability_id.split(".", 1)[0].casefold()
    provider_id = _PROVIDER_BY_PREFIX.get(prefix)
    if provider_id is None:
        return None

    if prefix == "browser" and capability_id not in _CERTIFIED_BROWSER_CAPABILITIES:
        return None

    return provider_id, capability_id


def resolve_existing_security_engine_v097(aura_core, dispatcher):
    for owner in (
        aura_core,
        getattr(dispatcher, "context", None),
    ):
        if owner is None:
            continue
        for attr in _SECURITY_ATTRS:
            candidate = getattr(owner, attr, None)
            if candidate is not None:
                return candidate
    return None


class ProductivityMissionToolExecutorV097:
    def __init__(self, *, registry, origin: str = "MissionEngine"):
        self.registry = registry
        self.origin = str(origin or "MissionEngine")

    def __call__(self, tool_call):
        target = resolve_productivity_target_v097(tool_call)
        if target is None:
            raise ValueError("unsupported_productivity_mission_tool")
        provider_id, capability_id = target

        from integrations.registry import IntegrationMissionToolAdapter

        adapter = IntegrationMissionToolAdapter(
            registry=self.registry,
            provider_id=provider_id,
            capability_id=capability_id,
            origin=self.origin,
        )
        return adapter(tool_call)


def build_productivity_mission_engine_v097(
    *,
    security_engine,
    registry,
    store=None,
    planning_context_provider=None,
):
    from mission_engine.engine import MissionEngine

    if security_engine is None:
        raise RuntimeError("productivity_mission_security_engine_unavailable")

    executor = ProductivityMissionToolExecutorV097(registry=registry)
    return MissionEngine(
        security_engine=security_engine,
        tool_executor=executor,
        store=store,
        planning_context_provider=planning_context_provider,
    )


def ensure_productivity_mission_engine_v097(aura_core, dispatcher):
    existing = getattr(aura_core, "_productivity_mission_engine_v097", None)
    if existing is not None:
        return existing

    context = getattr(dispatcher, "context", None)
    registry = getattr(context, "registry", None)
    if registry is None:
        raise RuntimeError("productivity_mission_registry_unavailable")

    security_engine = resolve_existing_security_engine_v097(aura_core, dispatcher)
    if security_engine is None:
        raise RuntimeError("productivity_mission_security_engine_unavailable")

    engine = build_productivity_mission_engine_v097(
        security_engine=security_engine,
        registry=registry,
    )
    aura_core._productivity_mission_engine_v097 = engine
    return engine


__all__ = [
    "ProductivityMissionToolExecutorV097",
    "resolve_productivity_target_v097",
    "resolve_existing_security_engine_v097",
    "build_productivity_mission_engine_v097",
    "ensure_productivity_mission_engine_v097",
]
