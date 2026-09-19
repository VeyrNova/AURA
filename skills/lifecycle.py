from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .developer_contract import (
    SkillDeveloperContractError,
    SkillDeveloperContractV102,
)
from .registry import (
    DuplicateSkillError,
    SkillCapabilityRegistryV100,
)
from .runtime import SecureSkillRuntimeV101


class SkillLifecycleError(RuntimeError):
    pass


class SkillAlreadyInstalledError(SkillLifecycleError):
    pass


class SkillNotInstalledError(SkillLifecycleError):
    pass


class SkillAlreadyActiveError(SkillLifecycleError):
    pass


class SkillNotActiveError(SkillLifecycleError):
    pass


class SkillRegistryConflictError(SkillLifecycleError):
    pass


@dataclass(frozen=True)
class SkillLifecycleRecordV102:
    skill_id: str
    state: str
    contract: SkillDeveloperContractV102

    @property
    def active(self) -> bool:
        return self.state == "active"


class SkillLifecycleManagerV102:
    """Metadata-only Skill lifecycle.

    Install stores a validated developer contract only.
    Activate registers the existing SkillManifest in SkillCapabilityRegistryV100.
    Deactivate unregisters only that Skill manifest.
    Uninstall removes lifecycle metadata and never touches IntegrationRegistry.
    Execution remains exclusively owned by SecureSkillRuntimeV101.
    """

    def __init__(
        self,
        *,
        skill_registry: SkillCapabilityRegistryV100,
        secure_runtime: SecureSkillRuntimeV101,
        aura_version: str,
    ):
        if not isinstance(skill_registry, SkillCapabilityRegistryV100):
            raise TypeError("SkillCapabilityRegistryV100 required")
        if not isinstance(secure_runtime, SecureSkillRuntimeV101):
            raise TypeError("SecureSkillRuntimeV101 required")

        self._skill_registry = skill_registry
        self._secure_runtime = secure_runtime
        self._aura_version = str(aura_version or "").strip()
        self._contracts: dict[str, SkillDeveloperContractV102] = {}
        self._active: set[str] = set()

    @property
    def aura_version(self) -> str:
        return self._aura_version

    def install(
        self,
        contract: SkillDeveloperContractV102,
    ) -> SkillLifecycleRecordV102:
        if not isinstance(contract, SkillDeveloperContractV102):
            raise TypeError("SkillDeveloperContractV102 required")

        skill_id = contract.manifest.skill_id
        if skill_id in self._contracts:
            raise SkillAlreadyInstalledError(skill_id)

        contract.validate_for_aura_version(self._aura_version)

        if self._skill_registry.get_manifest(skill_id) is not None:
            raise SkillRegistryConflictError(
                "skill_registry_already_contains:" + skill_id
            )

        self._contracts[skill_id] = contract
        return self.get_record(skill_id)

    def activate(self, skill_id: str) -> SkillLifecycleRecordV102:
        skill_id = str(skill_id or "").strip()
        contract = self._contracts.get(skill_id)
        if contract is None:
            raise SkillNotInstalledError(skill_id)
        if skill_id in self._active:
            raise SkillAlreadyActiveError(skill_id)

        contract.validate_for_aura_version(self._aura_version)

        if self._skill_registry.get_manifest(skill_id) is not None:
            raise SkillRegistryConflictError(
                "skill_registry_already_contains:" + skill_id
            )

        try:
            self._skill_registry.register_manifest(contract.manifest)
        except DuplicateSkillError as exc:
            raise SkillRegistryConflictError(skill_id) from exc

        self._active.add(skill_id)
        return self.get_record(skill_id)

    def deactivate(self, skill_id: str) -> SkillLifecycleRecordV102:
        skill_id = str(skill_id or "").strip()
        if skill_id not in self._contracts:
            raise SkillNotInstalledError(skill_id)
        if skill_id not in self._active:
            raise SkillNotActiveError(skill_id)

        removed = self._skill_registry.unregister_manifest(skill_id)
        if not removed:
            raise SkillRegistryConflictError(
                "active_skill_missing_from_registry:" + skill_id
            )

        self._active.remove(skill_id)
        return self.get_record(skill_id)

    def uninstall(self, skill_id: str) -> bool:
        skill_id = str(skill_id or "").strip()
        if skill_id not in self._contracts:
            return False

        if skill_id in self._active:
            removed = self._skill_registry.unregister_manifest(skill_id)
            if not removed:
                raise SkillRegistryConflictError(
                    "active_skill_missing_from_registry:" + skill_id
                )
            self._active.remove(skill_id)

        self._contracts.pop(skill_id, None)
        return True

    def get_record(
        self,
        skill_id: str,
    ) -> Optional[SkillLifecycleRecordV102]:
        skill_id = str(skill_id or "").strip()
        contract = self._contracts.get(skill_id)
        if contract is None:
            return None
        return SkillLifecycleRecordV102(
            skill_id=skill_id,
            state=("active" if skill_id in self._active else "installed"),
            contract=contract,
        )

    def list_records(self) -> tuple[SkillLifecycleRecordV102, ...]:
        return tuple(
            self.get_record(skill_id)
            for skill_id in sorted(self._contracts)
        )

    def is_active(self, skill_id: str) -> bool:
        return str(skill_id or "").strip() in self._active

    def runtime(self) -> SecureSkillRuntimeV101:
        return self._secure_runtime


__all__ = [
    "SkillLifecycleError",
    "SkillAlreadyInstalledError",
    "SkillNotInstalledError",
    "SkillAlreadyActiveError",
    "SkillNotActiveError",
    "SkillRegistryConflictError",
    "SkillLifecycleRecordV102",
    "SkillLifecycleManagerV102",
]
