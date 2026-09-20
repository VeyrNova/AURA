from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

from .package import SkillPackageArtifactV110


_PUBLISHER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")
_KEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")
ED25519_SIGNATURE_BYTES_V111 = 64
ED25519_PUBLIC_KEY_BYTES_V111 = 32


class SkillPackageSigningError(ValueError):
    pass


class SkillPackageSignatureError(SkillPackageSigningError):
    pass


def _normalize_id(value: str, *, kind: str) -> str:
    text = str(value or "").strip().lower()
    regex = (
        _PUBLISHER_ID_RE
        if kind == "publisher"
        else _KEY_ID_RE
    )
    if not regex.fullmatch(text):
        raise SkillPackageSigningError(
            "invalid_" + kind + "_id:" + text
        )
    return text


@dataclass(frozen=True)
class SignedSkillPackageEnvelopeV111:
    publisher_id: str
    key_id: str
    artifact: SkillPackageArtifactV110
    signature: bytes
    algorithm: str = "Ed25519"

    def __post_init__(self) -> None:
        if not isinstance(
            self.artifact,
            SkillPackageArtifactV110,
        ):
            raise TypeError(
                "SkillPackageArtifactV110 required"
            )

        publisher_id = _normalize_id(
            self.publisher_id,
            kind="publisher",
        )
        key_id = _normalize_id(
            self.key_id,
            kind="key",
        )
        signature = bytes(self.signature)

        if self.algorithm != "Ed25519":
            raise SkillPackageSigningError(
                "unsupported_algorithm:"
                + str(self.algorithm)
            )
        if (
            len(signature)
            != ED25519_SIGNATURE_BYTES_V111
        ):
            raise SkillPackageSigningError(
                "invalid_signature_length:"
                + str(len(signature))
            )

        object.__setattr__(
            self,
            "publisher_id",
            publisher_id,
        )
        object.__setattr__(
            self,
            "key_id",
            key_id,
        )
        object.__setattr__(
            self,
            "signature",
            signature,
        )


def ed25519_public_key_bytes_v111(
    public_key: Ed25519PublicKey,
) -> bytes:
    if not isinstance(
        public_key,
        Ed25519PublicKey,
    ):
        raise TypeError(
            "Ed25519PublicKey required"
        )
    raw = public_key.public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )
    if (
        len(raw)
        != ED25519_PUBLIC_KEY_BYTES_V111
    ):
        raise SkillPackageSigningError(
            "invalid_public_key_length"
        )
    return raw


def sign_skill_package_v111(
    *,
    artifact: SkillPackageArtifactV110,
    publisher_id: str,
    key_id: str,
    private_key: Ed25519PrivateKey,
) -> SignedSkillPackageEnvelopeV111:
    if not isinstance(
        artifact,
        SkillPackageArtifactV110,
    ):
        raise TypeError(
            "SkillPackageArtifactV110 required"
        )
    if not isinstance(
        private_key,
        Ed25519PrivateKey,
    ):
        raise TypeError(
            "Ed25519PrivateKey required"
        )

    signature = private_key.sign(
        bytes(artifact.package_bytes)
    )
    return SignedSkillPackageEnvelopeV111(
        publisher_id=publisher_id,
        key_id=key_id,
        artifact=artifact,
        signature=signature,
    )


def verify_skill_package_signature_v111(
    *,
    envelope: SignedSkillPackageEnvelopeV111,
    public_key_bytes: bytes,
) -> None:
    if not isinstance(
        envelope,
        SignedSkillPackageEnvelopeV111,
    ):
        raise TypeError(
            "SignedSkillPackageEnvelopeV111 required"
        )

    raw = bytes(public_key_bytes)
    if (
        len(raw)
        != ED25519_PUBLIC_KEY_BYTES_V111
    ):
        raise SkillPackageSignatureError(
            "invalid_public_key_length:"
            + str(len(raw))
        )

    try:
        public_key = (
            Ed25519PublicKey.from_public_bytes(raw)
        )
        public_key.verify(
            envelope.signature,
            bytes(
                envelope.artifact.package_bytes
            ),
        )
    except (
        InvalidSignature,
        ValueError,
    ) as exc:
        raise SkillPackageSignatureError(
            "signature_verification_failed"
        ) from exc


__all__ = [
    "ED25519_SIGNATURE_BYTES_V111",
    "ED25519_PUBLIC_KEY_BYTES_V111",
    "SkillPackageSigningError",
    "SkillPackageSignatureError",
    "SignedSkillPackageEnvelopeV111",
    "ed25519_public_key_bytes_v111",
    "sign_skill_package_v111",
    "verify_skill_package_signature_v111",
]
