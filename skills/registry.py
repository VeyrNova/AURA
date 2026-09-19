from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import SkillManifest, SkillResolution


class SkillRegistry:
    # AURA v2.3 declarative capability registry.
    # It owns discovery and command-to-skill resolution only.
    # Existing executors retain execution and authorization ownership.

    def __init__(self, root: Path | None = None):
        self.root = Path(root or Path(__file__).resolve().parent)
        self._skills: dict[str, SkillManifest] = {}
        self._command_index: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        skills: dict[str, SkillManifest] = {}
        command_index: dict[str, str] = {}

        for path in sorted(self.root.glob("*/skill.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            manifest = SkillManifest(
                skill_id=str(raw["skill_id"]),
                title=str(raw.get("title") or raw["skill_id"]),
                description=str(raw.get("description") or ""),
                commands=tuple(str(x) for x in raw.get("commands") or []),
                permissions=tuple(str(x) for x in raw.get("permissions") or []),
                owner=str(raw.get("owner") or ""),
                risk=str(raw.get("risk") or "unknown"),
                version=str(raw.get("version") or "2.3.0"),
                enabled=bool(raw.get("enabled", True)),
            )
            if manifest.skill_id in skills:
                raise RuntimeError(f"duplicate skill id: {manifest.skill_id}")
            skills[manifest.skill_id] = manifest

            for command in manifest.commands:
                if command in command_index:
                    raise RuntimeError(
                        f"duplicate command owner: {command} -> "
                        f"{command_index[command]} / {manifest.skill_id}"
                    )
                command_index[command] = manifest.skill_id

        self._skills = skills
        self._command_index = command_index

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._skills))

    def get(self, skill_id: str) -> SkillManifest | None:
        return self._skills.get(str(skill_id))

    def resolve_command(self, command: str) -> SkillResolution | None:
        command = str(command)
        skill_id = self._command_index.get(command)
        if skill_id is None:
            return None
        manifest = self._skills[skill_id]
        if not manifest.enabled:
            return None
        return SkillResolution(
            command=command,
            skill_id=skill_id,
            owner=manifest.owner,
            permissions=manifest.permissions,
            risk=manifest.risk,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": "2.3.0",
            "skills": [self._skills[k].to_dict() for k in sorted(self._skills)],
            "command_index": {
                command: self._command_index[command]
                for command in sorted(self._command_index)
            },
        }
