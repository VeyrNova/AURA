from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

SCHEMA = "aura.controlled-continuous-learning.v170"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text


def _key(value: Any) -> str:
    return _norm_text(value).casefold()


def _fingerprint(subject: str, predicate: str, value: str) -> str:
    raw = (
        _key(subject)
        + "|"
        + _key(predicate)
        + "|"
        + _key(value)
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Provenance:
    source_kind: str
    source_ref: str
    observed_at: str
    extractor: str = "aura"
    confidence: float = 1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "observed_at": self.observed_at,
            "extractor": self.extractor,
            "confidence": max(0.0, min(1.0, float(self.confidence))),
        }


class ControlledContinuousLearningEngine:
    def __init__(self) -> None:
        self._candidates: list[dict[str, Any]] = []
        self._audit: list[dict[str, Any]] = []

    def propose_candidate(
        self,
        *,
        subject: str,
        predicate: str,
        value: str,
        provenance: Mapping[str, Any],
        importance: float = 0.5,
    ) -> dict[str, Any]:
        subject = _norm_text(subject)
        predicate = _norm_text(predicate)
        value = _norm_text(value)
        if not subject or not predicate or not value:
            raise ValueError("subject/predicate/value required")

        prov = dict(provenance or {})
        for key in ("source_kind", "source_ref", "observed_at"):
            if not _norm_text(prov.get(key)):
                raise ValueError(f"provenance.{key} required")

        fp = _fingerprint(subject, predicate, value)
        duplicate_of = None
        conflict_with = []

        for existing in self._candidates:
            if existing["fingerprint"] == fp:
                duplicate_of = existing["candidate_id"]
                break
            if (
                _key(existing["subject"]) == _key(subject)
                and _key(existing["predicate"]) == _key(predicate)
                and _key(existing["value"]) != _key(value)
            ):
                conflict_with.append(existing["candidate_id"])

        state = "duplicate" if duplicate_of else (
            "conflict_review" if conflict_with else "candidate"
        )
        candidate_id = "memcand_" + hashlib.sha256(
            (fp + "|" + str(len(self._candidates))).encode("utf-8")
        ).hexdigest()[:16]

        record = {
            "schema": SCHEMA,
            "candidate_id": candidate_id,
            "fingerprint": fp,
            "subject": subject,
            "predicate": predicate,
            "value": value,
            "importance": max(0.0, min(1.0, float(importance))),
            "state": state,
            "requires_explicit_approval": True,
            "approved": False,
            "consolidated": False,
            "duplicate_of": duplicate_of,
            "conflict_with": conflict_with,
            "provenance": {
                "source_kind": _norm_text(prov.get("source_kind")),
                "source_ref": _norm_text(prov.get("source_ref")),
                "observed_at": _norm_text(prov.get("observed_at")),
                "extractor": _norm_text(prov.get("extractor") or "aura"),
                "confidence": max(
                    0.0,
                    min(1.0, float(prov.get("confidence") or 0)),
                ),
            },
            "created_at": _now(),
        }
        self._candidates.append(record)
        self._audit.append({
            "event": "candidate_proposed",
            "candidate_id": candidate_id,
            "state": state,
            "at": _now(),
        })
        return dict(record)

    def approve_candidate(
        self,
        candidate_id: str,
        *,
        user_confirmed: bool,
    ) -> dict[str, Any]:
        record = self._find(candidate_id)
        if not user_confirmed:
            raise PermissionError("explicit approval required")
        if record["state"] == "duplicate":
            raise ValueError("duplicate candidate cannot be approved")
        if record["state"] == "conflict_review":
            raise ValueError("conflict must be resolved before approval")
        if record["state"] not in {"candidate", "approved"}:
            raise ValueError("candidate is not approvable")

        record["state"] = "approved"
        record["approved"] = True
        record["approved_at"] = _now()
        self._audit.append({
            "event": "candidate_approved",
            "candidate_id": candidate_id,
            "at": _now(),
        })
        return dict(record)

    def resolve_conflict(
        self,
        candidate_id: str,
        *,
        keep_candidate: bool,
        user_confirmed: bool,
    ) -> dict[str, Any]:
        record = self._find(candidate_id)
        if not user_confirmed:
            raise PermissionError("explicit approval required")
        if record["state"] != "conflict_review":
            raise ValueError("candidate is not in conflict review")

        record["state"] = "candidate" if keep_candidate else "rejected"
        record["conflict_resolution"] = (
            "keep_candidate" if keep_candidate else "reject_candidate"
        )
        record["conflict_resolved_at"] = _now()
        self._audit.append({
            "event": "conflict_resolved",
            "candidate_id": candidate_id,
            "resolution": record["conflict_resolution"],
            "at": _now(),
        })
        return dict(record)

    def consolidation_plan(self) -> dict[str, Any]:
        approved = [
            dict(x)
            for x in self._candidates
            if x["state"] == "approved" and not x["consolidated"]
        ]
        return {
            "schema": SCHEMA,
            "kind": "consolidation_plan",
            "count": len(approved),
            "items": approved,
            "requires_explicit_approval": True,
            "live_memory_mutation_performed": False,
            "model_weight_mutation_performed": False,
        }

    def mark_consolidated(
        self,
        candidate_ids: Iterable[str],
        *,
        user_confirmed: bool,
    ) -> dict[str, Any]:
        if not user_confirmed:
            raise PermissionError("explicit approval required")
        changed = []
        for candidate_id in candidate_ids:
            record = self._find(candidate_id)
            if record["state"] != "approved":
                raise ValueError("only approved candidates can be consolidated")
            record["state"] = "consolidated"
            record["consolidated"] = True
            record["consolidated_at"] = _now()
            changed.append(candidate_id)
            self._audit.append({
                "event": "candidate_consolidated",
                "candidate_id": candidate_id,
                "at": _now(),
            })
        return {
            "schema": SCHEMA,
            "kind": "consolidation_commit",
            "candidate_ids": changed,
            "live_memory_mutation_performed": False,
            "model_weight_mutation_performed": False,
        }

    def candidates(self) -> list[dict[str, Any]]:
        return [dict(x) for x in self._candidates]

    def audit_log(self) -> list[dict[str, Any]]:
        return [dict(x) for x in self._audit]

    def _find(self, candidate_id: str) -> dict[str, Any]:
        for record in self._candidates:
            if record["candidate_id"] == candidate_id:
                return record
        raise KeyError(candidate_id)


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "candidate_proposal": True,
        "provenance_required": True,
        "duplicate_detection": True,
        "conflict_detection": True,
        "explicit_approval_required": True,
        "consolidation_plan": True,
        "audit_log": True,
        "live_memory_mutation": False,
        "model_weight_mutation": False,
        "autonomous_self_modification": False,
    }
