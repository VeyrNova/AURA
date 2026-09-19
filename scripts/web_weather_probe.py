"""Explicit network probe for AURA v0.7.0 weather tool."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.internet_manager import InternetToolManager
from tools.models import ToolPlan


def main() -> int:
    print("=== AURA v0.7.0 — WEATHER INTERNET PROBE ===")
    print("Ce test effectue une requête HTTPS réelle vers Open-Meteo pour Paris.\n")
    manager = InternetToolManager()
    result = manager.execute(ToolPlan("weather", "WEB_WEATHER", {"location": "Paris", "tomorrow": False}, "weather"))
    print(result.response)
    if result.ok:
        print("\n[PASS] Météo Internet sourcee opérationnelle.")
        return 0
    print("\n[FAIL] La météo Internet n'est pas joignable depuis cette machine.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
