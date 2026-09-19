from __future__ import annotations
import sys
from pathlib import Path

def check(root: Path, ui: Path | None, baseline: dict, *, portable: bool = False) -> dict:
    sys.path.insert(0, str(root))
    from tools.internet_manager import InternetToolManager

    prompt = "Quel temps fait-il actuellement à Toulon ?"
    extracted = InternetToolManager._extract_weather_location(prompt)
    checks = {
        "extracts_location": "toulon" in str(extracted).casefold(),
    }
    plan_detail = None
    try:
        plan = InternetToolManager().plan(prompt)
        plan_detail = {
            "name": getattr(plan, "name", None),
            "action": getattr(plan, "action", None),
            "args": getattr(plan, "args", None),
        }
        # If Internet tools are enabled in this environment, plan must preserve Toulon.
        if plan is not None:
            checks["plan_weather"] = getattr(plan, "name", None) == "weather"
            checks["plan_action"] = getattr(plan, "action", None) == "WEB_WEATHER"
            checks["plan_location"] = "toulon" in str((getattr(plan, "args", {}) or {}).get("location") or "").casefold()
    except Exception as exc:
        if not portable:
            checks["plan_constructor"] = False
        plan_detail = {"environment_error": f"{type(exc).__name__}: {exc}"}
    return {
        "name": "weather_location_roundtrip",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "blocking": True,
        "checks": checks,
        "plan": plan_detail,
    }
