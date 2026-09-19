from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolPlan:
    name: str
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    category: str = ""


@dataclass(frozen=True)
class ToolSource:
    name: str
    host: str
    checked_at: str
    url: str = ""


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    response: str
    category: str
    source: str
    sources: tuple[ToolSource, ...] = ()
    # Optional TTS-only wording. The UI/history keeps `response` with full
    # provenance/details while voice may use a shorter deterministic phrasing.
    speech_response: str = ""
    # v0.7.0.15.3: structured completeness metadata for visual result surfaces.
    item_count: int = 0
    expected_items: int = 0
    complete: bool = True
    # v0.7.0.15.6.12: optional structured payload for dedicated visual tool
    # surfaces (weather/maps/etc.). Existing positional call sites remain valid.
    data: dict[str, Any] = field(default_factory=dict)
