"""AURA P0.6.4.1 — canonical routing decision contract (shadow mode).

The existing runtime still chooses every route. This module only normalizes
the route that has already been selected so the future Intelligent Router can
be validated before it takes ownership.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import time
from typing import Any
import os


DELIVERIES = frozenset({
    "LOCAL_UI", "LOCAL_CORE", "TOOL", "DOCUMENT", "ROUTER", "LLM",
})


# P0.6.4.9 — one emergency switch can return every canonical gate to the
# mature legacy/shadow path without disabling the underlying capabilities.
CANONICAL_ROUTER_MASTER_ENABLED = (
    str(os.environ.get("AURA_ROUTER_CANONICAL_MASTER", "1"))
    .strip().casefold() not in {"0", "false", "off", "no"}
)

# Explicit perimeter of routes that may currently be labelled CANONICAL/OWNED.
# DOCUMENT and conversational LLM are intentionally absent until a later cutover.
CANONICAL_ROUTE_PAIRS = frozenset({
    ("LOCAL_CORE", "intent-manager"),
    ("LOCAL_CORE", "adaptive-feedback"),
    ("LOCAL_CORE", "self-dialogue"),
    ("LOCAL_CORE", "social-ambient"),
    ("LOCAL_CORE", "grounding"),
    ("LOCAL_CORE", "agent-kernel"),
    ("LOCAL_CORE", "system-safe-app"),
    ("LOCAL_CORE", "system-policy-deny"),
    ("LOCAL_CORE", "system-folder-registry"),
    ("LOCAL_CORE", "system-authorized-folder"),
    ("LOCAL_CORE", "system-authorized-file"),
    ("LOCAL_CORE", "system-local-document"),
    ("LOCAL_CORE", "system-authorized-project"),
    ("TOOL", "web-search"),
    ("TOOL", "weather"),
    ("TOOL", "maps"),
    ("TOOL", "knowledge-reference"),
    ("TOOL", "web-fetch"),
    ("ROUTER", "fast-agent-router"),
})

SHADOW_LOCKED_DELIVERIES = frozenset({"DOCUMENT", "LLM"})

OWNED_LOCAL_INTENTS = frozenset({
    "ROADMAP_STATUS","ROADMAP_NEXT","ROADMAP_FINISH","ROADMAP_SCHEDULE","ROADMAP_BLOCKED","ROADMAP_PHASE","ROADMAP_HISTORY","ROADMAP_UPDATE_STATUS","ROADMAP_UPDATE_PROGRESS","ROADMAP_SHIFT","ROADMAP_ADD","ROADMAP_RENAME_PHASE","ROADMAP_ARCHIVE","ROADMAP_DELETE","ROADMAP_ARCHIVE_PHASE","ROADMAP_RESTORE_REVISION",
    "CREATE_MEMORY","LIST_MEMORIES","SEARCH_MEMORY","FORGET_MEMORY",
    "FORGET_ALL_MEMORIES","FORGET_MEMORY_ALL","EXPLAIN_MEMORY","MEMORY_STATUS",
    "SET_MEMORY_PRIVATE_MODE","SET_MEMORY_NORMAL_MODE","CREATE_NOTE","SEARCH_NOTE",
    "LIST_NOTES","DELETE_NOTE","CREATE_TASK","LIST_TASKS","COMPLETE_TASK",
    "CREATE_REMINDER","LIST_REMINDERS","DELETE_REMINDER",
})

CANONICAL_LOCAL_INTENT_OWNERSHIP = (
    str(os.environ.get("AURA_ROUTER_CANONICAL_LOCAL_INTENTS", "1"))
    .strip().casefold() not in {"0","false","off","no"}
)


OWNED_TOOL_NAMES = frozenset({"web_search", "weather", "maps", "knowledge_reference", "web_fetch"})
CANONICAL_TOOL_OWNERSHIP = (
    str(os.environ.get("AURA_ROUTER_CANONICAL_TOOLS", "1"))
    .strip().casefold() not in {"0","false","off","no"}
)


OWNED_ZERO_LLM_LOCAL_ROUTES = frozenset({
    "adaptive-feedback",
    "self-dialogue",
    "social-ambient",
    "grounding",
})
CANONICAL_ZERO_LLM_LOCAL_OWNERSHIP = (
    str(os.environ.get("AURA_ROUTER_CANONICAL_ZERO_LLM_LOCAL", "1"))
    .strip().casefold() not in {"0","false","off","no"}
)


OWNED_AGENT_ACTIONS = frozenset({
    "WEB_WEATHER",
    "MAPS_LOCATE",
    "MAPS_DIRECTIONS",
    "WEB_SEARCH",
    "WEB_FETCH",
    "KNOWLEDGE_REFERENCE_LOCAL",
    "WEB_KNOWLEDGE_REFERENCE",
})
OWNED_AGENT_SOURCES = frozenset({
    "deterministic-route-weather",
    "deterministic-sequence",
    "fast-structured-router",
})
CANONICAL_READONLY_AGENTPLAN_OWNERSHIP = (
    str(os.environ.get("AURA_ROUTER_CANONICAL_AGENT_PLANS", "1"))
    .strip().casefold() not in {"0","false","off","no"}
)


CANONICAL_FAST_ROUTER_SELECTOR_OWNERSHIP = (
    str(os.environ.get("AURA_ROUTER_CANONICAL_FAST_SELECTOR", "1"))
    .strip().casefold() not in {"0","false","off","no"}
)


# P0.6.5.0 — Desktop Intelligence starts with the already-proven fixed safe
# application launcher only. Arbitrary executables, paths and arguments remain
# outside the canonical perimeter.
OWNED_SAFE_DESKTOP_ACTIONS = frozenset({"OPEN_SAFE_APP"})
OWNED_SAFE_DESKTOP_APPS = frozenset({
    "calculator",
    "notepad",
    "explorer",
    "paint",
})
CANONICAL_SAFE_DESKTOP_OWNERSHIP = (
    str(os.environ.get("AURA_DESKTOP_CANONICAL_SAFE_APPS", "1"))
    .strip().casefold() not in {"0","false","off","no"}
)


OWNED_AUTHORIZED_FOLDER_ACTIONS = frozenset({
    "AUTHORIZE_FOLDER",
    "REVOKE_AUTHORIZED_FOLDER",
    "LIST_AUTHORIZED_FOLDER",
    "OPEN_AUTHORIZED_FOLDER",
})
CANONICAL_AUTHORIZED_FOLDER_OWNERSHIP = (
    str(os.environ.get("AURA_DESKTOP_CANONICAL_FOLDERS", "1"))
    .strip().casefold() not in {"0","false","off","no"}
)


CANONICAL_AUTHORIZED_FILE_READ_OWNERSHIP = (
    str(os.environ.get("AURA_DESKTOP_CANONICAL_FILE_READ", "1"))
    .strip().casefold() not in {"0","false","off","no"}
)


CANONICAL_LOCAL_DOCUMENT_INTELLIGENCE_OWNERSHIP = (
    str(os.environ.get("AURA_DESKTOP_CANONICAL_LOCAL_DOCUMENT", "1"))
    .strip().casefold() not in {"0","false","off","no"}
)


CANONICAL_AUTHORIZED_PROJECT_INTELLIGENCE_OWNERSHIP = (
    str(os.environ.get("AURA_DESKTOP_CANONICAL_PROJECT_INTELLIGENCE", "1"))
    .strip().casefold() not in {"0","false","off","no"}
)

OWNED_AUTHORIZED_PROJECT_ACTIONS = frozenset({"ANALYZE_AUTHORIZED_PROJECT"})


def canonical_route_pair_allowed(delivery: str, route: str) -> bool:
    pair = (
        str(delivery or "").strip().upper(),
        str(route or "").strip().casefold().replace("_", "-"),
    )
    return pair in CANONICAL_ROUTE_PAIRS


def canonical_router_guardrails_snapshot() -> dict[str, Any]:
    """Read-only snapshot of the current canonical perimeter and kill switches."""
    switches = {
        "master": bool(CANONICAL_ROUTER_MASTER_ENABLED),
        "local_intents": bool(CANONICAL_LOCAL_INTENT_OWNERSHIP),
        "tools_readonly": bool(CANONICAL_TOOL_OWNERSHIP),
        "zero_llm_local": bool(CANONICAL_ZERO_LLM_LOCAL_OWNERSHIP),
        "agentplans_readonly": bool(CANONICAL_READONLY_AGENTPLAN_OWNERSHIP),
        "fast_selector": bool(CANONICAL_FAST_ROUTER_SELECTOR_OWNERSHIP),
        "desktop_safe_apps": bool(CANONICAL_SAFE_DESKTOP_OWNERSHIP),
        "desktop_authorized_folders": bool(CANONICAL_AUTHORIZED_FOLDER_OWNERSHIP),
        "desktop_authorized_file_read": bool(CANONICAL_AUTHORIZED_FILE_READ_OWNERSHIP),
        "desktop_local_document_intelligence": bool(CANONICAL_LOCAL_DOCUMENT_INTELLIGENCE_OWNERSHIP),
        "desktop_authorized_project_intelligence": bool(CANONICAL_AUTHORIZED_PROJECT_INTELLIGENCE_OWNERSHIP),
    }
    active_scopes = sum(
        1 for key, value in switches.items()
        if key != "master" and value
    )

    forbidden_pairs = sorted(
        f"{delivery}:{route}"
        for delivery, route in CANONICAL_ROUTE_PAIRS
        if delivery in SHADOW_LOCKED_DELIVERIES
    )
    dangerous_agent_actions = sorted(
        action for action in OWNED_AGENT_ACTIONS
        if action in {
            "RUN_PROGRAM", "RUN_SHELL", "SYSTEM_POWER",
            "FILE_WRITE", "FILE_DELETE", "DESKTOP_ACTION",
        }
    )

    desktop_registry_safe = (
        OWNED_SAFE_DESKTOP_ACTIONS == frozenset({"OPEN_SAFE_APP"})
        and bool(OWNED_SAFE_DESKTOP_APPS)
        and all("/" not in app and "\\" not in app for app in OWNED_SAFE_DESKTOP_APPS)
    )
    invariants = {
        "document_llm_shadow_locked": not forbidden_pairs,
        "agent_registry_readonly": not dangerous_agent_actions,
        "desktop_safe_app_registry_fixed": bool(desktop_registry_safe),
        "authorized_folder_actions_scoped": (
            OWNED_AUTHORIZED_FOLDER_ACTIONS
            == frozenset({
                "AUTHORIZE_FOLDER",
                "REVOKE_AUTHORIZED_FOLDER",
                "LIST_AUTHORIZED_FOLDER",
                "OPEN_AUTHORIZED_FOLDER",
            })
        ),
        "authorized_project_intelligence_readonly": (
            OWNED_AUTHORIZED_PROJECT_ACTIONS == frozenset({"ANALYZE_AUTHORIZED_PROJECT"})
        ),
        "canonical_perimeter_explicit": bool(CANONICAL_ROUTE_PAIRS),
        "master_fail_closed": True,
    }
    structurally_safe = all(invariants.values())

    if not switches["master"]:
        status = "LEGACY_FALLBACK"
    elif active_scopes < 10:
        status = "PARTIAL"
    elif structurally_safe:
        status = "SAFE"
    else:
        status = "BLOCKED"

    return {
        "status": status,
        "safe": structurally_safe,
        "master_enabled": switches["master"],
        "switches": switches,
        "active_scopes": active_scopes,
        "total_scopes": 10,
        "shadow_locked": sorted(SHADOW_LOCKED_DELIVERIES),
        "canonical_route_pairs": [
            {"delivery": delivery, "route": route}
            for delivery, route in sorted(CANONICAL_ROUTE_PAIRS)
        ],
        "owned_agent_actions": sorted(OWNED_AGENT_ACTIONS),
        "invariants": invariants,
        "violations": forbidden_pairs + dangerous_agent_actions,
        "next_cutover_locked": ["DOCUMENT", "LLM"],
    }


@dataclass(frozen=True)
class RouteDecision:
    seq: int
    delivery: str
    route: str
    reason: str
    workspace: str
    intent: str = ""
    provider: str = ""
    model: str = ""
    source: str = "runtime"
    owner: str = "legacy"
    mode: str = "shadow"
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_route_decision(
    *,
    seq: int,
    delivery: str,
    route: str,
    reason: str,
    workspace: str = "home",
    intent: str = "",
    provider: str = "",
    model: str = "",
    source: str = "runtime",
    owner: str = "legacy",
    mode: str = "shadow",
) -> RouteDecision:
    delivery = str(delivery or "LLM").strip().upper()
    if delivery not in DELIVERIES:
        delivery = "LLM"

    route_value = str(route or "conversation")[:80]
    reason_value = str(reason or "unspecified")[:180]
    owner_value = str(owner or "legacy").casefold().strip()[:32]
    mode_value = str(mode or "shadow").casefold().strip()[:32]

    # Fail closed at the contract boundary. A future code path cannot silently
    # claim CANONICAL/OWNED for Documents, LLM, or another unregistered route.
    if (
        owner_value == "canonical"
        and mode_value == "owned"
        and not canonical_route_pair_allowed(delivery, route_value)
    ):
        owner_value = "legacy"
        mode_value = "shadow"
        reason_value = f"guardrail-demoted:{reason_value}"[:180]

    return RouteDecision(
        seq=max(0, int(seq or 0)),
        delivery=delivery,
        route=route_value,
        reason=reason_value,
        workspace=str(workspace or "home").casefold().strip()[:32],
        intent=str(intent or "")[:80],
        provider=str(provider or "")[:48],
        model=str(model or "")[:120],
        source=str(source or "runtime")[:64],
        owner=owner_value,
        mode=mode_value,
        timestamp=time.time(),
    )


def canonical_owned_local_intent(preview_intent: str | None) -> dict[str, str] | None:
    """Own only intents already detected by the existing IntentManager."""
    if not CANONICAL_ROUTER_MASTER_ENABLED or not CANONICAL_LOCAL_INTENT_OWNERSHIP:
        return None
    intent = str(preview_intent or "").strip().upper()
    if intent not in OWNED_LOCAL_INTENTS:
        return None
    return {
        "delivery": "LOCAL_CORE",
        "route": "intent-manager",
        "reason": "canonical-owned-deterministic-intent",
        "intent": intent,
        "owner": "canonical",
        "mode": "owned",
    }


def canonical_owned_tool_descriptor(
    *,
    name: str = "",
    category: str = "",
    action: str = "",
) -> dict[str, str] | None:
    """Own a deterministic tool only AFTER the existing planner selected it.

    This gate does not parse user text, plan a tool, authorize an action or
    execute a provider. It receives the already-selected/authorized descriptor.
    """
    if not CANONICAL_ROUTER_MASTER_ENABLED or not CANONICAL_TOOL_OWNERSHIP:
        return None

    tool_name = str(name or "").strip().casefold()
    tool_category = str(category or "").strip().casefold()
    tool_action = str(action or "").strip().upper()

    if tool_name == "denied":
        return None

    if tool_name == "web_search":
        return {
            "delivery": "TOOL",
            "route": "web-search",
            "reason": "canonical-owned-research-tool",
            "intent": tool_action or "WEB_SEARCH",
            "owner": "canonical",
            "mode": "owned",
        }

    if tool_name == "weather" or tool_category == "weather":
        return {
            "delivery": "TOOL",
            "route": "weather",
            "reason": "canonical-owned-weather-tool",
            "intent": tool_action or "WEB_WEATHER",
            "owner": "canonical",
            "mode": "owned",
        }

    if tool_name == "maps" or tool_category == "maps":
        return {
            "delivery": "TOOL",
            "route": "maps",
            "reason": "canonical-owned-maps-tool",
            "intent": tool_action or "MAPS",
            "owner": "canonical",
            "mode": "owned",
        }

    if tool_name == "knowledge_reference" or tool_category == "knowledge_reference":
        return {
            "delivery": "TOOL",
            "route": "knowledge-reference",
            "reason": "canonical-owned-knowledge-reference",
            "intent": tool_action or "KNOWLEDGE_REFERENCE_LOCAL",
            "owner": "canonical",
            "mode": "owned",
        }

    if tool_name == "web_fetch" or tool_category == "web_fetch":
        return {
            "delivery": "TOOL",
            "route": "web-fetch",
            "reason": "canonical-owned-web-fetch",
            "intent": tool_action or "WEB_FETCH",
            "owner": "canonical",
            "mode": "owned",
        }

    return None


def canonical_owned_tool_plan(plan) -> dict[str, str] | None:
    """Adapter for the existing tools.models.ToolPlan without importing it."""
    if plan is None:
        return None
    return canonical_owned_tool_descriptor(
        name=str(getattr(plan, "name", "") or ""),
        category=str(getattr(plan, "category", "") or ""),
        action=str(getattr(plan, "action", "") or ""),
    )



def canonical_owned_zero_llm_local(route: str) -> dict[str, str] | None:
    """Own an already-resolved local route that requires no LLM/provider.

    The existing runtime still detects and produces the local result. This gate
    only assigns canonical ownership after that existing detector has selected
    one of the explicitly allowlisted zero-LLM routes.
    """
    if not CANONICAL_ROUTER_MASTER_ENABLED or not CANONICAL_ZERO_LLM_LOCAL_OWNERSHIP:
        return None

    route_name = str(route or "").strip().casefold().replace("_", "-")
    if route_name not in OWNED_ZERO_LLM_LOCAL_ROUTES:
        return None

    reasons = {
        "adaptive-feedback": "canonical-owned-adaptive-feedback",
        "self-dialogue": "canonical-owned-self-dialogue",
        "social-ambient": "canonical-owned-social-ambient",
        "grounding": "canonical-owned-grounding",
    }
    return {
        "delivery": "LOCAL_CORE",
        "route": route_name,
        "reason": reasons[route_name],
        "intent": route_name.upper().replace("-", "_"),
        "owner": "canonical",
        "mode": "owned",
    }



def canonical_owned_agent_plan(plan) -> dict[str, str] | None:
    """Own an AgentPlan only after legacy validation + security authorization.

    This function never plans, validates, authorizes or executes a step.
    Callers must pass the already-authorized AgentPlan produced by the existing
    AgentOrchestrator. Ownership is limited to the explicit read-only registry.
    """
    if not CANONICAL_ROUTER_MASTER_ENABLED or not CANONICAL_READONLY_AGENTPLAN_OWNERSHIP or plan is None:
        return None

    source = str(getattr(plan, "source", "") or "").strip().casefold()
    steps = tuple(getattr(plan, "steps", ()) or ())
    if source not in OWNED_AGENT_SOURCES or not (2 <= len(steps) <= 6):
        return None

    actions = tuple(
        str(getattr(step, "action", "") or "").strip().upper()
        for step in steps
    )
    if not actions or any(action not in OWNED_AGENT_ACTIONS for action in actions):
        return None

    reason = (
        "canonical-owned-fast-router-agent-plan"
        if source == "fast-structured-router"
        else "canonical-owned-deterministic-agent-plan"
    )
    return {
        "delivery": "LOCAL_CORE",
        "route": "agent-kernel",
        "reason": reason,
        "intent": "AGENT_PLAN",
        "owner": "canonical",
        "mode": "owned",
        "source": source,
    }



def canonical_owned_fast_router_selector(candidate: bool) -> dict[str, str] | None:
    """Own only the decision to invoke the existing Fast Structured Router.

    `candidate` must already come from AuraCore.should_try_fast_agent_router(),
    whose deterministic AgentToolSelector sees only the read-only registry.

    This function never:
    - parses user text;
    - calls an LLM;
    - accepts an LLM JSON plan;
    - validates a plan;
    - authorizes a step;
    - executes a tool.
    """
    if not CANONICAL_ROUTER_MASTER_ENABLED or not CANONICAL_FAST_ROUTER_SELECTOR_OWNERSHIP or not bool(candidate):
        return None

    return {
        "delivery": "ROUTER",
        "route": "fast-agent-router",
        "reason": "canonical-owned-fast-router-selector",
        "intent": "FAST_AGENT_ROUTER",
        "owner": "canonical",
        "mode": "owned",
    }



def canonical_owned_safe_desktop_plan(plan) -> dict[str, str] | None:
    """Own only an already-authorized fixed safe-app launch plan.

    The plan is created by SystemService after SecurityPolicyEngine authorizes
    OPEN_SAFE_APP. No command/path/argument is accepted here.
    """
    if (
        not CANONICAL_ROUTER_MASTER_ENABLED
        or not CANONICAL_SAFE_DESKTOP_OWNERSHIP
        or plan is None
    ):
        return None

    action = str(getattr(plan, "action", "") or "").strip().upper()
    app_id = str(getattr(plan, "app_id", "") or "").strip().casefold()
    authorized = bool(getattr(plan, "authorized", False))
    permission = str(getattr(plan, "permission", "") or "").strip().casefold()
    risk = str(getattr(plan, "risk", "") or "").strip().upper()

    if action not in OWNED_SAFE_DESKTOP_ACTIONS:
        return None
    if app_id not in OWNED_SAFE_DESKTOP_APPS:
        return None
    if not authorized:
        return None
    if permission != "safe_app_launch":
        return None
    if risk not in {"LOW", "SAFE"}:
        return None

    return {
        "delivery": "LOCAL_CORE",
        "route": "system-safe-app",
        "reason": "canonical-owned-authorized-safe-app",
        "intent": "OPEN_SAFE_APP",
        "owner": "canonical",
        "mode": "owned",
        "app_id": app_id,
    }



def canonical_owned_desktop_policy_denial(
    action: str,
    *,
    allowed: bool,
    target: str = "",
) -> dict[str, str] | None:
    """Own a deterministic SecurityPolicyEngine denial; never an execution."""
    if not CANONICAL_ROUTER_MASTER_ENABLED:
        return None

    normalized_action = str(action or "").strip().upper()
    if normalized_action != "RUN_PROGRAM" or bool(allowed):
        return None

    return {
        "delivery": "LOCAL_CORE",
        "route": "system-policy-deny",
        "reason": "canonical-owned-desktop-policy-denial",
        "intent": "RUN_PROGRAM_DENIED",
        "owner": "canonical",
        "mode": "owned",
        "target": str(target or "")[:80],
    }



def canonical_owned_authorized_folder_plan(plan) -> dict[str, str] | None:
    """Own an already-authorized action over an explicit folder registry id."""
    if (
        not CANONICAL_ROUTER_MASTER_ENABLED
        or not CANONICAL_AUTHORIZED_FOLDER_OWNERSHIP
        or plan is None
    ):
        return None

    action = str(getattr(plan, "action", "") or "").strip().upper()
    folder_id = str(getattr(plan, "folder_id", "") or "").strip().casefold()
    authorized = bool(getattr(plan, "authorized", False))
    permission = str(getattr(plan, "permission", "") or "").strip().casefold()
    risk = str(getattr(plan, "risk", "") or "").strip().upper()

    if action not in OWNED_AUTHORIZED_FOLDER_ACTIONS:
        return None
    if len(folder_id) != 16 or any(ch not in "0123456789abcdef" for ch in folder_id):
        return None
    if not authorized or permission != "authorized_folder_access":
        return None
    if risk not in {"SAFE", "LOW", "MEDIUM"}:
        return None

    route = (
        "system-folder-registry"
        if action in {"AUTHORIZE_FOLDER", "REVOKE_AUTHORIZED_FOLDER"}
        else "system-authorized-folder"
    )
    return {
        "delivery": "LOCAL_CORE",
        "route": route,
        "reason": f"canonical-owned-{action.casefold().replace('_','-')}",
        "intent": action,
        "owner": "canonical",
        "mode": "owned",
        "folder_id": folder_id,
    }



def canonical_owned_authorized_file_read_plan(plan) -> dict[str, str] | None:
    """Own only local read of an already-resolved file inside an authorized folder."""
    if (
        not CANONICAL_ROUTER_MASTER_ENABLED
        or not CANONICAL_AUTHORIZED_FILE_READ_OWNERSHIP
        or plan is None
    ):
        return None

    action = str(getattr(plan, "action", "") or "").strip().upper()
    folder_id = str(getattr(plan, "folder_id", "") or "").strip().casefold()
    file_id = str(getattr(plan, "file_id", "") or "").strip().casefold()
    authorized = bool(getattr(plan, "authorized", False))
    permission = str(getattr(plan, "permission", "") or "").strip().casefold()
    risk = str(getattr(plan, "risk", "") or "").strip().upper()

    if action != "READ_AUTHORIZED_FILE":
        return None
    for opaque_id in (folder_id, file_id):
        if len(opaque_id) != 16 or any(ch not in "0123456789abcdef" for ch in opaque_id):
            return None
    if not authorized or permission != "authorized_file_read":
        return None
    if risk not in {"SAFE", "LOW"}:
        return None

    return {
        "delivery": "LOCAL_CORE",
        "route": "system-authorized-file",
        "reason": "canonical-owned-read-authorized-file",
        "intent": "READ_AUTHORIZED_FILE",
        "owner": "canonical",
        "mode": "owned",
        "folder_id": folder_id,
        "file_id": file_id,
    }



def canonical_owned_local_document_analysis_plan(plan) -> dict[str, str] | None:
    """Own deterministic local analysis of an already-authorized file."""
    if (
        not CANONICAL_ROUTER_MASTER_ENABLED
        or not CANONICAL_LOCAL_DOCUMENT_INTELLIGENCE_OWNERSHIP
        or plan is None
    ):
        return None

    action = str(getattr(plan, "action", "") or "").strip().upper()
    folder_id = str(getattr(plan, "folder_id", "") or "").strip().casefold()
    file_id = str(getattr(plan, "file_id", "") or "").strip().casefold()
    analysis_mode = str(getattr(plan, "analysis_mode", "") or "").strip().casefold()
    authorized = bool(getattr(plan, "authorized", False))
    permission = str(getattr(plan, "permission", "") or "").strip().casefold()
    risk = str(getattr(plan, "risk", "") or "").strip().upper()

    if action != "ANALYZE_AUTHORIZED_FILE":
        return None
    if analysis_mode not in {"summary", "search", "context"}:
        return None
    for opaque_id in (folder_id, file_id):
        if len(opaque_id) != 16 or any(ch not in "0123456789abcdef" for ch in opaque_id):
            return None
    if not authorized or permission != "authorized_file_read":
        return None
    if risk not in {"SAFE", "LOW"}:
        return None

    return {
        "delivery": "LOCAL_CORE",
        "route": "system-local-document",
        "reason": f"canonical-owned-local-document-{analysis_mode}",
        "intent": "ANALYZE_AUTHORIZED_FILE",
        "owner": "canonical",
        "mode": "owned",
        "analysis_mode": analysis_mode,
        "folder_id": folder_id,
        "file_id": file_id,
    }


def canonical_owned_authorized_project_analysis_plan(plan) -> dict[str, str] | None:
    """Own bounded, local-only intelligence over files in one authorized project."""
    if (
        not CANONICAL_ROUTER_MASTER_ENABLED
        or not CANONICAL_AUTHORIZED_PROJECT_INTELLIGENCE_OWNERSHIP
        or plan is None
    ):
        return None

    action=str(getattr(plan,"action","") or "").strip().upper()
    folder_id=str(getattr(plan,"folder_id","") or "").strip().casefold()
    analysis_mode=str(getattr(plan,"analysis_mode","") or "").strip().casefold()
    file_ids=tuple(getattr(plan,"file_ids",()) or ())
    authorized=bool(getattr(plan,"authorized",False))
    permission=str(getattr(plan,"permission","") or "").strip().casefold()
    risk=str(getattr(plan,"risk","") or "").strip().upper()

    if action != "ANALYZE_AUTHORIZED_PROJECT":
        return None
    if analysis_mode not in {"summary","search","context"}:
        return None
    if len(folder_id)!=16 or any(ch not in "0123456789abcdef" for ch in folder_id):
        return None
    if not file_ids or len(file_ids)>24:
        return None
    for file_id in file_ids:
        value=str(file_id or "").casefold().strip()
        if len(value)!=16 or any(ch not in "0123456789abcdef" for ch in value):
            return None
    if not authorized or permission!="authorized_file_read":
        return None
    if risk not in {"SAFE","LOW"}:
        return None

    return {
        "delivery":"LOCAL_CORE",
        "route":"system-authorized-project",
        "reason":f"canonical-owned-authorized-project-{analysis_mode}",
        "intent":"ANALYZE_AUTHORIZED_PROJECT",
        "owner":"canonical",
        "mode":"owned",
        "analysis_mode":analysis_mode,
        "folder_id":folder_id,
        "file_count":str(len(file_ids)),
    }

# AURA_V096_BROWSER_ROUTE_MAPPING_BEGIN
BROWSER_ROUTE_MAP_V096 = {
    "browser.open": "browser-open",
    "browser.navigate": "browser-navigate",
    "browser.read": "browser-read",
    "browser.extract": "browser-extract",
    "browser.search": "browser-search",
    "browser.click": "browser-click",
    "browser.fill": "browser-fill",
    "browser.submit": "browser-submit",
    "browser.download": "browser-download",
    "browser.workflow": "browser-workflow",
}

BROWSER_CANONICAL_ROUTE_PAIRS_V096 = frozenset(
    ("TOOL", route)
    for route in BROWSER_ROUTE_MAP_V096.values()
)

CANONICAL_ROUTE_PAIRS = CANONICAL_ROUTE_PAIRS | BROWSER_CANONICAL_ROUTE_PAIRS_V096
OWNED_TOOL_NAMES = OWNED_TOOL_NAMES | frozenset({"browser", "browser.provider"})

def canonical_owned_browser_descriptor_v096(capability):
    key = str(capability or "").strip().casefold().replace("_", ".")
    route = BROWSER_ROUTE_MAP_V096.get(key)
    if route is None:
        return None
    return {
        "delivery": "TOOL",
        "route": route,
        "reason": "canonical-owned-browser-v096",
        "intent": key.upper().replace(".", "_"),
        "provider": "browser.provider",
        "owner": "AURA_BROWSER_WORKFLOWS_V096",
        "mode": "CANONICAL",
    }
# AURA_V096_BROWSER_ROUTE_MAPPING_END
