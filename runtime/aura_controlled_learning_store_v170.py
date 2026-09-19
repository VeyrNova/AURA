from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from runtime.aura_controlled_continuous_learning_v170 import (
    SCHEMA,
    _fingerprint,
    _key,
    _norm_text,
)


STORE_SCHEMA = "aura.controlled-learning-candidate-store.v170"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemorySourceAdapter:
    ALLOWED_SOURCE_KINDS = frozenset({
        "conversation",
        "memory",
        "project",
        "document",
        "manual",
    })

    @classmethod
    def provenance(
        cls,
        *,
        source_kind: str,
        source_ref: str,
        observed_at: str | None = None,
        extractor: str = "aura-l170",
        confidence: float = 1.0,
    ) -> dict[str, Any]:
        source_kind = _norm_text(source_kind).casefold()
        source_ref = _norm_text(source_ref)
        observed_at = _norm_text(observed_at or _now())
        if source_kind not in cls.ALLOWED_SOURCE_KINDS:
            raise ValueError("unsupported source kind")
        if not source_ref:
            raise ValueError("source_ref required")
        return {
            "source_kind": source_kind,
            "source_ref": source_ref,
            "observed_at": observed_at,
            "extractor": _norm_text(extractor or "aura-l170"),
            "confidence": max(0.0, min(1.0, float(confidence))),
        }

    @staticmethod
    def conversation_ref(text: str) -> str:
        raw = _norm_text(text).encode("utf-8")
        return "conversation:" + hashlib.sha256(raw).hexdigest()[:16]


class ControlledLearningCandidateStore:
    def __init__(self, store_path: str | Path) -> None:
        self.store_path = Path(store_path).expanduser().resolve()

    def _load(self) -> dict[str, Any]:
        if not self.store_path.exists():
            return {
                "schema": STORE_SCHEMA,
                "candidates": [],
                "audit": [],
            }
        data = json.loads(self.store_path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise RuntimeError("invalid candidate store")
        if not isinstance(data.get("candidates"), list):
            raise RuntimeError("invalid candidate rows")
        if not isinstance(data.get("audit"), list):
            raise RuntimeError("invalid audit rows")
        return data

    def _save(self, data: Mapping[str, Any]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=self.store_path.name + ".",
            suffix=".tmp",
            dir=str(self.store_path.parent),
        )
        os.close(fd)
        temp = Path(temp_name)
        try:
            temp.write_text(
                json.dumps(dict(data), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temp, self.store_path)
        finally:
            if temp.exists():
                temp.unlink()

    def propose(
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

        for key in ("source_kind", "source_ref", "observed_at"):
            if not _norm_text(provenance.get(key)):
                raise ValueError(f"provenance.{key} required")

        data = self._load()
        rows = data["candidates"]
        fp = _fingerprint(subject, predicate, value)

        duplicate_of = None
        conflict_with = []
        for row in rows:
            if row.get("fingerprint") == fp:
                duplicate_of = str(row.get("candidate_id") or "")
                break
            if (
                _key(row.get("subject")) == _key(subject)
                and _key(row.get("predicate")) == _key(predicate)
                and _key(row.get("value")) != _key(value)
            ):
                conflict_with.append(str(row.get("candidate_id") or ""))

        state = "duplicate" if duplicate_of else (
            "conflict_review" if conflict_with else "candidate"
        )
        created_at = _now()
        candidate_id = "memcand_" + hashlib.sha256(
            (
                fp
                + "|"
                + str(len(rows))
                + "|"
                + str(provenance.get("source_ref") or "")
            ).encode("utf-8")
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
            "provenance": dict(provenance),
            "created_at": created_at,
            "live_memory_mutation_performed": False,
            "model_weight_mutation_performed": False,
        }
        rows.append(record)
        data["audit"].append({
            "event": "candidate_proposed",
            "candidate_id": candidate_id,
            "state": state,
            "at": created_at,
            "source_ref": provenance.get("source_ref"),
        })
        self._save(data)
        return dict(record)

    def candidates(self) -> list[dict[str, Any]]:
        return [dict(x) for x in self._load()["candidates"]]

    def conflicts(self) -> list[dict[str, Any]]:
        return [
            dict(x)
            for x in self._load()["candidates"]
            if str(x.get("state") or "") == "conflict_review"
        ]

    def consolidation_plan(self) -> dict[str, Any]:
        approved = [
            dict(x)
            for x in self._load()["candidates"]
            if str(x.get("state") or "") == "approved"
            and not bool(x.get("consolidated"))
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

    def audit_log(self) -> list[dict[str, Any]]:
        return [dict(x) for x in self._load()["audit"]]

# AURA_L170_R3_EXPLICIT_APPROVAL_CONTROLLED_CONSOLIDATION

def _aura_l170_r3_find(self, data, candidate_id=None, state=None):
    rows = data.get("candidates") or []
    if candidate_id:
        for row in rows:
            if str(row.get("candidate_id") or "") == str(candidate_id):
                return row
        raise KeyError(candidate_id)
    for row in reversed(rows):
        if state is None or str(row.get("state") or "") == str(state):
            return row
    raise KeyError("no matching candidate")

def _aura_l170_r3_approve(self, candidate_id=None, *, user_confirmed=False):
    if not user_confirmed:
        raise PermissionError("explicit approval required")
    data = self._load()
    row = _aura_l170_r3_find(self, data, candidate_id)
    st = str(row.get("state") or "")
    if st == "duplicate":
        raise ValueError("duplicate candidate cannot be approved")
    if st == "conflict_review":
        raise ValueError("conflict must be resolved before approval")
    if st not in {"candidate", "approved"}:
        raise ValueError("candidate is not approvable")
    row["state"] = "approved"
    row["approved"] = True
    row["approved_at"] = _now()
    data["audit"].append({
        "event": "candidate_approved",
        "candidate_id": row.get("candidate_id"),
        "at": _now(),
        "explicit_user_confirmation": True,
    })
    self._save(data)
    return dict(row)

def _aura_l170_r3_resolve(self, candidate_id=None, *, keep_candidate, user_confirmed=False):
    if not user_confirmed:
        raise PermissionError("explicit approval required")
    data = self._load()
    row = _aura_l170_r3_find(self, data, candidate_id, "conflict_review")
    if str(row.get("state") or "") != "conflict_review":
        raise ValueError("candidate is not in conflict review")
    row["state"] = "candidate" if keep_candidate else "rejected"
    row["conflict_resolution"] = "keep_candidate" if keep_candidate else "reject_candidate"
    row["conflict_resolved_at"] = _now()
    data["audit"].append({
        "event": "conflict_resolved",
        "candidate_id": row.get("candidate_id"),
        "resolution": row["conflict_resolution"],
        "at": _now(),
        "explicit_user_confirmation": True,
    })
    self._save(data)
    return dict(row)

def _aura_l170_r3_consolidate(self, candidate_id=None, *, user_confirmed=False):
    if not user_confirmed:
        raise PermissionError("explicit approval required")
    data = self._load()
    row = _aura_l170_r3_find(self, data, candidate_id, "approved")
    if str(row.get("state") or "") != "approved":
        raise ValueError("only approved candidates can be consolidated")
    ledger = data.setdefault("consolidated_memory", [])
    fp = str(row.get("fingerprint") or "")
    memory = next((x for x in ledger if str(x.get("fingerprint") or "") == fp), None)
    if memory is None:
        memory = {
            "memory_id": "mem_" + hashlib.sha256(
                (fp + "|" + str(row.get("candidate_id") or "")).encode("utf-8")
            ).hexdigest()[:16],
            "candidate_id": row.get("candidate_id"),
            "fingerprint": fp,
            "subject": row.get("subject"),
            "predicate": row.get("predicate"),
            "value": row.get("value"),
            "provenance": dict(row.get("provenance") or {}),
            "importance": row.get("importance"),
            "consolidated_at": _now(),
            "controlled_learning_ledger": True,
            "live_memory_backend_injection_performed": False,
            "model_weight_mutation_performed": False,
        }
        ledger.append(memory)
    row["state"] = "consolidated"
    row["consolidated"] = True
    row["consolidated_at"] = _now()
    row["controlled_memory_id"] = memory.get("memory_id")
    data["audit"].append({
        "event": "candidate_consolidated",
        "candidate_id": row.get("candidate_id"),
        "memory_id": memory.get("memory_id"),
        "at": _now(),
        "explicit_user_confirmation": True,
        "live_memory_backend_injection_performed": False,
        "model_weight_mutation_performed": False,
    })
    self._save(data)
    return {
        "candidate": dict(row),
        "memory": dict(memory),
        "controlled_learning_ledger_write_performed": True,
        "live_memory_backend_injection_performed": False,
        "model_weight_mutation_performed": False,
    }

def _aura_l170_r3_list_consolidated(self):
    return [
        dict(x) for x in self._load().get("consolidated_memory") or []
        if isinstance(x, Mapping)
    ]

ControlledLearningCandidateStore.approve_candidate = _aura_l170_r3_approve
ControlledLearningCandidateStore.resolve_conflict = _aura_l170_r3_resolve
ControlledLearningCandidateStore.consolidate_candidate = _aura_l170_r3_consolidate
ControlledLearningCandidateStore.list_consolidated = _aura_l170_r3_list_consolidated
