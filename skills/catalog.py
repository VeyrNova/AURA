from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .package import (
    SkillPackageArtifactV110,
    decode_skill_package_v110,
)


class SkillCatalogError(RuntimeError):
    pass


class DuplicateSkillCatalogEntryError(
    SkillCatalogError
):
    pass


@dataclass(frozen=True)
class SkillCatalogEntryV110:
    skill_id: str
    skill_version: str
    display_name: str
    description: str
    package_sha256: str
    package_bytes: bytes


class LocalSkillCatalogV110:
    """Local declarative package index only.

    This catalog cannot install, activate, execute or alter
    integration providers.
    """

    def __init__(self):
        self._entries: dict[
            str,
            SkillCatalogEntryV110,
        ] = {}

    def add_package(
        self,
        artifact: SkillPackageArtifactV110,
    ) -> SkillCatalogEntryV110:
        if not isinstance(
            artifact,
            SkillPackageArtifactV110,
        ):
            raise TypeError(
                "SkillPackageArtifactV110 required"
            )

        if artifact.skill_id in self._entries:
            raise DuplicateSkillCatalogEntryError(
                artifact.skill_id
            )

        contract = decode_skill_package_v110(
            artifact.package_bytes,
            expected_sha256=artifact.sha256,
        )

        if contract.manifest.skill_id != artifact.skill_id:
            raise SkillCatalogError(
                "artifact_skill_id_mismatch"
            )
        if (
            contract.manifest.skill_version
            != artifact.skill_version
        ):
            raise SkillCatalogError(
                "artifact_skill_version_mismatch"
            )

        entry = SkillCatalogEntryV110(
            skill_id=contract.manifest.skill_id,
            skill_version=contract.manifest.skill_version,
            display_name=contract.manifest.display_name,
            description=contract.manifest.description,
            package_sha256=artifact.sha256,
            package_bytes=bytes(
                artifact.package_bytes
            ),
        )
        self._entries[entry.skill_id] = entry
        return entry

    def get(
        self,
        skill_id: str,
    ) -> Optional[SkillCatalogEntryV110]:
        return self._entries.get(
            str(skill_id or "").strip()
        )

    def list_entries(
        self,
    ) -> tuple[SkillCatalogEntryV110, ...]:
        return tuple(
            self._entries[key]
            for key in sorted(self._entries)
        )

    def remove(self, skill_id: str) -> bool:
        key = str(skill_id or "").strip()
        return self._entries.pop(key, None) is not None


__all__ = [
    "SkillCatalogError",
    "DuplicateSkillCatalogEntryError",
    "SkillCatalogEntryV110",
    "LocalSkillCatalogV110",
]
