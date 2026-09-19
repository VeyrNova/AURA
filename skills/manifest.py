from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping
import re


_SKILL_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{2,63}$")
_PROVIDER_ID_RE = re.compile(r"^[a-z][a-z0-9_-]*\.provider$")
_CAPABILITY_ID_RE = re.compile(r"^[a-z][a-z0-9_-]*\.[a-z][a-z0-9_.-]*$")
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


class SkillManifestError(ValueError):
    pass


@dataclass(frozen=True)
class SkillCapabilityRef:
    provider_id: str
    capability_id: str

    def __post_init__(self) -> None:
        provider_id = str(self.provider_id or "").strip()
        capability_id = str(self.capability_id or "").strip()

        if not _PROVIDER_ID_RE.fullmatch(provider_id):
            raise SkillManifestError("invalid_provider_id:" + provider_id)
        if not _CAPABILITY_ID_RE.fullmatch(capability_id):
            raise SkillManifestError("invalid_capability_id:" + capability_id)

        provider_prefix = provider_id.split(".", 1)[0]
        capability_prefix = capability_id.split(".", 1)[0]
        if provider_prefix != capability_prefix:
            raise SkillManifestError(
                "provider_capability_prefix_mismatch:"
                + provider_id
                + ":"
                + capability_id
            )

        object.__setattr__(self, "provider_id", provider_id)
        object.__setattr__(self, "capability_id", capability_id)


@dataclass(frozen=True)
class SkillManifest:
    skill_id: str
    display_name: str
    skill_version: str
    capabilities: tuple[SkillCapabilityRef, ...]
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        skill_id = str(self.skill_id or "").strip()
        display_name = str(self.display_name or "").strip()
        skill_version = str(self.skill_version or "").strip()
        description = str(self.description or "").strip()
        capabilities = tuple(self.capabilities or ())

        if not _SKILL_ID_RE.fullmatch(skill_id):
            raise SkillManifestError("invalid_skill_id:" + skill_id)
        if not display_name:
            raise SkillManifestError("display_name_required")
        if not _SEMVER_RE.fullmatch(skill_version):
            raise SkillManifestError("invalid_skill_version:" + skill_version)
        if not capabilities:
            raise SkillManifestError("at_least_one_capability_required")

        normalized = []
        seen = set()
        for item in capabilities:
            if not isinstance(item, SkillCapabilityRef):
                raise SkillManifestError("capability_ref_type_required")
            key = (item.provider_id, item.capability_id)
            if key in seen:
                raise SkillManifestError(
                    "duplicate_capability_ref:"
                    + item.provider_id
                    + ":"
                    + item.capability_id
                )
            seen.add(key)
            normalized.append(item)

        meta = MappingProxyType(dict(self.metadata or {}))

        object.__setattr__(self, "skill_id", skill_id)
        object.__setattr__(self, "display_name", display_name)
        object.__setattr__(self, "skill_version", skill_version)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "capabilities", tuple(normalized))
        object.__setattr__(self, "metadata", meta)


__all__ = [
    "SkillManifestError",
    "SkillCapabilityRef",
    "SkillManifest",
]
