from __future__ import annotations

from typing import Optional

from .catalog import (
    LocalSkillCatalogV110,
    SkillCatalogEntryV110,
)
from .developer_contract import (
    SkillDeveloperContractV102,
)
from .lifecycle import (
    SkillLifecycleManagerV102,
    SkillLifecycleRecordV102,
)
from .package import (
    SkillPackageArtifactV110,
    decode_skill_package_v110,
    encode_skill_package_v110,
)


class SkillDistributionError(RuntimeError):
    pass


class SkillDistributionNotFoundError(
    SkillDistributionError
):
    pass


class SkillDistributionServiceV110:
    """Local declarative distribution only.

    No network, filesystem package installation, dynamic code import,
    activation or execution authority is provided here.
    """

    def __init__(
        self,
        *,
        catalog: LocalSkillCatalogV110,
        lifecycle: SkillLifecycleManagerV102,
    ):
        if not isinstance(
            catalog,
            LocalSkillCatalogV110,
        ):
            raise TypeError(
                "LocalSkillCatalogV110 required"
            )
        if not isinstance(
            lifecycle,
            SkillLifecycleManagerV102,
        ):
            raise TypeError(
                "SkillLifecycleManagerV102 required"
            )

        self._catalog = catalog
        self._lifecycle = lifecycle

    def publish(
        self,
        contract: SkillDeveloperContractV102,
    ) -> SkillCatalogEntryV110:
        artifact = encode_skill_package_v110(
            contract
        )
        return self._catalog.add_package(
            artifact
        )

    def export_package(
        self,
        skill_id: str,
    ) -> SkillPackageArtifactV110:
        entry = self._catalog.get(skill_id)
        if entry is None:
            raise SkillDistributionNotFoundError(
                str(skill_id)
            )

        return SkillPackageArtifactV110(
            skill_id=entry.skill_id,
            skill_version=entry.skill_version,
            package_bytes=bytes(entry.package_bytes),
            sha256=entry.package_sha256,
        )

    def install(
        self,
        skill_id: str,
    ) -> SkillLifecycleRecordV102:
        artifact = self.export_package(skill_id)
        contract = decode_skill_package_v110(
            artifact.package_bytes,
            expected_sha256=artifact.sha256,
        )
        return self._lifecycle.install(
            contract
        )

    def unpublish(self, skill_id: str) -> bool:
        return self._catalog.remove(skill_id)


__all__ = [
    "SkillDistributionError",
    "SkillDistributionNotFoundError",
    "SkillDistributionServiceV110",
]
