from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from collections.abc import Mapping
from typing import Any, Optional

from .developer_contract import (
    SkillDeveloperContractV102,
    build_skill_developer_contract_v102,
)
from .manifest import SkillCapabilityRef, SkillManifest


SKILL_PACKAGE_SCHEMA_V110 = "aura.skill-package.v1"
MAX_SKILL_PACKAGE_BYTES_V110 = 1_048_576


class SkillPackageError(ValueError):
    pass


class SkillPackageSchemaError(SkillPackageError):
    pass


class SkillPackageIntegrityError(SkillPackageError):
    pass


class SkillPackageMetadataError(SkillPackageError):
    pass


@dataclass(frozen=True)
class SkillPackageArtifactV110:
    skill_id: str
    skill_version: str
    package_bytes: bytes
    sha256: str


def _json_safe(value: Any, *, path: str = "$") -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise SkillPackageMetadataError(
                "non_finite_number:" + path
            )
        return value

    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise SkillPackageMetadataError(
                    "non_string_key:" + path
                )
            out[key] = _json_safe(
                item,
                path=path + "." + key,
            )
        return out

    if isinstance(value, (list, tuple)):
        return [
            _json_safe(item, path=path + "[]")
            for item in value
        ]

    raise SkillPackageMetadataError(
        "non_json_safe:"
        + path
        + ":"
        + type(value).__name__
    )


def _manifest_payload(
    manifest: SkillManifest,
) -> dict[str, Any]:
    return {
        "skill_id": manifest.skill_id,
        "display_name": manifest.display_name,
        "skill_version": manifest.skill_version,
        "capabilities": [
            {
                "provider_id": ref.provider_id,
                "capability_id": ref.capability_id,
            }
            for ref in manifest.capabilities
        ],
        "description": manifest.description,
        "metadata": _json_safe(
            manifest.metadata,
            path="$.manifest.metadata",
        ),
    }


def _contract_payload(
    contract: SkillDeveloperContractV102,
) -> dict[str, Any]:
    return {
        "min_aura_version": contract.min_aura_version,
        "max_aura_version": contract.max_aura_version,
        "execution_model": contract.execution_model,
        "install_scope": contract.install_scope,
        "dynamic_code": bool(contract.dynamic_code),
        "metadata": _json_safe(
            contract.metadata,
            path="$.developer_contract.metadata",
        ),
    }


def _canonical_payload_bytes(
    payload: Mapping[str, Any],
) -> bytes:
    try:
        text = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise SkillPackageSchemaError(
            "canonical_json_failed"
        ) from exc
    return text.encode("utf-8")


def encode_skill_package_v110(
    contract: SkillDeveloperContractV102,
) -> SkillPackageArtifactV110:
    if not isinstance(
        contract,
        SkillDeveloperContractV102,
    ):
        raise TypeError(
            "SkillDeveloperContractV102 required"
        )

    payload = {
        "schema": SKILL_PACKAGE_SCHEMA_V110,
        "manifest": _manifest_payload(contract.manifest),
        "developer_contract": _contract_payload(contract),
    }
    package_bytes = _canonical_payload_bytes(payload)

    if len(package_bytes) > MAX_SKILL_PACKAGE_BYTES_V110:
        raise SkillPackageSchemaError(
            "package_too_large:"
            + str(len(package_bytes))
        )

    digest = sha256(package_bytes).hexdigest()
    return SkillPackageArtifactV110(
        skill_id=contract.manifest.skill_id,
        skill_version=contract.manifest.skill_version,
        package_bytes=package_bytes,
        sha256=digest,
    )


def _strict_keys(
    obj: Mapping[str, Any],
    expected: set[str],
    *,
    path: str,
) -> None:
    actual = set(obj)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise SkillPackageSchemaError(
            path
            + ":keys:"
            + "missing="
            + ",".join(missing)
            + ";unknown="
            + ",".join(unknown)
        )


def decode_skill_package_v110(
    package_bytes: bytes,
    *,
    expected_sha256: Optional[str] = None,
) -> SkillDeveloperContractV102:
    if not isinstance(
        package_bytes,
        (bytes, bytearray),
    ):
        raise TypeError("package_bytes must be bytes")

    raw = bytes(package_bytes)
    if not raw:
        raise SkillPackageSchemaError("empty_package")
    if len(raw) > MAX_SKILL_PACKAGE_BYTES_V110:
        raise SkillPackageSchemaError(
            "package_too_large:" + str(len(raw))
        )

    digest = sha256(raw).hexdigest()
    if (
        expected_sha256 is not None
        and digest != str(expected_sha256).strip().lower()
    ):
        raise SkillPackageIntegrityError(
            "sha256_mismatch:"
            + digest
        )

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise SkillPackageSchemaError(
            "invalid_utf8_json"
        ) from exc

    if not isinstance(payload, dict):
        raise SkillPackageSchemaError(
            "top_level_object_required"
        )

    _strict_keys(
        payload,
        {"schema", "manifest", "developer_contract"},
        path="$",
    )
    if payload["schema"] != SKILL_PACKAGE_SCHEMA_V110:
        raise SkillPackageSchemaError(
            "unsupported_schema:"
            + str(payload["schema"])
        )

    manifest_payload = payload["manifest"]
    contract_payload = payload["developer_contract"]
    if not isinstance(manifest_payload, dict):
        raise SkillPackageSchemaError(
            "manifest_object_required"
        )
    if not isinstance(contract_payload, dict):
        raise SkillPackageSchemaError(
            "developer_contract_object_required"
        )

    _strict_keys(
        manifest_payload,
        {
            "skill_id",
            "display_name",
            "skill_version",
            "capabilities",
            "description",
            "metadata",
        },
        path="$.manifest",
    )
    _strict_keys(
        contract_payload,
        {
            "min_aura_version",
            "max_aura_version",
            "execution_model",
            "install_scope",
            "dynamic_code",
            "metadata",
        },
        path="$.developer_contract",
    )

    capabilities_payload = manifest_payload["capabilities"]
    if not isinstance(capabilities_payload, list):
        raise SkillPackageSchemaError(
            "capabilities_array_required"
        )

    refs = []
    for index, item in enumerate(capabilities_payload):
        if not isinstance(item, dict):
            raise SkillPackageSchemaError(
                "capability_object_required:"
                + str(index)
            )
        _strict_keys(
            item,
            {"provider_id", "capability_id"},
            path="$.manifest.capabilities["
            + str(index)
            + "]",
        )
        refs.append(
            SkillCapabilityRef(
                str(item["provider_id"]),
                str(item["capability_id"]),
            )
        )

    manifest = SkillManifest(
        skill_id=str(manifest_payload["skill_id"]),
        display_name=str(
            manifest_payload["display_name"]
        ),
        skill_version=str(
            manifest_payload["skill_version"]
        ),
        capabilities=tuple(refs),
        description=str(
            manifest_payload["description"]
        ),
        metadata=_json_safe(
            manifest_payload["metadata"],
            path="$.manifest.metadata",
        ),
    )

    developer_payload = dict(contract_payload)
    developer_payload["metadata"] = _json_safe(
        developer_payload["metadata"],
        path="$.developer_contract.metadata",
    )

    return build_skill_developer_contract_v102(
        manifest=manifest,
        payload=developer_payload,
    )


__all__ = [
    "SKILL_PACKAGE_SCHEMA_V110",
    "MAX_SKILL_PACKAGE_BYTES_V110",
    "SkillPackageError",
    "SkillPackageSchemaError",
    "SkillPackageIntegrityError",
    "SkillPackageMetadataError",
    "SkillPackageArtifactV110",
    "encode_skill_package_v110",
    "decode_skill_package_v110",
]
