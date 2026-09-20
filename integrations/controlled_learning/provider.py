from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from integrations import IntegrationCapability, IntegrationManifest, IntegrationRequest
from runtime.aura_controlled_learning_store_v170 import (
    ControlledLearningCandidateStore,
    MemorySourceAdapter,
)

PROVIDER_ID = "controlled.learning"


class ControlledLearningProvider:
    def __init__(self, store_path: str | Path | None = None) -> None:
        default_store = Path(
            os.environ.get(
                "AURA_L170_CANDIDATE_STORE",
                str(Path(__file__).resolve().parents[2] / "data" / "memory" / "learning_candidates_v170.json"),
            )
        )
        self.store_path = Path(store_path or default_store).expanduser().resolve()
        self._manifest = IntegrationManifest(
            provider_id=PROVIDER_ID,
            display_name="AURA Controlled Continuous Learning",
            provider_version="1.7.0-l170.r2",
            capabilities=(
                IntegrationCapability("learning.propose_candidate", "learning.propose_candidate", "Persist a provenance-aware learning candidate only.", "low", False, "local_write", True),
                IntegrationCapability("learning.list_candidates", "learning.list_candidates", "List local learning candidates.", "low", False, "read", True),
                IntegrationCapability("learning.list_conflicts", "learning.list_conflicts", "List unresolved learning conflicts.", "low", False, "read", True),
                IntegrationCapability("learning.consolidation_plan", "learning.consolidation_plan", "Build a non-mutating consolidation plan.", "low", False, "read", True),
            ),
            auth_kind="local_store",
            metadata={
                "candidate_store_path": str(self.store_path),
                "candidate_is_live_memory": False,
                "approval_capability_exposed": False,
                "live_memory_mutation": False,
                "model_weight_mutation": False,
                "autonomous_self_modification": False,
            },
        )

    @property
    def manifest(self) -> IntegrationManifest:
        return self._manifest

    def health_snapshot(self) -> Mapping[str, Any]:
        return {
            "provider_id": PROVIDER_ID,
            "available": True,
            "health_state": "healthy",
            "candidate_store_path": str(self.store_path),
            "candidate_is_live_memory": False,
            "model_weight_mutation": False,
        }

    def execute(self, request: IntegrationRequest) -> Any:
        capability = str(request.capability_id or "")
        params = dict(request.params or {})
        store = ControlledLearningCandidateStore(self.store_path)

        if capability == "learning.propose_candidate":
            source_kind = str(params.get("source_kind") or "conversation")
            source_ref = str(params.get("source_ref") or "").strip()
            if not source_ref:
                source_ref = MemorySourceAdapter.conversation_ref(
                    str(params.get("raw_source_text") or "")
                )
            provenance = MemorySourceAdapter.provenance(
                source_kind=source_kind,
                source_ref=source_ref,
                observed_at=params.get("observed_at"),
                extractor="aura-conversation-l170-r2",
                confidence=float(params.get("confidence") or 1.0),
            )
            result = store.propose(
                subject=str(params.get("subject") or ""),
                predicate=str(params.get("predicate") or ""),
                value=str(params.get("value") or ""),
                provenance=provenance,
                importance=float(params.get("importance") or 0.5),
            )
        elif capability == "learning.list_candidates":
            rows = store.candidates()
            result = {
                "kind": "candidate_list",
                "count": len(rows),
                "items": rows,
                "live_memory_mutation_performed": False,
            }
        elif capability == "learning.list_conflicts":
            rows = store.conflicts()
            result = {
                "kind": "conflict_list",
                "count": len(rows),
                "items": rows,
                "live_memory_mutation_performed": False,
            }
        elif capability == "learning.consolidation_plan":
            result = store.consolidation_plan()
        else:
            raise ValueError(f"unsupported L170 capability: {capability}")

        return {
            "provider_id": PROVIDER_ID,
            "capability_id": capability,
            "l170_result": result,
            "live_memory_mutation_performed": False,
            "model_weight_mutation_performed": False,
        }

# AURA_L170_R3_EXPLICIT_APPROVAL_CONTROLLED_CONSOLIDATION
_AURA_L170_R3_BASE_PROVIDER = ControlledLearningProvider

class ControlledLearningProvider(_AURA_L170_R3_BASE_PROVIDER):
    def __init__(self, store_path=None):
        super().__init__(store_path=store_path)
        old = self._manifest
        metadata = dict(old.metadata or {})
        metadata.update({
            "approval_capability_exposed": True,
            "controlled_consolidation_capability_exposed": True,
            "controlled_learning_ledger_write": True,
            "live_memory_backend_injection": False,
            "model_weight_mutation": False,
            "autonomous_self_modification": False,
        })
        self._manifest = IntegrationManifest(
            provider_id=old.provider_id,
            display_name=old.display_name,
            provider_version="1.7.0-l170.r3",
            capabilities=tuple(old.capabilities) + (
                IntegrationCapability("learning.approve_candidate", "learning.approve_candidate", "Explicitly approve the latest or selected candidate.", "medium", True, "local_write", True),
                IntegrationCapability("learning.resolve_conflict", "learning.resolve_conflict", "Explicitly resolve a candidate conflict.", "medium", True, "local_write", True),
                IntegrationCapability("learning.consolidate_candidate", "learning.consolidate_candidate", "Explicitly consolidate an approved candidate.", "medium", True, "local_write", True),
                IntegrationCapability("learning.list_consolidated", "learning.list_consolidated", "List consolidated controlled-learning memories.", "low", False, "read", True),
            ),
            auth_kind=old.auth_kind,
            metadata=metadata,
        )

    def execute(self, request: IntegrationRequest) -> Any:
        capability = str(request.capability_id or "")
        params = dict(request.params or {})
        store = ControlledLearningCandidateStore(self.store_path)
        if capability == "learning.approve_candidate":
            result = store.approve_candidate(
                params.get("candidate_id"),
                user_confirmed=bool(params.get("explicit_confirmation")),
            )
        elif capability == "learning.resolve_conflict":
            result = store.resolve_conflict(
                params.get("candidate_id"),
                keep_candidate=bool(params.get("keep_candidate")),
                user_confirmed=bool(params.get("explicit_confirmation")),
            )
        elif capability == "learning.consolidate_candidate":
            result = store.consolidate_candidate(
                params.get("candidate_id"),
                user_confirmed=bool(params.get("explicit_confirmation")),
            )
        elif capability == "learning.list_consolidated":
            rows = store.list_consolidated()
            result = {
                "kind": "consolidated_memory_list",
                "count": len(rows),
                "items": rows,
                "live_memory_backend_injection_performed": False,
                "model_weight_mutation_performed": False,
            }
        else:
            return super().execute(request)
        return {
            "provider_id": PROVIDER_ID,
            "capability_id": capability,
            "l170_result": result,
            "live_memory_backend_injection_performed": False,
            "model_weight_mutation_performed": False,
        }
