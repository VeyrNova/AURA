from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class SkillManifest:
    skill_id: str
    title: str
    description: str
    commands: tuple[str, ...]
    permissions: tuple[str, ...]
    owner: str
    risk: str
    version: str = "2.3.0"
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "title": self.title,
            "description": self.description,
            "commands": list(self.commands),
            "permissions": list(self.permissions),
            "owner": self.owner,
            "risk": self.risk,
            "version": self.version,
            "enabled": self.enabled,
        }


@dataclass(frozen=True)
class SkillResolution:
    command: str
    skill_id: str
    owner: str
    permissions: tuple[str, ...]
    risk: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "skill_id": self.skill_id,
            "owner": self.owner,
            "permissions": list(self.permissions),
            "risk": self.risk,
        }


@dataclass(frozen=True)
class SkillInvocationContext:
    dispatch_existing_command: Callable[[str, Mapping[str, Any]], Any]
    source: str = "skill-registry"

    def dispatch(self, command: str, payload: Mapping[str, Any] | None = None) -> Any:
        return self.dispatch_existing_command(str(command), dict(payload or {}))
