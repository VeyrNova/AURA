# AURA v2.3 Skill Registry Foundation
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from skills import SkillRegistry


@lru_cache(maxsize=1)
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry(Path(__file__).resolve().parents[1] / "skills")


def skill_registry_snapshot() -> dict[str, Any]:
    return get_skill_registry().snapshot()


def resolve_skill_for_command(command: str) -> dict[str, Any] | None:
    resolution = get_skill_registry().resolve_command(command)
    return None if resolution is None else resolution.to_dict()
