from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.planner import DeterministicAgentPlanner
from agent.tool_registry import AgentToolRegistry
from config.settings import settings
from tools.internet_manager import InternetToolManager


def main() -> int:
    print(f"AURA v{settings.APP_VERSION} — Agent Kernel diagnostics")
    print(f"enabled={settings.AGENT_KERNEL_ENABLED} multi_tool={settings.AGENT_MULTI_TOOL_ENABLED} max_steps={settings.AGENT_MAX_STEPS}")
    registry = AgentToolRegistry.default_readonly()
    print("registered=" + ", ".join(spec.name for spec in registry.specs()))
    planner = DeterministicAgentPlanner(InternetToolManager(), registry, max_steps=settings.AGENT_MAX_STEPS)
    samples = (
        "Montre-moi Toulon sur la carte puis météo à Toulon",
        "Itinéraire de Vidauban à Toulon puis météo à Toulon",
        "Météo à Toulon",
    )
    for sample in samples:
        plan = planner.plan(sample)
        actions = ",".join(step.action for step in plan.steps) if plan else "legacy-single-flow"
        print(f"{sample!r} => {actions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
