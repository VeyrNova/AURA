from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .catalog import (
    LocalSkillCatalogV110,
    SkillCatalogEntryV110,
)
from .lifecycle import (
    SkillLifecycleManagerV102,
    SkillLifecycleRecordV102,
)
from .package import (
    SkillPackageArtifactV110,
    decode_skill_package_v110,
)
from .signing import SignedSkillPackageEnvelopeV111
from .trust import (
    LocalSkillTrustStoreV111,
    TrustedPublisherKeyV111,
)


class TrustedSkillDistributionError(
    RuntimeError
):
    pass


class TrustedSkillDistributionNotFoundError(
    TrustedSkillDistributionError
):
    pass


class TrustedSkillCatalogMismatchError(
    TrustedSkillDistributionError
):
    pass


@dataclass(frozen=True)
class TrustedSkillAcceptanceV111:
    skill_id: str
    skill_version: str
    publisher_id: str
    key_id: str
    package_sha256: str


class TrustedSkillDistributionServiceV111:
    """Verified local distribution path.

    Signature/trust is checked before catalog acceptance and rechecked
    before installation. Activation/execution remain external authorities.
    """

    def __init__(
        self,
        *,
        catalog: LocalSkillCatalogV110,
        lifecycle: SkillLifecycleManagerV102,
        trust_store: LocalSkillTrustStoreV111,
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
        if not isinstance(
            trust_store,
            LocalSkillTrustStoreV111,
        ):
            raise TypeError(
                "LocalSkillTrustStoreV111 required"
            )

        self._catalog = catalog
        self._lifecycle = lifecycle
        self._trust_store = trust_store
        self._accepted: dict[
            str,
            SignedSkillPackageEnvelopeV111,
        ] = {}

    def accept(
        self,
        envelope: SignedSkillPackageEnvelopeV111,
    ) -> TrustedSkillAcceptanceV111:
        trusted_key = self._trust_store.verify(
            envelope
        )

        artifact = envelope.artifact
        contract = decode_skill_package_v110(
            artifact.package_bytes,
            expected_sha256=artifact.sha256,
        )
        if (
            contract.manifest.skill_id
            != artifact.skill_id
        ):
            raise TrustedSkillCatalogMismatchError(
                "artifact_skill_id_mismatch"
            )
        if (
            contract.manifest.skill_version
            != artifact.skill_version
        ):
            raise TrustedSkillCatalogMismatchError(
                "artifact_skill_version_mismatch"
            )

        entry = self._catalog.add_package(
            artifact
        )
        self._accepted[entry.skill_id] = envelope

        return TrustedSkillAcceptanceV111(
            skill_id=entry.skill_id,
            skill_version=entry.skill_version,
            publisher_id=trusted_key.publisher_id,
            key_id=trusted_key.key_id,
            package_sha256=entry.package_sha256,
        )

    def get_acceptance(
        self,
        skill_id: str,
    ) -> Optional[TrustedSkillAcceptanceV111]:
        key = str(skill_id or "").strip()
        envelope = self._accepted.get(key)
        entry = self._catalog.get(key)
        if envelope is None or entry is None:
            return None

        return TrustedSkillAcceptanceV111(
            skill_id=entry.skill_id,
            skill_version=entry.skill_version,
            publisher_id=envelope.publisher_id,
            key_id=envelope.key_id,
            package_sha256=entry.package_sha256,
        )

    def install(
        self,
        skill_id: str,
    ) -> SkillLifecycleRecordV102:
        key = str(skill_id or "").strip()
        envelope = self._accepted.get(key)
        entry = self._catalog.get(key)

        if envelope is None or entry is None:
            raise TrustedSkillDistributionNotFoundError(
                key
            )

        if (
            entry.package_sha256
            != envelope.artifact.sha256
            or bytes(entry.package_bytes)
            != bytes(
                envelope.artifact.package_bytes
            )
        ):
            raise TrustedSkillCatalogMismatchError(
                "catalog_package_mismatch:"
                + key
            )

        self._trust_store.verify(envelope)

        contract = decode_skill_package_v110(
            envelope.artifact.package_bytes,
            expected_sha256=(
                envelope.artifact.sha256
            ),
        )
        return self._lifecycle.install(
            contract
        )

    def unpublish(self, skill_id: str) -> bool:
        key = str(skill_id or "").strip()
        self._accepted.pop(key, None)
        return self._catalog.remove(key)


__all__ = [
    "TrustedSkillDistributionError",
    "TrustedSkillDistributionNotFoundError",
    "TrustedSkillCatalogMismatchError",
    "TrustedSkillAcceptanceV111",
    "TrustedSkillDistributionServiceV111",
]
