from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentVisualComposition:
    """Validated visual composition selected from an Agent Kernel result.

    The composer is deliberately deterministic: tool observations may request a
    known rich surface, but they cannot instantiate arbitrary widgets or execute
    code. Unknown combinations simply fall back to the generic PLAN AURA panel.
    """

    kind: str
    maps_data: dict[str, Any] = field(default_factory=dict)
    weather_data: dict[str, Any] = field(default_factory=dict)
    title: str = ""
    subtitle: str = ""

    @property
    def specialized(self) -> bool:
        return bool(self.kind)


def _observation_rows(result) -> list[dict[str, Any]]:
    data = dict(getattr(result, "data", {}) or {})
    rows = data.get("observations") or []
    return [row for row in rows if isinstance(row, dict)]


def compose_agent_visual(result) -> AgentVisualComposition | None:
    """Select a safe rich surface for a completed multi-tool result.

    v0.7.1.0.1 initially specializes the most useful combination already
    supported by AURA: Maps/Route + Weather. The matching is category based so
    it remains compatible with deterministic and future structured planners.
    """

    if not getattr(result, "ok", False):
        return None

    maps_row: dict[str, Any] | None = None
    weather_row: dict[str, Any] | None = None
    for row in _observation_rows(result):
        if not bool(row.get("ok")):
            continue
        category = str(row.get("category") or "").casefold()
        payload = row.get("data")
        if not isinstance(payload, dict) or not payload:
            continue
        if category == "maps" and maps_row is None:
            maps_row = row
        elif category == "weather" and weather_row is None:
            weather_row = row

    if maps_row is None or weather_row is None:
        return None

    maps_data = dict(maps_row.get("data") or {})
    weather_data = dict(weather_row.get("data") or {})
    mode = str(maps_data.get("mode") or "location").casefold()
    destination = str(
        maps_data.get("label")
        or weather_data.get("place_label")
        or weather_data.get("location")
        or maps_data.get("destination")
        or ""
    ).strip()

    if mode == "directions":
        return AgentVisualComposition(
            kind="route_weather",
            maps_data=maps_data,
            weather_data=weather_data,
            title="AURA ROUTE INTELLIGENCE",
            subtitle=destination,
        )

    return AgentVisualComposition(
        kind="maps_weather",
        maps_data=maps_data,
        weather_data=weather_data,
        title="AURA GEO + WEATHER",
        subtitle=destination,
    )
