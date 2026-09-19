from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .signing import (
    ED25519_PUBLIC_KEY_BYTES_V111,
    SignedSkillPackageEnvelopeV111,
    SkillPackageSignatureError,
    verify_skill_package_signature_v111,
)


class SkillTrustError(RuntimeError):
    pass


class DuplicateTrustedPublisherKeyError(
    SkillTrustError
):
    pass


class UnknownTrustedPublisherError(
    SkillTrustError
):
    pass


class UnknownTrustedKeyError(
    SkillTrustError
):
    pass


class DisabledTrustedKeyError(
    SkillTrustError
):
    pass


class RevokedTrustedKeyError(
    SkillTrustError
):
    pass


@dataclass(frozen=True)
class TrustedPublisherKeyV111:
    publisher_id: str
    key_id: str
    public_key_bytes: bytes
    enabled: bool = True
    revoked: bool = False

    def __post_init__(self) -> None:
        raw = bytes(self.public_key_bytes)
        if (
            len(raw)
            != ED25519_PUBLIC_KEY_BYTES_V111
        ):
            raise SkillTrustError(
                "invalid_public_key_length:"
                + str(len(raw))
            )
        object.__setattr__(
            self,
            "public_key_bytes",
            raw,
        )


class LocalSkillTrustStoreV111:
    """Local public-key trust only.

    No remote key fetch, TOFU or private-key authority exists here.
    """

    def __init__(self):
        self._keys: dict[
            tuple[str, str],
            TrustedPublisherKeyV111,
        ] = {}

    def add_key(
        self,
        key: TrustedPublisherKeyV111,
    ) -> TrustedPublisherKeyV111:
        if not isinstance(
            key,
            TrustedPublisherKeyV111,
        ):
            raise TypeError(
                "TrustedPublisherKeyV111 required"
            )
        ref = (
            str(key.publisher_id).strip().lower(),
            str(key.key_id).strip().lower(),
        )
        if ref in self._keys:
            raise DuplicateTrustedPublisherKeyError(
                ref[0] + ":" + ref[1]
            )

        normalized = TrustedPublisherKeyV111(
            publisher_id=ref[0],
            key_id=ref[1],
            public_key_bytes=key.public_key_bytes,
            enabled=bool(key.enabled),
            revoked=bool(key.revoked),
        )
        self._keys[ref] = normalized
        return normalized

    def get_key(
        self,
        publisher_id: str,
        key_id: str,
    ) -> Optional[TrustedPublisherKeyV111]:
        return self._keys.get(
            (
                str(publisher_id).strip().lower(),
                str(key_id).strip().lower(),
            )
        )

    def list_keys(
        self,
    ) -> tuple[TrustedPublisherKeyV111, ...]:
        return tuple(
            self._keys[key]
            for key in sorted(self._keys)
        )

    def set_enabled(
        self,
        publisher_id: str,
        key_id: str,
        enabled: bool,
    ) -> TrustedPublisherKeyV111:
        ref = (
            str(publisher_id).strip().lower(),
            str(key_id).strip().lower(),
        )
        current = self._keys.get(ref)
        if current is None:
            raise UnknownTrustedKeyError(
                ref[0] + ":" + ref[1]
            )
        if current.revoked and enabled:
            raise RevokedTrustedKeyError(
                ref[0] + ":" + ref[1]
            )

        updated = TrustedPublisherKeyV111(
            publisher_id=current.publisher_id,
            key_id=current.key_id,
            public_key_bytes=current.public_key_bytes,
            enabled=bool(enabled),
            revoked=current.revoked,
        )
        self._keys[ref] = updated
        return updated

    def revoke_key(
        self,
        publisher_id: str,
        key_id: str,
    ) -> TrustedPublisherKeyV111:
        ref = (
            str(publisher_id).strip().lower(),
            str(key_id).strip().lower(),
        )
        current = self._keys.get(ref)
        if current is None:
            raise UnknownTrustedKeyError(
                ref[0] + ":" + ref[1]
            )

        updated = TrustedPublisherKeyV111(
            publisher_id=current.publisher_id,
            key_id=current.key_id,
            public_key_bytes=current.public_key_bytes,
            enabled=False,
            revoked=True,
        )
        self._keys[ref] = updated
        return updated

    def verify(
        self,
        envelope: SignedSkillPackageEnvelopeV111,
    ) -> TrustedPublisherKeyV111:
        if not isinstance(
            envelope,
            SignedSkillPackageEnvelopeV111,
        ):
            raise TypeError(
                "SignedSkillPackageEnvelopeV111 required"
            )

        publisher_keys = [
            key
            for key in self._keys.values()
            if key.publisher_id
            == envelope.publisher_id
        ]
        if not publisher_keys:
            raise UnknownTrustedPublisherError(
                envelope.publisher_id
            )

        key = self.get_key(
            envelope.publisher_id,
            envelope.key_id,
        )
        if key is None:
            raise UnknownTrustedKeyError(
                envelope.publisher_id
                + ":"
                + envelope.key_id
            )
        if key.revoked:
            raise RevokedTrustedKeyError(
                envelope.publisher_id
                + ":"
                + envelope.key_id
            )
        if not key.enabled:
            raise DisabledTrustedKeyError(
                envelope.publisher_id
                + ":"
                + envelope.key_id
            )

        try:
            verify_skill_package_signature_v111(
                envelope=envelope,
                public_key_bytes=key.public_key_bytes,
            )
        except SkillPackageSignatureError:
            raise

        return key


__all__ = [
    "SkillTrustError",
    "DuplicateTrustedPublisherKeyError",
    "UnknownTrustedPublisherError",
    "UnknownTrustedKeyError",
    "DisabledTrustedKeyError",
    "RevokedTrustedKeyError",
    "TrustedPublisherKeyV111",
    "LocalSkillTrustStoreV111",
]
