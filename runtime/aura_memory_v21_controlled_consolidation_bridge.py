from __future__ import annotations

"""
AURA v2.1 R6 — Controlled Consolidation Bridge.

Two-phase, fail-closed bridge from explicitly approved L170 learning candidates
to the canonical MemoryKernelV2 graph. It does not replace either authority:
- L170 owns candidate capture/approval/consolidated ledger state.
- MemoryKernelV2 owns durable canonical memory truth.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Mapping
import uuid

from memory.kernel_v2 import MemoryKernelV2


class ConsolidationBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class ConsolidationMapping:
    subject_name: str
    predicate: str
    object_text: str
    entity_type: str = "concept"
    scope: str = "user"
    scope_id: str | None = None
    memory_type: str = "semantic"
    valid_from: str | None = None
    valid_to: str | None = None


class ControlledMemoryConsolidationBridge:
    """Explicit-approval, conflict-safe, recoverable L170 -> MemoryKernel bridge."""

    SCHEMA = "aura.memory-v21.controlled-consolidation-bridge.v1"

    def __init__(self, kernel: MemoryKernelV2, store: Any):
        self.kernel = kernel
        self.store = store

    @staticmethod
    def _candidate_id(candidate: Mapping[str, Any]) -> str:
        value = candidate.get("candidate_id") or candidate.get("id")
        value = str(value or "").strip()
        if not value:
            raise ConsolidationBlocked("candidate_id is required")
        return value

    @staticmethod
    def _fingerprint(candidate: Mapping[str, Any]) -> str:
        value = str(candidate.get("fingerprint") or "").strip().casefold()
        if not value:
            raise ConsolidationBlocked("candidate fingerprint is required")
        return value

    @staticmethod
    def _stable_memory_id(fingerprint: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, "aura:l170:" + fingerprint))

    @staticmethod
    def _candidate_confidence(candidate: Mapping[str, Any]) -> float:
        source = candidate.get("source")
        if isinstance(source, Mapping) and source.get("confidence") is not None:
            raw = source.get("confidence")
        else:
            raw = candidate.get("confidence", 1.0)
        try:
            value = float(raw)
        except Exception:
            value = 1.0
        return max(0.0, min(1.0, value))

    @staticmethod
    def _source_metadata(candidate: Mapping[str, Any]) -> dict[str, Any]:
        source = candidate.get("source")
        src = dict(source) if isinstance(source, Mapping) else {}
        for key in ("source_kind", "source_id", "observed_at", "extractor", "confidence"):
            if key not in src and candidate.get(key) is not None:
                src[key] = candidate.get(key)
        return src

    def _all_candidates(self) -> list[dict[str, Any]]:
        if hasattr(self.store, "list_candidates"):
            result = self.store.list_candidates()
            if isinstance(result, Mapping):
                values = result.get("items") or result.get("candidates") or []
            else:
                values = result or []
            return [dict(x) for x in values if isinstance(x, Mapping)]

        plan = self.store.consolidation_plan()
        values = plan.get("items") or [] if isinstance(plan, Mapping) else []
        return [dict(x) for x in values if isinstance(x, Mapping)]

    def candidate(self, candidate_id: str) -> dict[str, Any]:
        target = str(candidate_id or "").strip()
        for row in self._all_candidates():
            try:
                if self._candidate_id(row) == target:
                    return row
            except ConsolidationBlocked:
                continue

        plan = self.store.consolidation_plan()
        for row in (plan.get("items") or []) if isinstance(plan, Mapping) else []:
            if isinstance(row, Mapping) and self._candidate_id(row) == target:
                return dict(row)
        raise KeyError(target)

    def _validate_candidate(self, candidate: Mapping[str, Any], *, allow_consolidated=False) -> None:
        state = str(candidate.get("state") or "").strip().casefold()
        approved = bool(candidate.get("approved"))
        requires = candidate.get("requires_explicit_approval")
        consolidated = bool(candidate.get("consolidated"))

        if requires is not True:
            raise ConsolidationBlocked("candidate is not governed by explicit approval")
        if not approved:
            raise ConsolidationBlocked("candidate is not explicitly approved")
        if state not in ({"approved", "consolidated"} if allow_consolidated else {"approved"}):
            raise ConsolidationBlocked(f"candidate state is not approved: {state!r}")
        if consolidated and not allow_consolidated:
            raise ConsolidationBlocked("candidate is already consolidated")
        if candidate.get("conflict_with"):
            raise ConsolidationBlocked("candidate has unresolved L170 conflict")
        if candidate.get("duplicate_of"):
            raise ConsolidationBlocked("candidate is marked as duplicate")
        self._fingerprint(candidate)

    def _entity_exact(self, mapping: ConsolidationMapping) -> dict[str, Any] | None:
        scope = self.kernel._scope(mapping.scope)
        scope_id = self.kernel._scope_id(scope, mapping.scope_id)
        conn = self.kernel._connect()
        try:
            row = conn.execute(
                """
                SELECT * FROM memory_v21_entities
                WHERE lower(entity_type)=lower(?)
                  AND lower(canonical_name)=lower(?)
                  AND scope=? AND scope_id=? AND status='active'
                ORDER BY updated_at DESC LIMIT 1
                """,
                (
                    str(mapping.entity_type).strip().casefold(),
                    str(mapping.subject_name).strip(),
                    scope.value,
                    scope_id,
                ),
            ).fetchone()
            if row is None:
                return None
            return {
                "entity_id": str(row["entity_id"]),
                "entity_type": str(row["entity_type"]),
                "canonical_name": str(row["canonical_name"]),
                "scope": str(row["scope"]),
                "scope_id": str(row["scope_id"]),
                "confidence": float(row["confidence"]),
            }
        finally:
            conn.close()

    def _fact_by_key(self, fact_key: str) -> dict[str, Any] | None:
        conn = self.kernel._connect()
        try:
            row = conn.execute(
                """
                SELECT * FROM memory_v21_facts
                WHERE fact_key=? AND status='active'
                ORDER BY version DESC, updated_at DESC LIMIT 1
                """,
                (fact_key,),
            ).fetchone()
            if row is None:
                return None
            return {
                "fact_id": str(row["fact_id"]),
                "memory_id": row["memory_id"],
                "subject_entity_id": str(row["subject_entity_id"]),
                "predicate": str(row["predicate"]),
                "object_text": row["object_text"],
                "object_entity_id": row["object_entity_id"],
                "fact_key": str(row["fact_key"]),
                "confidence": float(row["confidence"]),
                "observed_at": row["observed_at"],
                "valid_from": row["valid_from"],
                "valid_to": row["valid_to"],
                "version": int(row["version"]),
                "status": str(row["status"]),
            }
        finally:
            conn.close()

    def _memory_exists(self, memory_id: str) -> bool:
        conn = self.kernel._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM memory_kernel_v2_records WHERE memory_id=? LIMIT 1",
                (memory_id,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    @staticmethod
    def _same_object(fact: Mapping[str, Any], mapping: ConsolidationMapping) -> bool:
        return (
            str(fact.get("object_text") or "").strip().casefold()
            == str(mapping.object_text or "").strip().casefold()
        )

    def preview(
        self,
        candidate: Mapping[str, Any],
        mapping: ConsolidationMapping,
    ) -> dict[str, Any]:
        self._validate_candidate(candidate, allow_consolidated=True)

        candidate_id = self._candidate_id(candidate)
        fingerprint = self._fingerprint(candidate)
        memory_id = self._stable_memory_id(fingerprint)
        fact_key = f"l170:{fingerprint}:{str(mapping.predicate).strip().casefold()}"

        subject = self._entity_exact(mapping)
        predicted_conflicts: list[dict[str, Any]] = []

        if subject is not None:
            existing = self.kernel.v21_list_facts(
                subject_entity_id=subject["entity_id"],
                predicate=str(mapping.predicate).strip().casefold(),
                status="active",
                limit=500,
            )
            for fact in existing:
                if self._same_object(fact, mapping):
                    continue
                if self.kernel.v21_temporal_overlap(
                    fact.get("valid_from"),
                    fact.get("valid_to"),
                    mapping.valid_from,
                    mapping.valid_to,
                ):
                    predicted_conflicts.append({
                        "fact_id": fact["fact_id"],
                        "fact_key": fact["fact_key"],
                        "object_text": fact.get("object_text"),
                        "confidence": fact.get("confidence"),
                    })

        existing_fact = self._fact_by_key(fact_key)
        idempotent = bool(
            existing_fact is not None
            and self._same_object(existing_fact, mapping)
            and self._memory_exists(memory_id)
        )

        return {
            "schema": self.SCHEMA,
            "candidate_id": candidate_id,
            "fingerprint": fingerprint,
            "memory_id": memory_id,
            "fact_key": fact_key,
            "approved": bool(candidate.get("approved")),
            "candidate_state": str(candidate.get("state") or ""),
            "idempotent": idempotent,
            "predicted_conflicts": predicted_conflicts,
            "blocked": bool(predicted_conflicts),
            "mapping": {
                "subject_name": mapping.subject_name,
                "predicate": mapping.predicate,
                "object_text": mapping.object_text,
                "entity_type": mapping.entity_type,
                "scope": mapping.scope,
                "scope_id": mapping.scope_id,
                "memory_type": mapping.memory_type,
                "valid_from": mapping.valid_from,
                "valid_to": mapping.valid_to,
            },
        }

    def _rollback_created(
        self,
        *,
        fact_id: str | None,
        memory_id: str | None,
        entity_id: str | None,
    ) -> None:
        conn = self.kernel._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if fact_id:
                conn.execute("DELETE FROM memory_v21_facts WHERE fact_id=?", (fact_id,))
                conn.execute("DELETE FROM memory_kernel_v2_audit WHERE memory_id=?", (fact_id,))
            if memory_id:
                conn.execute("DELETE FROM memory_kernel_v2_records WHERE memory_id=?", (memory_id,))
                conn.execute("DELETE FROM memory_kernel_v2_audit WHERE memory_id=?", (memory_id,))
            if entity_id:
                refs = conn.execute(
                    """
                    SELECT
                      (SELECT COUNT(*) FROM memory_v21_facts WHERE subject_entity_id=?) +
                      (SELECT COUNT(*) FROM memory_v21_relations
                        WHERE subject_entity_id=? OR object_entity_id=?)
                    """,
                    (entity_id, entity_id, entity_id),
                ).fetchone()[0]
                if int(refs or 0) == 0:
                    conn.execute("DELETE FROM memory_v21_entities WHERE entity_id=?", (entity_id,))
                    conn.execute("DELETE FROM memory_kernel_v2_audit WHERE memory_id=?", (entity_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _commit_l170(self, candidate_id: str) -> Any:
        method = getattr(self.store, "consolidate_candidate", None)
        if method is None:
            raise ConsolidationBlocked("L170 store exposes no consolidate_candidate")

        signature = inspect.signature(method)
        if "user_confirmed" not in signature.parameters:
            raise ConsolidationBlocked(
                "L170 consolidate_candidate has no user_confirmed gate; fail closed"
            )
        return method(candidate_id, user_confirmed=True)

    def consolidate(
        self,
        candidate_id: str,
        mapping: ConsolidationMapping,
        *,
        explicit_confirmation: bool,
    ) -> dict[str, Any]:
        if explicit_confirmation is not True:
            raise ConsolidationBlocked("explicit_confirmation=True is required")

        candidate = self.candidate(candidate_id)
        self._validate_candidate(candidate, allow_consolidated=True)
        preview = self.preview(candidate, mapping)

        if preview["blocked"]:
            raise ConsolidationBlocked(
                "canonical graph conflict predicted; resolve before consolidation"
            )

        # Fully idempotent recovery path: canonical already exists and L170 may
        # have been committed by a prior attempt.
        if preview["idempotent"] and bool(candidate.get("consolidated")):
            return {
                "schema": self.SCHEMA,
                "status": "already_consolidated",
                "candidate_id": preview["candidate_id"],
                "memory_id": preview["memory_id"],
                "fact_key": preview["fact_key"],
                "idempotent": True,
                "l170_committed": True,
                "canonical_committed": True,
            }

        fingerprint = preview["fingerprint"]
        memory_id = preview["memory_id"]
        fact_key = preview["fact_key"]
        confidence = self._candidate_confidence(candidate)
        source = self._source_metadata(candidate)
        observed_at = source.get("observed_at")
        provenance = {
            "kernel": "MemoryKernelV2",
            "created_by": "controlled_learning_bridge_r6",
            "bridge_schema": self.SCHEMA,
            "l170_candidate_id": preview["candidate_id"],
            "l170_fingerprint": fingerprint,
            "l170_source": source,
            "explicit_approval_verified": True,
        }

        created_entity_id = None
        created_memory_id = None
        created_fact_id = None

        subject = self._entity_exact(mapping)
        if subject is None:
            subject = self.kernel.v21_upsert_entity(
                mapping.subject_name,
                entity_type=mapping.entity_type,
                scope=mapping.scope,
                scope_id=mapping.scope_id,
                confidence=confidence,
            )
            created_entity_id = subject["entity_id"]

        existing_memory = self._memory_exists(memory_id)
        if not existing_memory:
            memory_content = (
                f"{mapping.subject_name} | {mapping.predicate} | {mapping.object_text}"
            )
            self.kernel.remember(
                memory_content,
                memory_type=mapping.memory_type,
                scope=mapping.scope,
                scope_id=mapping.scope_id,
                provenance=provenance,
                memory_id=memory_id,
            )
            created_memory_id = memory_id

        existing_fact = self._fact_by_key(fact_key)
        if existing_fact is not None and not self._same_object(existing_fact, mapping):
            if created_memory_id or created_entity_id:
                self._rollback_created(
                    fact_id=None,
                    memory_id=created_memory_id,
                    entity_id=created_entity_id,
                )
            raise ConsolidationBlocked("stable candidate fact key maps to different content")

        if existing_fact is None:
            stored = self.kernel.v21_store_temporal_fact(
                subject["entity_id"],
                mapping.predicate,
                object_text=mapping.object_text,
                memory_id=memory_id,
                fact_key=fact_key,
                confidence=confidence,
                observed_at=observed_at,
                valid_from=mapping.valid_from,
                valid_to=mapping.valid_to,
                provenance=provenance,
                detect_conflicts=False,
            )
            fact = stored["fact"]
            created_fact_id = fact["fact_id"]
        else:
            fact = existing_fact

        try:
            l170_result = self._commit_l170(preview["candidate_id"])
        except Exception:
            self._rollback_created(
                fact_id=created_fact_id,
                memory_id=created_memory_id,
                entity_id=created_entity_id,
            )
            raise

        return {
            "schema": self.SCHEMA,
            "status": "consolidated",
            "candidate_id": preview["candidate_id"],
            "fingerprint": fingerprint,
            "memory_id": memory_id,
            "entity_id": subject["entity_id"],
            "fact_id": fact["fact_id"],
            "fact_key": fact_key,
            "idempotent": False,
            "canonical_committed": True,
            "l170_committed": True,
            "provenance": provenance,
            "l170_result": l170_result,
        }
