from __future__ import annotations

import sys
from pathlib import Path

# AURA v0.8.6.1.1 — CI GATE ACCURACY REPAIR / MAPS CONTRACT
# Two different contracts are intentionally tested:
#   1) the legacy raw extractor on a phrase it natively owns;
#   2) InternetToolManager.plan() on the richer "en voiture de ... à ..." phrase,
#      which must exercise the deterministic P0.8.5.4.7.5 route-pair fallback.

class _NullToolContext:
    def clear(self):
        return None

    def plan_followup(self, _text):
        return None


def _planner_contract(internet_manager):
    settings = internet_manager.settings
    forced = {
        "KNOWLEDGE_REFERENCE_ENABLED": False,
        "INTERNET_TOOLS_ENABLED": True,
        "MAPS_TOOL_ENABLED": True,
        "WEB_FETCH_ENABLED": False,
    }
    previous = {}
    for name, value in forced.items():
        if hasattr(settings, name):
            previous[name] = getattr(settings, name)
            setattr(settings, name, value)

    manager = internet_manager.InternetToolManager.__new__(
        internet_manager.InternetToolManager
    )
    manager.context = _NullToolContext()

    try:
        return manager.plan(
            "Calcule un itinéraire en voiture de Toulon à Marseille."
        )
    finally:
        for name, value in previous.items():
            setattr(settings, name, value)


def check(root: Path, ui: Path | None, baseline: dict, *, portable: bool = False) -> dict:
    sys.path.insert(0, str(root))
    import tools.internet_manager as internet_manager

    raw = internet_manager.extract_maps_request(
        "itinéraire de Toulon à Marseille."
    )
    plan = _planner_contract(internet_manager)

    plan_args = (getattr(plan, "args", {}) or {}) if plan is not None else {}
    checks = {
        "raw_request_detected": isinstance(raw, dict),
        "raw_action_directions": (
            isinstance(raw, dict) and raw.get("action") == "directions"
        ),
        "raw_origin_toulon": (
            isinstance(raw, dict)
            and "toulon" in str(raw.get("origin") or "").casefold()
        ),
        "raw_destination_marseille": (
            isinstance(raw, dict)
            and "marseille" in str(raw.get("destination") or "").casefold()
        ),
        "planner_detected": plan is not None,
        "planner_tool_maps": getattr(plan, "name", None) == "maps",
        "planner_action_directions": (
            getattr(plan, "action", None) == "MAPS_DIRECTIONS"
        ),
        "planner_origin_toulon": (
            "toulon" in str(plan_args.get("origin") or "").casefold()
        ),
        "planner_destination_marseille": (
            "marseille" in str(plan_args.get("destination") or "").casefold()
        ),
        "planner_driving": (
            str(plan_args.get("travelmode") or "").casefold() == "driving"
        ),
    }

    ui_detail = None
    if ui is None:
        if not portable:
            checks["active_ui_available"] = False
        ui_detail = "ENVIRONMENT"
    else:
        nav = ui / "dist" / "assets" / "aura-p060-navigation-workspace.js"
        text = (
            nav.read_text(encoding="utf-8-sig", errors="replace")
            if nav.is_file()
            else ""
        )
        ui_checks = {
            "shared_bus_listener": "aura:hub-event" in text,
            "maps_subscriber": (
                "__AURA_SHARED_EVENT_SUBSCRIBERS__.maps=true" in text
            ),
            "private_eventsource_absent": (
                "new EventSource(`/api/events?token=${encodeURIComponent(token)}`)"
                not in text
            ),
            "native_source_evidence": "source:'core-shared-native'" in text,
            "fallback_source_evidence": "source:'core-fallback'" in text,
        }
        checks.update(ui_checks)
        ui_detail = ui_checks

    return {
        "name": "maps_contract",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "blocking": True,
        "checks": checks,
        "raw_request": raw,
        "planner": {
            "name": getattr(plan, "name", None),
            "action": getattr(plan, "action", None),
            "args": plan_args,
        },
        "ui": ui_detail,
        "gate_revision": "v0.8.6.1.1",
    }
