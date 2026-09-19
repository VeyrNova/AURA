from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional
import re

from .manifest import SkillManifest


class SkillDeveloperContractError(ValueError):
    pass


_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)

_ALLOWED_EXECUTION_MODEL = "secure_runtime_v101"
_ALLOWED_INSTALL_SCOPE = "metadata_only"


def _version_tuple(value: str) -> tuple[int, int, int]:
    text = str(value or "").strip()
    match = _SEMVER_RE.fullmatch(text)
    if not match:
        raise SkillDeveloperContractError("invalid_semver:" + text)
    return tuple(int(match.group(i)) for i in (1, 2, 3))


@dataclass(frozen=True)
class SkillDeveloperContractV102:
    manifest: SkillManifest
    min_aura_version: str
    max_aura_version: Optional[str] = None
    execution_model: str = _ALLOWED_EXECUTION_MODEL
    install_scope: str = _ALLOWED_INSTALL_SCOPE
    dynamic_code: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, SkillManifest):
            raise SkillDeveloperContractError("SkillManifest required")

        min_version = str(self.min_aura_version or "").strip()
        max_version = (
            None
            if self.max_aura_version is None
            else str(self.max_aura_version).strip()
        )
        min_tuple = _version_tuple(min_version)
        max_tuple = None if max_version is None else _version_tuple(max_version)

        if max_tuple is not None and max_tuple < min_tuple:
            raise SkillDeveloperContractError("invalid_version_range")

        execution_model = str(self.execution_model or "").strip()
        if execution_model != _ALLOWED_EXECUTION_MODEL:
            raise SkillDeveloperContractError(
                "unsupported_execution_model:" + execution_model
            )

        install_scope = str(self.install_scope or "").strip()
        if install_scope != _ALLOWED_INSTALL_SCOPE:
            raise SkillDeveloperContractError(
                "unsupported_install_scope:" + install_scope
            )

        if bool(self.dynamic_code):
            raise SkillDeveloperContractError("dynamic_code_forbidden")

        object.__setattr__(self, "min_aura_version", min_version)
        object.__setattr__(self, "max_aura_version", max_version)
        object.__setattr__(self, "execution_model", execution_model)
        object.__setattr__(self, "install_scope", install_scope)
        object.__setattr__(self, "dynamic_code", False)
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata or {})),
        )

    def supports_aura_version(self, aura_version: str) -> bool:
        current = _version_tuple(aura_version)
        minimum = _version_tuple(self.min_aura_version)
        maximum = (
            None
            if self.max_aura_version is None
            else _version_tuple(self.max_aura_version)
        )
        if current < minimum:
            return False
        if maximum is not None and current > maximum:
            return False
        return True

    def validate_for_aura_version(self, aura_version: str) -> None:
        if not self.supports_aura_version(aura_version):
            raise SkillDeveloperContractError(
                "incompatible_aura_version:"
                + str(aura_version)
                + ":"
                + self.min_aura_version
                + ":"
                + str(self.max_aura_version)
            )


def build_skill_developer_contract_v102(
    *,
    manifest: SkillManifest,
    payload: Mapping[str, Any],
) -> SkillDeveloperContractV102:
    if not isinstance(payload, Mapping):
        raise SkillDeveloperContractError("mapping_payload_required")

    allowed = {
        "min_aura_version",
        "max_aura_version",
        "execution_model",
        "install_scope",
        "dynamic_code",
        "metadata",
    }
    unknown = sorted(str(key) for key in payload if str(key) not in allowed)
    if unknown:
        raise SkillDeveloperContractError(
            "unknown_contract_fields:" + ",".join(unknown)
        )

    if "min_aura_version" not in payload:
        raise SkillDeveloperContractError("min_aura_version_required")

    return SkillDeveloperContractV102(
        manifest=manifest,
        min_aura_version=str(payload["min_aura_version"]),
        max_aura_version=payload.get("max_aura_version"),
        execution_model=str(
            payload.get("execution_model", _ALLOWED_EXECUTION_MODEL)
        ),
        install_scope=str(
            payload.get("install_scope", _ALLOWED_INSTALL_SCOPE)
        ),
        dynamic_code=bool(payload.get("dynamic_code", False)),
        metadata=payload.get("metadata") or {},
    )


__all__ = [
    "SkillDeveloperContractError",
    "SkillDeveloperContractV102",
    "build_skill_developer_contract_v102",
]
